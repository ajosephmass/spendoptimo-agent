"""Utilities for interacting with Amazon Bedrock AgentCore.

The actual SDK (`bedrock-agentcore-sdk-python`) is optional at runtime. When it
is not installed, the helper falls back to stub behaviour so unit tests or local
mocking can proceed. In production you should install the SDK and provide the
required credentials/policy to allow AgentCore provisioning and invocation.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence

import boto3
from requests import HTTPError  # type: ignore

logger = logging.getLogger(__name__)

try:
    from bedrock_agentcore_starter_toolkit.services.runtime import (
        HttpBedrockAgentCoreClient,
        generate_session_id,
    )
    STARTER_TOOLKIT_AVAILABLE = True
except ImportError:
    logger.warning("bedrock-agentcore-starter-toolkit not available")
    STARTER_TOOLKIT_AVAILABLE = False
    # Provide stub implementations
    def generate_session_id():
        import uuid
        return str(uuid.uuid4())
    
    class HttpBedrockAgentCoreClient:
        def __init__(self, region):
            self.region = region
        
        def invoke_endpoint(self, **kwargs):
            raise RuntimeError("bedrock-agentcore-starter-toolkit not installed")

try:  # pragma: no cover - optional dependency for real deployments
    from bedrock_agentcore.managed_agents import ManagedAgentClient  # type: ignore
except ImportError:  # pragma: no cover - fall back for local mock
    ManagedAgentClient = None  # type: ignore


@dataclass
class AgentCoreConfig:
    """Configuration references for the SpendOptimo AgentCore deployment."""

    agent_id_param: str
    agent_alias_param: str
    agent_invoke_param: str
    agent_role_param: str
    region_name: str = "us-east-1"


class AgentCoreGateway:
    """Lightweight wrapper that invokes AgentCore Runtime endpoints via the Starter Toolkit HTTP client.

    This expects requests to include an Authorization: Bearer <JWT> header (e.g., Cognito ID token).
    """

    def __init__(self, config: AgentCoreConfig):
        self._config = config
        self._ssm = boto3.client("ssm", region_name=config.region_name)
        self._control = boto3.client("bedrock-agentcore-control", region_name=config.region_name)
        self._http = HttpBedrockAgentCoreClient(config.region_name)

    def _fetch_parameter(self, name: str) -> str:
        logger.debug("Fetching SSM parameter %s", name)
        response = self._ssm.get_parameter(Name=name, WithDecryption=True)
        value = response.get("Parameter", {}).get("Value")
        if not value:
            raise RuntimeError(f"SSM parameter {name} is empty")
        return value

    def fetch_metadata(self) -> Dict[str, str]:
        """Return deployed metadata for the AgentCore gateway/runtime."""
        meta: Dict[str, str] = {
            "gateway_id": self._fetch_parameter(self._config.agent_id_param),
            "agent_alias": self._fetch_parameter(self._config.agent_alias_param),
            "runtime_endpoint_arn": self._fetch_parameter(self._config.agent_invoke_param),
            "agent_role_arn": self._fetch_parameter(self._config.agent_role_param),
        }
        runtime_id_param = self._config.agent_invoke_param.replace("/invoke-arn", "/runtime-id")
        try:
            meta["runtime_id"] = self._fetch_parameter(runtime_id_param)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Runtime ID parameter %s not found: %s", runtime_id_param, exc)
        return meta

    def _resolve_runtime_arn(self, *, endpoint_name: str = "prod") -> str:
        """Resolve AgentRuntimeArn using the AgentRuntimeId stored in SSM (if present).

        Falls back to parsing from the RuntimeEndpointArn if necessary.
        """
        runtime_endpoint_arn = self._fetch_parameter(self._config.agent_invoke_param)
        # If we also have the runtime id in SSM, prefer control plane get to learn runtime ARN
        try:
            runtime_id_param = self._config.agent_invoke_param.replace("/invoke-arn", "/runtime-id")
            runtime_id = self._fetch_parameter(runtime_id_param)
            resp = self._control.get_agent_runtime_endpoint(
                agentRuntimeId=runtime_id,
                endpointName=endpoint_name,
            )
            arn = resp.get("agentRuntimeArn")
            if arn:
                return arn
        except Exception as e:  # noqa: BLE001
            logger.warning("Falling back to endpoint ARN for runtime ARN resolution: %s", e)
        # Fallback: derive runtime ARN from endpoint ARN (strip /runtime-endpoint/alias)
        if "/runtime-endpoint/" in runtime_endpoint_arn:
            return runtime_endpoint_arn.split("/runtime-endpoint/")[0]
        return runtime_endpoint_arn

    def invoke(self, *, goal: str, bearer_token: Optional[str], session_id: Optional[str] = None) -> Dict[str, Any]:
        meta = self.fetch_metadata()
        requested_alias = (meta.get("agent_alias") or "prod").strip() or "prod"
        alias_candidates: Sequence[str] = (
            [requested_alias, "DEFAULT"] if requested_alias.upper() != "DEFAULT" else ["DEFAULT"]
        )

        last_exc: Exception | None = None
        for alias in alias_candidates:
            try:
                payload = self._invoke_single_alias(
                    alias=alias,
                    goal=goal,
                    bearer_token=bearer_token,
                    session_id=session_id,
                    runtime_metadata=meta,
                )
                completion = payload.get("response", "") or payload.get("completion", "")
                return {
                    "completion": completion,
                    "raw": payload,
                    "metadata": {**meta, "runtime_alias_used": alias},
                }
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("AgentCore invocation failed using alias '%s': %s", alias, exc, exc_info=True)
        if last_exc:
            raise last_exc
        raise RuntimeError("AgentCore invocation failed without a captured exception")

    def _invoke_single_alias(
        self,
        *,
        alias: str,
        goal: str,
        bearer_token: Optional[str],
        session_id: Optional[str],
        runtime_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        runtime_id = runtime_metadata.get("runtime_id")
        sess = session_id or generate_session_id()

        if runtime_id:
            try:
                client = boto3.client("bedrock-agent-runtime", region_name=self._config.region_name)
                resp = client.invoke_agent_runtime(
                    agentRuntimeId=runtime_id,
                    agentRuntimeAliasId=alias,
                    sessionId=sess,
                    inputText=goal,
                )
                return {"completion": resp.get("completion", ""), "raw": resp}
            except Exception as exc:  # noqa: BLE001
                logger.warning("InvokeAgentRuntime via SDK failed for alias '%s': %s", alias, exc, exc_info=True)

        runtime_arn = self._resolve_runtime_arn(endpoint_name=alias)
        payload = {"prompt": goal}
        logger.info(
            "Invoking AgentCore runtime arn=%s alias=%s session=%s via HTTP fallback goal=%s",
            runtime_arn,
            alias,
            sess,
            goal,
        )
        try:
            result = self._http.invoke_endpoint(
                agent_arn=runtime_arn,
                payload=payload,
                session_id=sess,
                bearer_token=bearer_token,
                endpoint_name=alias,
            )
            return result
        except Exception as exc:  # noqa: BLE001
            status_code = None
            response_text = ""
            if isinstance(exc, HTTPError) and exc.response is not None:
                status_code = exc.response.status_code
                response_text = exc.response.text or ""
            logger.error(
                "HTTP invoke failed for agent runtime %s (alias=%s session=%s status=%s): %s\nResponse body: %s",
                runtime_arn,
                alias,
                sess,
                status_code,
                exc,
                response_text[:1000],
            )
            raise


class ManagedAgentProvisioner:
    """Manages provisioning via the official AgentCore SDK (if present)."""

    def __init__(self, *, region_name: str = "us-east-1"):
        if ManagedAgentClient is None:
            raise RuntimeError(
                "bedrock-agentcore-sdk-python is not installed. Install it to enable provisioning."
            )
        self._client = ManagedAgentClient(region_name=region_name)
        self._region = region_name

    def ensure_agent(
        self,
        *,
        agent_name: str,
        instruction: str,
        model_id: str,
        action_group_manifest: Dict[str, Any],
    ) -> Dict[str, str]:
        """Create or update the agent and return metadata."""

        logger.info("Ensuring AgentCore deployment for %s", agent_name)
        result = self._client.upsert_agent(
            agent_name=agent_name,
            instruction=instruction,
            foundation_model=model_id,
            action_groups=[action_group_manifest],
        )
        return {
            "agent_id": result.agent_id,
            "agent_alias_id": result.alias_id,
            "agent_invoke_arn": result.invoke_arn,
            "agent_role_arn": result.agent_role_arn,
        }
