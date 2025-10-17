from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _load_gateway_manifest() -> Dict[str, Any]:
    try:
        here = os.path.dirname(__file__)
        with open(os.path.join(here, 'gateway.manifest.json'), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        logger.warning('Failed to load gateway.manifest.json: %s', e)
        return {"tools": []}


def _build_openapi_from_manifest(api_base: str, manifest: Dict[str, Any], *, title: str) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        'openapi': '3.0.0',
        'info': {'title': title, 'version': '1.0.0'},
        'servers': [{'url': api_base.rstrip('/')}] if api_base else [],
        'paths': {},
    }
    tools = manifest.get('tools') or []
    for t in tools:
        url = t.get('url') or t.get('path') or '/'
        method = (t.get('method') or 'GET').lower()
        if url.startswith('http'):
            try:
                # Extract path after scheme+host
                path_part = '/' + url.split('://', 1)[1].split('/', 1)[1]
            except Exception:  # noqa: BLE001
                path_part = '/'
        else:
            path_part = url
        spec['paths'].setdefault(path_part, {})[method] = {
            'operationId': t.get('name') or (method + path_part.replace('/', '_')),
            'responses': {'200': {'description': 'OK'}},
        }
    return spec


def _ensure_gateway(
    ac,
    *,
    name: str,
    instruction: str,
    role_arn: Optional[str],
    authorizer_type: str = 'AWS_IAM',
    jwt_discovery_url: Optional[str] = None,
    jwt_allowed_audience: Optional[list[str]] = None,
    jwt_allowed_clients: Optional[list[str]] = None,
) -> str:
    items = ac.list_gateways().get('items', [])
    for it in items:
        if it.get('name') == name:
            return it.get('gatewayId') or it.get('id') or ''
    kwargs: Dict[str, Any] = {
        'name': name,
        'protocolType': 'MCP',
        'protocolConfiguration': {'mcp': {
            'supportedVersions': ['2025-03-26'],
            'instructions': instruction,
            'searchType': 'SEMANTIC',
        }},
        'authorizerType': authorizer_type,
        'roleArn': role_arn or None,
    }
    if (authorizer_type or '').upper() == 'CUSTOM_JWT':
        if not jwt_discovery_url:
            raise ValueError('JwtDiscoveryUrl is required for CUSTOM_JWT authorizer')
        auth_cfg: Dict[str, Any] = {'customJWTAuthorizer': {'discoveryUrl': jwt_discovery_url}}
        if jwt_allowed_audience:
            auth_cfg['customJWTAuthorizer']['allowedAudience'] = jwt_allowed_audience
        if jwt_allowed_clients:
            auth_cfg['customJWTAuthorizer']['allowedClients'] = jwt_allowed_clients
        kwargs['authorizerConfiguration'] = auth_cfg
    resp = ac.create_gateway(**kwargs)
    return resp.get('gatewayId') or resp.get('gateway', {}).get('gatewayId') or ''


def _wait_gateway_ready(ac, *, gateway_id: str, timeout_s: int = 300, poll_s: int = 5) -> None:
    import time
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        try:
            g = ac.get_gateway(gatewayIdentifier=gateway_id)
            status = g.get('status') or g.get('gateway', {}).get('status')
            reasons = g.get('statusReasons') or g.get('gateway', {}).get('statusReasons') or []
            logger.info('Gateway %s status=%s reasons=%s', gateway_id, status, reasons)
            if status and status.upper() not in ('CREATING', 'UPDATING', 'PENDING'):
                if status.upper() == 'FAILED':
                    raise RuntimeError(f'Gateway {gateway_id} failed: {reasons}')
                return
            time.sleep(poll_s)
        except ClientError as e:
            logger.warning('GetGateway error (retrying): %s', e)
            time.sleep(poll_s)
    raise TimeoutError(f'Gateway {gateway_id} did not become ready in {timeout_s}s (last status={last_status})')


