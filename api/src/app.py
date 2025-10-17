"""
SpendOptimo API Lambda handler.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import boto3
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from mangum import Mangum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AgentCore integration
try:
    from agentcore.client import AgentCoreGateway, AgentCoreConfig
    AGENTCORE_AVAILABLE = True
except ImportError:
    logger.warning("AgentCore not available - using fallback")
    AGENTCORE_AVAILABLE = False

# Strands integration
try:
    from automation.strands_runner import SpendOptimoStrandRunner
    STRANDS_AVAILABLE = True
except ImportError:
    logger.warning("Strands SDK not available - using fallback")
    STRANDS_AVAILABLE = False


def _agentcore_gateway():
    """Initialize AgentCore gateway with environment variables."""
    if not AGENTCORE_AVAILABLE:
        raise RuntimeError("AgentCore not available")
    
    config = AgentCoreConfig(
        agent_id_param=os.getenv("AGENTCORE_ID_PARAM", ""),
        agent_alias_param=os.getenv("AGENTCORE_ALIAS_PARAM", ""),
        agent_invoke_param=os.getenv("AGENTCORE_INVOKE_PARAM", ""),
        agent_role_param=os.getenv("AGENTCORE_ROLE_PARAM", ""),
    )
    return AgentCoreGateway(config)


def _strand_runner():
    """Initialize Strands runner."""
    if not STRANDS_AVAILABLE:
        raise RuntimeError("Strands SDK not available")
    
    return SpendOptimoStrandRunner()


async def healthcheck(request: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({"status": "healthy", "timestamp": datetime.now().isoformat()})


async def chat(request: Request) -> JSONResponse:
    """Chat endpoint that routes to AgentCore."""
    try:
        body = await request.json()
        goal = body.get("goal") or body.get("prompt")
        
        if not goal:
            return _error_response("goal or prompt is required", status_code=400, code="missing_goal")
        
        if AGENTCORE_AVAILABLE:
            gateway = _agentcore_gateway()
            # Extract bearer token from Authorization header if present
            auth_header = request.headers.get("authorization", "")
            bearer_token = None
            if auth_header.startswith("Bearer "):
                bearer_token = auth_header[7:]
            
            response = gateway.invoke(goal=goal, bearer_token=bearer_token)
            
            # Wrap response in the format the frontend expects
            formatted_response = {
                "agent": response
            }
            
            return JSONResponse(formatted_response, headers=_cors_headers())
        else:
            # Fallback response when AgentCore is not available
            fallback_response = {
                "message": "AgentCore is not available. Please check your deployment.",
                "error": "agentcore_unavailable"
            }
            return JSONResponse(fallback_response, headers=_cors_headers())

    except Exception as e:
        logger.exception("/v1/chat failed: %s", e)
        return _error_response(str(e), status_code=500, code="chat_failed")


async def analyze(request: Request) -> JSONResponse:
    """Cost analysis endpoint."""
    try:
        from services.analytics import analyze_cost

        params = request.query_params
        days = _parse_positive_int(params.get("days"), default=7)
        group_by = _split_csv(params.get("groupBy"))
        data = analyze_cost(
            days,
            granularity=(params.get("granularity") or "DAILY"),
            group_by=group_by,
            filter_dimension=params.get("filterDimension"),
            filter_value=params.get("filterValue"),
            include_forecast=_parse_bool(params.get("forecast") or params.get("includeForecast"), default=True),
            include_anomalies=_parse_bool(params.get("anomalies") or params.get("includeAnomalies"), default=True),
            include_savings=_parse_bool(params.get("savings") or params.get("includeSavings"), default=True),
        )
        return JSONResponse({"brand": "SpendOptimo", "analysis": data}, headers=_cors_headers())
    except ValueError as exc:
        return _error_response(str(exc), status_code=400, code="invalid_request")
    except Exception as e:
        logger.exception("/v1/analyze failed: %s", e)
        return _error_response(str(e), status_code=500, code="analyze_failed")


async def execute_workflow(request: Request) -> JSONResponse:
    """Execute workflow - uses workflow agent if available, otherwise falls back to Strands."""
    try:
        body = await request.json()
        recommendations = body.get("recommendations", [])
        
        logger.info(f"Execute workflow called with {len(recommendations)} recommendations")
        
        # Get workflow agent endpoint from environment
        workflow_endpoint = os.getenv("WORKFLOW_AGENT_ENDPOINT")
        
        if workflow_endpoint:
            # Use the workflow agent runtime (preferred)
            logger.info("Using workflow agent runtime")
            import requests
            response = requests.post(
                f"{workflow_endpoint}/invocations",
                json={"recommendations": recommendations},
                headers={'Content-Type': 'application/json'},
                timeout=300
            )
            
            if response.status_code == 200:
                result = response.json()
                return JSONResponse({
                    "brand": "SpendOptimoWorkflow",
                    "result": result,
                }, headers=_cors_headers())
            else:
                logger.error(f"Workflow agent returned {response.status_code}: {response.text}")
                # Fall through to Strands fallback
        
        # Fallback to Strands SDK workflow
        logger.info("Using Strands SDK workflow (fallback)")
        runner = _strand_runner()
        result = runner.run(
            action="optimize_existing_instances",
            context={"recommendations": recommendations}
        )
        
        return JSONResponse({
            "brand": "SpendOptimo",
            "action": "optimize_existing_instances",
            "execution": {
                "id": result.execution_id,
                "stateMachineArn": result.state_machine_arn or "strands-sdk-execution",
                "scheduleName": result.schedule_name,
                "payload": result.payload,
            },
        }, headers=_cors_headers())
        
    except Exception as e:
        logger.exception("/v1/execute-workflow failed: %s", e)
        return _error_response(str(e), status_code=500, code="workflow_failed")


async def automation(request: Request) -> JSONResponse:
    """Automation endpoint - routes to workflow agent."""
    try:
        body = await request.json()
        recommendations = body.get("context", {}).get("recommendations", [])
        
        logger.info(f"Automation called with {len(recommendations)} recommendations")
        
        # Get workflow agent endpoint from SSM
        workflow_endpoint = None
        try:
            ssm = boto3.client('ssm')
            param = ssm.get_parameter(Name='/spendoptimo/workflow-agent/invoke-arn')
            workflow_endpoint = param['Parameter']['Value']
            logger.info(f"Found workflow agent endpoint: {workflow_endpoint}")
        except Exception as e:
            logger.warning(f"Could not get workflow agent endpoint from SSM: {e}")
        
        if workflow_endpoint and AGENTCORE_AVAILABLE:
            # Call the workflow agent using AgentCore gateway (same as chat)
            logger.info("Calling workflow agent runtime...")
            
            # Extract bearer token
            auth_header = request.headers.get("authorization", "")
            bearer_token = None
            if auth_header.startswith("Bearer "):
                bearer_token = auth_header[7:]
            
            if not bearer_token:
                logger.warning("No bearer token found for workflow agent")
                return _error_response("Bearer token required for workflow execution", status_code=401)
            
            try:
                import time
                
                # Create execution ID
                execution_id = f"workflow-{int(time.time() * 1000)}"
                
                # Start workflow execution in background using Lambda async invocation
                logger.info(f"Starting async workflow execution: {execution_id}")
                
                # We'll invoke ourselves asynchronously with a special flag
                lambda_client = boto3.client('lambda')
                import os
                current_function = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'SpendOptimoApiFn')
                
                # Prepare async payload
                async_payload = {
                    "_async_workflow": True,
                    "recommendations": recommendations,
                    "bearer_token": bearer_token,
                    "execution_id": execution_id
                }
                
                # Invoke async
                lambda_client.invoke(
                    FunctionName=current_function,
                    InvocationType='Event',  # Asynchronous
                    Payload=json.dumps(async_payload).encode('utf-8')
                )
                
                logger.info(f"Async workflow invocation sent: {execution_id}")
                
                # Return immediately with 202 Accepted
                return JSONResponse({
                    "brand": "SpendOptimoWorkflow",
                    "status": "accepted",
                    "execution_id": execution_id,
                    "result": {
                        "message": f"✅ Workflow execution started for {len(recommendations)} recommendation(s).\n\nThe workflow is running in the background and will:\n1. Stop each instance\n2. Modify instance type\n3. Restart instance\n4. Verify changes\n\nThis process typically takes 3-5 minutes to complete. You can check your EC2 console to monitor progress.",
                        "recommendations_processed": len(recommendations),
                        "execution_details": "Workflow is running asynchronously in the background.",
                        "status": "in_progress"
                    },
                }, status_code=202, headers=_cors_headers())
            except Exception as e:
                logger.error(f"Workflow agent invocation failed: {e}", exc_info=True)
                return _error_response(f"Workflow agent failed: {str(e)}", status_code=500)
        
        # No workflow agent configured
        logger.error("No workflow agent endpoint configured in SSM")
        return _error_response("Workflow agent not configured", status_code=503)
    except Exception as e:
        logger.exception("/v1/automation failed: %s", e)
        return _error_response(str(e), status_code=500, code="automation_failed")


async def options_handler(request: Request) -> JSONResponse:
    """Handle CORS preflight requests."""
    return JSONResponse({}, status_code=200, headers=_cors_headers())


routes = [
    Route("/healthz", endpoint=healthcheck, methods=["GET"]),
    Route("/v1/chat", endpoint=chat, methods=["POST"]),
    Route("/v1/chat", endpoint=options_handler, methods=["OPTIONS"]),
    Route("/v1/analyze", endpoint=analyze, methods=["GET"]),
    Route("/v1/analyze", endpoint=options_handler, methods=["OPTIONS"]),
    Route("/v1/execute-workflow", endpoint=execute_workflow, methods=["POST"]),
    Route("/v1/execute-workflow", endpoint=options_handler, methods=["OPTIONS"]),
    Route("/v1/automation", endpoint=automation, methods=["POST"]),
    Route("/v1/automation", endpoint=options_handler, methods=["OPTIONS"]),
]

app = Starlette(debug=False, routes=routes)
_mangum_handler = Mangum(app)


# Wrap Mangum handler to intercept async workflow executions
def handler(event, context):
    """Lambda handler that intercepts async workflow executions."""
    # Check if this is an async workflow execution
    if isinstance(event, dict) and event.get("_async_workflow"):
        logger.info("Handling async workflow execution")
        recommendations = event.get("recommendations", [])
        bearer_token = event.get("bearer_token")
        execution_id = event.get("execution_id", "unknown")
        
        try:
            # Create a gateway config for the workflow agent
            workflow_config = AgentCoreConfig(
                agent_id_param='/spendoptimo/workflow-agent/id',
                agent_alias_param='/spendoptimo/workflow-agent/alias',
                agent_invoke_param='/spendoptimo/workflow-agent/invoke-arn',
                agent_role_param='/spendoptimo/workflow-agent/role-arn',
            )
            workflow_gateway = AgentCoreGateway(workflow_config)
            
            # Invoke workflow agent with recommendations
            prompt = json.dumps(recommendations, indent=2)
            logger.info(f"Invoking workflow agent for execution {execution_id}")
            response = workflow_gateway.invoke(goal=prompt, bearer_token=bearer_token)
            
            logger.info(f"Workflow execution {execution_id} completed successfully")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "execution_id": execution_id,
                    "status": "completed",
                    "message": response.get("message", "Workflow executed")
                })
            }
        except Exception as e:
            logger.error(f"Async workflow execution {execution_id} failed: {e}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "execution_id": execution_id,
                    "status": "failed",
                    "error": str(e)
                })
            }
    
    # Normal HTTP request - pass to Mangum
    return _mangum_handler(event, context)


def _cors_headers() -> Dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Authorization,Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def _error_response(message: str, *, status_code: int, code: str | None = None) -> JSONResponse:
    body = {"error": code or "error", "message": message}
    return JSONResponse(body, status_code=status_code, headers=_cors_headers())


def _parse_positive_int(value: Optional[str], *, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer value '{value}'") from exc
    if parsed <= 0:
        raise ValueError("Value must be greater than zero")
    return parsed


def _parse_bool(value: Optional[str], *, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y", "on"}:
        return True
    if lowered in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _split_csv(raw: Optional[str]) -> Optional[Iterable[str]]:
    if not raw:
        return None
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or None
