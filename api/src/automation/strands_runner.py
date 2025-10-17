"""Helpers that wrap the AWS Strands Agents SDK and Step Functions fallback.

The runner prefers native Strands execution when the SDK is installed. When the
SDK is absent (common in local development) or when a Step Functions state
machine ARN is supplied, we execute via AWS APIs instead. In the worst case we
return a mock execution id so the agent can continue reasoning."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from botocore.exceptions import BotoCoreError, ClientError

from services import aws

logger = logging.getLogger(__name__)

try:
    from strands_agents.core import Agent as StrandsAgent  # type: ignore
    from strands_agents.workflow import Step, Workflow  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    StrandsAgent = None  # type: ignore[assignment]
    Step = None  # type: ignore[assignment]
    Workflow = None  # type: ignore[assignment]

AUTOMATION_SCHEDULER_ROLE_ARN = os.getenv("AUTOMATION_SCHEDULER_ROLE_ARN")


@dataclass
class StrandExecutionResult:
    execution_id: str
    state_machine_arn: Optional[str] = None
    schedule_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class SpendOptimoStrandRunner:
    """Abstraction around Strands workflow execution."""

    def __init__(self, *, state_machine_arn: Optional[str] = None):
        self._state_machine_arn = state_machine_arn
        self._agent = self._initialise_strands_agent()

    def run(self, *, action: str, context: Dict[str, Any]) -> StrandExecutionResult:
        """Execute an optimization workflow immediately."""

        payload = self._build_payload(action=action, context=context)

        # Execute via Strands SDK (in-process)
        result = self._run_via_strands(action, context)
        if result:
            execution_id, workflow_results = result
            logger.info("Executed via Strands SDK (in-process)")
            # Update payload with actual workflow results
            payload["workflow"] = workflow_results
            return StrandExecutionResult(
                execution_id=execution_id,
                state_machine_arn="strands-sdk-execution",
                payload=payload,
            )

        # If Strands SDK failed, return error
        logger.error("Strands SDK execution failed for action '%s'", action)
        return StrandExecutionResult(
            execution_id=f"failed-{uuid.uuid4().hex[:8]}",
            state_machine_arn="execution-failed",
            payload=payload,
        )


    def _initialise_strands_agent(self):
        if not StrandsAgent:
            logger.info("Strands SDK not installed; using fallback execution mode")
            return None
        try:
            return StrandsAgent(name="SpendOptimo-Strand")  # type: ignore[call-arg]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unable to initialise Strands agent, fallback to mock mode: %s", exc)
            return None


    def _run_via_strands(self, action: str, context: Dict[str, Any]) -> Optional[tuple]:
        """Execute workflow via Strands SDK and return (execution_id, results)."""
        blueprint = self._workflow_blueprint(action)
        
        # Execute each step manually to capture results
        workflow_results = {}
        execution_id = f"strands-{uuid.uuid4().hex[:8]}"
        
        try:
            from .strands_workflows import execute_workflow_step
        except ImportError:
            logger.warning("Could not import workflow steps")
            return None
        
        try:
            logger.info(f"Executing Strands workflow for action '{action}' with {len(blueprint)} steps")
            
            # Execute each step and capture results
            step_context = {**context}
            for step_def in blueprint:
                step_name = step_def["name"]
                logger.info(f"Executing step: {step_name}")
                
                # Execute the step
                step_result = execute_workflow_step(step_name, step_context)
                
                # Store the result
                workflow_results[step_name] = step_result
                
                # Merge step result into context for next step
                step_context.update(step_result)
                
                # Check if step failed
                if step_result.get("status") == "failed":
                    logger.error(f"Step {step_name} failed: {step_result.get('error')}")
                    workflow_results["status"] = "failed"
                    workflow_results["message"] = f"Workflow failed at step: {step_name}"
                    break
            else:
                # All steps completed successfully
                workflow_results["status"] = "completed"
                workflow_results["message"] = "Workflow completed successfully"
            
            logger.info(f"Strands workflow '{action}' completed with id {execution_id}")
            return (execution_id, workflow_results)
            
        except Exception as exc:
            logger.error(f"Strands workflow execution failed: {str(exc)}")
            logger.exception("Full exception:")
            return None

    def _build_payload(self, *, action: str, context: Dict[str, Any], schedule_time: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "action": action,
            "context": context,
            "workflow": self._workflow_blueprint(action),
            "requestedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if schedule_time:
            payload["scheduleAt"] = schedule_time
        return payload

    def _build_workflow(self, action: str, blueprint: List[Dict[str, Any]], context: Dict[str, Any]):
        if not (Step and Workflow):
            return None
        
        # Import the real workflow steps
        try:
            from .strands_workflows import execute_workflow_step
        except ImportError:
            logger.warning("Could not import real workflow steps, using mock handlers")
            return None
        
        steps = []
        for step in blueprint:
            inputs = dict(step.get("inputs") or {})
            if step.get("passContext", True):
                # Only fill keys that were not explicitly provided.
                for key, value in context.items():
                    inputs.setdefault(key, value)
            
            # Create a handler that calls the real workflow step
            def create_handler(step_name: str):
                def handler(inputs_dict: Dict[str, Any]) -> Dict[str, Any]:
                    # Merge inputs with context
                    merged_context = {**context, **inputs_dict}
                    return execute_workflow_step(step_name, merged_context)
                return handler
            
            steps.append(Step(
                name=step["name"], 
                handler=create_handler(step["name"]), 
                inputs=inputs
            ))  # type: ignore[union-attr]
        
        return Workflow(name=f"SpendOptimo-{action}", steps=steps)  # type: ignore[union-attr]

    def _workflow_blueprint(self, action: str) -> List[Dict[str, Any]]:
        key = action.replace("-", "_").lower()
        base = WORKFLOW_LIBRARY.get(key)
        if not base:
            # Fallback to a generic rightsizing flow
            return WORKFLOW_LIBRARY["rightsizing"]
        return base

    @staticmethod
    def _generate_name(*, prefix: str, suffix: str = "") -> str:
        unique = uuid.uuid4().hex[:12]
        name = f"{prefix}{unique}{suffix}"
        return name[:80]


WORKFLOW_LIBRARY: Dict[str, List[Dict[str, Any]]] = {
    "optimize_existing_instances": [
        {"name": "validate_recommendations", "handler": "spendoptimo.validators.recommendations"},
        {"name": "apply_rightsizing", "handler": "spendoptimo.executors.rightsize_instance"},
        {"name": "verify_optimization", "handler": "spendoptimo.verifiers.optimization_verification"},
    ],
    "rightsizing": [
        {"name": "collect_cost_evidence", "handler": "spendoptimo.collectors.cost_explorer"},
        {"name": "collect_optimizer_signals", "handler": "spendoptimo.collectors.compute_optimizer"},
        {"name": "draft_action_plan", "handler": "spendoptimo.planners.optimization_plan"},
        {"name": "approve_plan", "handler": "spendoptimo.approvals.manual", "inputs": {"requiresApproval": True}},
        {"name": "apply_fix", "handler": "spendoptimo.executors.rightsize"},
        {"name": "verify_outcome", "handler": "spendoptimo.verifiers.cost_explorer"},
    ],
    "rightsizing_rds": [
        {"name": "collect_cost_evidence", "handler": "spendoptimo.collectors.cost_explorer"},
        {"name": "collect_rds_metrics", "handler": "spendoptimo.collectors.rds_utilization"},
        {"name": "draft_action_plan", "handler": "spendoptimo.planners.optimization_plan"},
        {"name": "approve_plan", "handler": "spendoptimo.approvals.manual", "inputs": {"resourceType": "rds"}},
        {"name": "apply_fix", "handler": "spendoptimo.executors.rightsize"},
        {"name": "verify_outcome", "handler": "spendoptimo.verifiers.rds"},
    ],
    "rightsizing_lambda": [
        {"name": "collect_cost_evidence", "handler": "spendoptimo.collectors.cost_explorer"},
        {"name": "collect_lambda_metrics", "handler": "spendoptimo.collectors.lambda_utilization"},
        {"name": "draft_action_plan", "handler": "spendoptimo.planners.optimization_plan"},
        {"name": "approve_plan", "handler": "spendoptimo.approvals.manual", "inputs": {"resourceType": "lambda"}},
        {"name": "apply_fix", "handler": "spendoptimo.executors.rightsize"},
        {"name": "verify_outcome", "handler": "spendoptimo.verifiers.lambda"},
    ],
    "schedule_resize": [
        {"name": "collect_targets", "handler": "spendoptimo.collectors.cost_explorer"},
        {"name": "draft_schedule", "handler": "spendoptimo.planners.scheduling"},
        {"name": "approve_plan", "handler": "spendoptimo.approvals.manual", "inputs": {"requiresApproval": True}},
        {"name": "publish_schedule", "handler": "spendoptimo.executors.scheduler"},
        {"name": "verify_outcome", "handler": "spendoptimo.verifiers.cost_explorer"},
    ],
    "shutdown_idle": [
        {"name": "identify_idle_resources", "handler": "spendoptimo.collectors.idle_detector"},
        {"name": "draft_shutdown_plan", "handler": "spendoptimo.planners.optimization_plan"},
        {"name": "approve_plan", "handler": "spendoptimo.approvals.manual"},
        {"name": "apply_fix", "handler": "spendoptimo.executors.shutdown"},
        {"name": "verify_outcome", "handler": "spendoptimo.verifiers.cost_explorer"},
    ],
}