def _ensure_gateway_target(
    ac,
    *,
    gateway_id: str,
    name: str,
    openapi_spec: Dict[str, Any],
    api_key_provider_arn: Optional[str] = None,
    oauth_provider_arn: Optional[str] = None,
    api_key_value: Optional[str] = None,
    credential_header: str = 'x-api-key',
    credential_location: str = 'HEADER',
) -> str:
    items = ac.list_gateway_targets(gatewayIdentifier=gateway_id).get('items', [])
    for it in items:
        if it.get('name') == name:
            return it.get('targetId') or it.get('id') or ''
    cred_cfgs: list[dict[str, Any]] = []
    if not api_key_provider_arn and not oauth_provider_arn:
        # Try to create an API key provider automatically if a value is supplied (or generate one)
        key_val = api_key_value or os.urandom(12).hex()
        api_key_provider_arn = _ensure_apikey_provider(ac, name=f'{gateway_id}-default-apikey', api_key=key_val)

    if api_key_provider_arn:
        cred_cfgs.append({
            'credentialProviderType': 'API_KEY',
            'credentialProvider': {
                'apiKeyCredentialProvider': {
                    'providerArn': api_key_provider_arn,
                    'credentialParameterName': credential_header,
                    'credentialLocation': credential_location,
                }
            }
        })
    elif oauth_provider_arn:
        cred_cfgs.append({
            'credentialProviderType': 'OAUTH',
            'credentialProvider': {
                'oauthCredentialProvider': {
                    'providerArn': oauth_provider_arn,
                    'scopes': [],
                }
            }
        })
    else:
        raise ValueError('OpenAPI target requires ApiKeyProviderArn or OAuthProviderArn')

    resp = ac.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name=name,
        targetConfiguration={'mcp': {'openApiSchema': {'inlinePayload': json.dumps(openapi_spec)}}},
        credentialProviderConfigurations=cred_cfgs,
    )
    return resp.get('targetId') or resp.get('target', {}).get('targetId') or ''


def _ensure_apikey_provider(ac, *, name: str, api_key: str) -> str:
    """Create or return ARN of an API key credential provider."""
    try:
        # If provider exists, return its ARN
        g = ac.get_api_key_credential_provider(name=name)
        arn = g.get('credentialProviderArn') or g.get('arn')
        if arn:
            return arn
    except ClientError:
        pass
    # Create new provider
    ac.create_api_key_credential_provider(name=name, apiKey=api_key)
    g = ac.get_api_key_credential_provider(name=name)
    return g.get('credentialProviderArn') or ''


def _build_image_via_codebuild(*, region: str, project_name: str, src_bucket: str, src_key: str) -> None:
    cb = boto3.client('codebuild', region_name=region)
    resp = cb.start_build(projectName=project_name, environmentVariablesOverride=[
        {'name': 'SRC_BUCKET', 'value': src_bucket, 'type': 'PLAINTEXT'},
        {'name': 'SRC_KEY', 'value': src_key, 'type': 'PLAINTEXT'},
    ])
    build_id = resp.get('build', {}).get('id')
    if not build_id:
        raise RuntimeError('Failed to start CodeBuild build')
    # Wait for completion
    while True:
        time.sleep(5)
        res = cb.batch_get_builds(ids=[build_id])
        b = (res.get('builds') or [{}])[0]
        status = b.get('buildStatus')
        if status in ('SUCCEEDED', 'FAILED', 'FAULT', 'STOPPED', 'TIMED_OUT'):
            if status != 'SUCCEEDED':
                raise RuntimeError(f'CodeBuild build {build_id} ended with status {status}')
            return


def _ensure_runtime(
    ac,
    *,
    name: str,
    image_uri: Optional[str],
    role_arn: Optional[str],
    authorizer_type: str = 'AWS_IAM',
    jwt_discovery_url: Optional[str] = None,
    jwt_allowed_audience: Optional[list[str]] = None,
    jwt_allowed_clients: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not image_uri:
        return None, None, None
    authorizer_cfg = None
    if (authorizer_type or '').upper() == 'CUSTOM_JWT':
        if not jwt_discovery_url:
            raise ValueError('JwtDiscoveryUrl is required when authorizer_type is CUSTOM_JWT')
        authorizer_cfg = {'customJWTAuthorizer': {'discoveryUrl': jwt_discovery_url}}
        if jwt_allowed_audience:
            authorizer_cfg['customJWTAuthorizer']['allowedAudience'] = jwt_allowed_audience
        if jwt_allowed_clients:
            authorizer_cfg['customJWTAuthorizer']['allowedClients'] = jwt_allowed_clients
    items = ac.list_agent_runtimes().get('agentRuntimes', [])
    existing = next((r for r in items if (r.get('name') or r.get('agentRuntimeName')) == name), None)
    runtime_version: Optional[str] = None
    if not existing:
        try:
            resp = ac.create_agent_runtime(
                agentRuntimeName=name,
                agentRuntimeArtifact={'containerConfiguration': {'containerUri': image_uri}},
                roleArn=role_arn or None,
                networkConfiguration={'networkMode': 'PUBLIC'},
                authorizerConfiguration=authorizer_cfg,
            )
            runtime_id = resp.get('agentRuntimeId') or resp.get('agentRuntime', {}).get('agentRuntimeId')
            runtime_version = resp.get('agentRuntimeVersion') or resp.get('agentRuntime', {}).get('agentRuntimeVersion')
        except ClientError as e:
            # Handle conflict if runtime already exists under the same name
            if e.response.get('Error', {}).get('Code') == 'ConflictException':
                items = ac.list_agent_runtimes().get('agentRuntimes', [])
                existing = next((r for r in items if (r.get('name') or r.get('agentRuntimeName')) == name), None)
                if not existing:
                    raise
                runtime_id = existing.get('agentRuntimeId')
            else:
                raise
    else:
        runtime_id = existing.get('agentRuntimeId')
        update_kwargs: Dict[str, Any] = {
            'agentRuntimeId': runtime_id,
            'agentRuntimeArtifact': {'containerConfiguration': {'containerUri': image_uri}},
            'roleArn': role_arn or None,
            'networkConfiguration': {'networkMode': 'PUBLIC'},
        }
        if authorizer_cfg is not None:
            update_kwargs['authorizerConfiguration'] = authorizer_cfg
        ac.update_agent_runtime(**update_kwargs)
    if runtime_id and not runtime_version:
        try:
            runtime_info = ac.get_agent_runtime(agentRuntimeId=runtime_id)
            runtime_version = runtime_info.get('agentRuntimeVersion') or runtime_info.get('agentRuntime', {}).get('agentRuntimeVersion')
        except Exception as exc:  # noqa: BLE001
            logger.warning('Unable to fetch runtime version for %s: %s', runtime_id, exc)
    # Ensure a runtime endpoint named 'prod'
    endpoint_arn: Optional[str] = None
    latest_version = runtime_version
    try:
        eps = ac.list_agent_runtime_endpoints(agentRuntimeId=runtime_id).get('runtimeEndpoints', [])
        prod = next((e for e in eps if e.get('name') == 'prod'), None)
        if not prod:
            create_args = {'agentRuntimeId': runtime_id, 'name': 'prod'}
            if latest_version:
                create_args['agentRuntimeVersion'] = latest_version
            cer = ac.create_agent_runtime_endpoint(**create_args)
            endpoint_arn = cer.get('agentRuntimeEndpointArn')
        else:
            endpoint_arn = prod.get('agentRuntimeEndpointArn')
            prod_version = prod.get('liveVersion')
            if latest_version and prod_version and prod_version != latest_version:
                logger.info('Updating prod endpoint to runtime version %s (was %s)', latest_version, prod_version)
                ac.update_agent_runtime_endpoint(
                    agentRuntimeId=runtime_id,
                    endpointName='prod',
                    agentRuntimeVersion=latest_version,
                )
    except Exception as e:  # noqa: BLE001
        logger.warning('Unable to ensure runtime endpoint: %s', e)
    return runtime_id, endpoint_arn, latest_version


def _ensure_agentcore_resources(props: Dict[str, Any]) -> Dict[str, str]:
    agent_name = props.get('AgentName') or props.get('agentName') or 'SpendOptimo'
    instruction = props.get('SystemPrompt') or 'You are SpendOptimo, a cost optimization assistant.'
    role_arn = props.get('AgentRoleArn') or ''
    api_base = props.get('ApiUrl') or (props.get('Tools') or [{}])[0].get('path') or ''
    image_uri = props.get('RuntimeContainerUri')

    region = os.getenv('AWS_REGION', 'us-east-1')
    ac = boto3.client('bedrock-agentcore-control', region_name=region)

    logger.info('AgentCore control provisioning (Gateway/Targets/Runtime) for %s', agent_name)
    gateway_id = _ensure_gateway(
        ac,
        name=f'{agent_name}-gateway',
        instruction=instruction,
        role_arn=role_arn,
        authorizer_type=(props.get('AuthorizerType') or 'AWS_IAM'),
        jwt_discovery_url=props.get('JwtDiscoveryUrl'),
        jwt_allowed_audience=props.get('JwtAllowedAudience') or None,
        jwt_allowed_clients=props.get('JwtAllowedClients') or None,
    )
    _wait_gateway_ready(ac, gateway_id=gateway_id)

    manifest = _load_gateway_manifest()
    openapi_spec = _build_openapi_from_manifest(api_base, manifest, title=f'{agent_name}-gateway')
    _ensure_gateway_target(
        ac,
        gateway_id=gateway_id,
        name=f'{agent_name}-targets',
        openapi_spec=openapi_spec,
        api_key_provider_arn=props.get('ApiKeyProviderArn') or None,
        oauth_provider_arn=props.get('OAuthProviderArn') or None,
        api_key_value=props.get('ApiKeyValue') or None,
        credential_header=props.get('ApiKeyHeader') or 'x-api-key',
        credential_location=(props.get('ApiKeyLocation') or 'HEADER').upper(),
    )

    # Build runtime image via CodeBuild if details provided
    if not image_uri and props.get('RuntimeBuildProject'):
        _build_image_via_codebuild(
            region=region,
            project_name=props['RuntimeBuildProject'],
            src_bucket=props['RuntimeSrcBucket'],
            src_key=props['RuntimeSrcKey'],
        )
        image_uri = f"{props['RuntimeRepoUri']}:{props['RuntimeImageTag']}"

    runtime_id, endpoint_arn, runtime_version = _ensure_runtime(
        ac,
        name=agent_name,
        image_uri=image_uri,
        role_arn=role_arn,
        authorizer_type=(props.get('AuthorizerType') or 'AWS_IAM'),
        jwt_discovery_url=props.get('JwtDiscoveryUrl'),
        jwt_allowed_audience=props.get('JwtAllowedAudience') or None,
        jwt_allowed_clients=props.get('JwtAllowedClients') or None,
    )

    # Maintain expected keys so stack outputs/SSM writes succeed without wider changes
    return {
        # Clearer keys
        'GatewayId': gateway_id,
        'AgentAlias': 'prod',
        'RuntimeEndpointArn': endpoint_arn or 'not-configured',
        'AgentRoleArn': role_arn,
        # Back-compat keys
        'AgentId': gateway_id,
        'AgentInvokeArn': endpoint_arn or 'not-configured',
        'AgentRuntimeId': runtime_id or '',
        'AgentRuntimeVersion': runtime_version or '',
    }


def handler(event, _context):
    logger.info('AgentCore provisioner event: %s', event)
    request_type = event.get('RequestType')
    physical_id = event.get('PhysicalResourceId') or 'SpendOptimoAgentCore'

    if request_type == 'Delete':
        return {'PhysicalResourceId': physical_id, 'Data': {}}

    props: Dict[str, Any] = event.get('ResourceProperties', {})
    try:
        data = _ensure_agentcore_resources(props)
    except ClientError as e:
        logger.error('Provisioning failed: %s', e)
        raise
    return {
        'PhysicalResourceId': physical_id,
        'Data': data,
    }
