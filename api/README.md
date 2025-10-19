# API Gateway and Orchestration Layer

This directory contains the API Gateway Lambda function that orchestrates interactions between the Analysis Agent, Workflow Agent, and frontend UI.

## Purpose

The API layer provides:
- RESTful endpoints for agent invocation
- Authentication via Amazon Cognito
- Dynamic execution plan generation
- Asynchronous workflow orchestration
- CORS handling for web interface

## Key Files

### `src/app.py`
Main API Lambda function with endpoints:

#### `POST /v1/agent/invoke`
Invokes the Analysis Agent with user queries.

**Request:**
```json
{
  "prompt": "Analyze my S3 buckets for cost optimization",
  "sessionId": "user-session-123"
}
```

**Response:**
```json
{
  "response": "I've analyzed your 9 S3 buckets...",
  "sessionId": "user-session-123"
}
```

#### `POST /v1/automation`
Executes optimization workflows via the Workflow Agent.

**Request:**
```json
{
  "action": "optimize_resources",
  "context": {
    "recommendations": [
      {
        "resource_type": "S3",
        "bucket_name": "test-bucket",
        "recommendation": "Apply Intelligent-Tiering"
      }
    ]
  }
}
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "execution_id": "workflow-1234567890",
  "result": {
    "message": "Execution Plan:\n- Apply lifecycle policy to bucket test-bucket\n\nStatus: In progress (3-5 minutes)",
    "execution_details": "..."
  }
}
```

#### `GET /health`
Health check endpoint.

### `requirements.txt`
Python dependencies:
- `boto3`: AWS SDK
- `requests`: HTTP client for invoking agents

## Architecture Flow

```
Frontend (React)
    ↓
API Gateway
    ↓
API Lambda (app.py)
    ↓
├─→ Analysis Agent (via invoke_agent)
│   └─→ Returns: Recommendations with savings
│
└─→ Workflow Agent (async invocation)
    ├─→ Generates dynamic execution plan
    ├─→ Returns 202 Accepted immediately
    └─→ Executes workflow in background
```

## Key Features

### 1. Dynamic Execution Plan Generation

When recommendations are submitted for execution, the API Lambda generates a service-specific execution plan **immediately**:

```python
# Group recommendations by resource type
resource_summary = {}
for rec in recommendations:
    rtype = rec.get('resource_type', 'EC2')
    resource_summary.setdefault(rtype, []).append(rec)

# Generate detailed plan
execution_plan = "**Execution Plan:**\n\n"

if 'EC2' in resource_summary:
    execution_plan += f"**EC2 Instances ({len(resource_summary['EC2'])}):**\n"
    for rec in resource_summary['EC2'][:3]:
        execution_plan += f"- Stop instance `{rec['instance_id']}`, "
        execution_plan += f"modify from `{rec['current_instance_type']}` to "
        execution_plan += f"`{rec['recommended_instance_type']}`, restart\n"

# Similar for S3, Lambda, etc.
```

This provides immediate, relevant feedback to users instead of a generic "processing" message.

### 2. Asynchronous Workflow Execution

The API doesn't wait for workflows to complete. Instead:

1. Generate execution plan from recommendations
2. Return **202 Accepted** with the plan and execution ID
3. Trigger Workflow Agent **asynchronously** using Lambda Event invocation
4. User sees progress immediately, workflow runs in background

```python
lambda_client.invoke(
    FunctionName=current_function,
    InvocationType='Event',  # Async - don't wait for response
    Payload=json.dumps({
        '_async_workflow': True,
        'recommendations': recommendations,
        'execution_id': execution_id
    })
)
```

### 3. CORS Handling

All endpoints return proper CORS headers for web interface:
```python
def _cors_headers():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization'
    }
```

### 4. Authentication

Uses Amazon Cognito JWT tokens for authentication:
```python
def verify_cognito_token(token):
    # Verify JWT signature and expiration
    # Extract user claims (username, email, groups)
    return user_info
```

## Environment Variables

Set by CDK during deployment:

- `ANALYSIS_AGENT_ID`: Bedrock AgentCore runtime ID for Analysis Agent
- `ANALYSIS_AGENT_ALIAS_ID`: Agent alias (default: `TSTALIASID`)
- `WORKFLOW_AGENT_ENDPOINT`: HTTP endpoint for Workflow Agent invocation
- `AWS_REGION`: AWS region (default: us-east-1)
- `COGNITO_USER_POOL_ID`: Cognito User Pool for authentication
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Deployment

Deployed via AWS CDK as part of the API stack:

```bash
cd infra
npx cdk deploy SpendOptimoApi
```

The CDK stack creates:
- Lambda function with Python 3.11 runtime
- API Gateway REST API with CORS enabled
- IAM role with permissions to invoke Bedrock agents
- CloudWatch log group for request/response logging

## IAM Permissions

The API Lambda requires:
```typescript
// Invoke Bedrock agents
'bedrock-agent-runtime:InvokeAgent',
'bedrock-agent-runtime:InvokeFlow',

// Async Lambda invocation (for workflow execution)
'lambda:InvokeFunction',

// SSM Parameter Store (for config)
'ssm:GetParameter',

// CloudWatch Logs
'logs:CreateLogGroup',
'logs:CreateLogStream',
'logs:PutLogEvents'
```

## Request/Response Examples

### Get S3 Recommendations

**Request:**
```bash
curl -X POST https://api.spendoptimo.com/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <cognito-token>" \
  -d '{
    "prompt": "Analyze my S3 buckets for cost optimization",
    "sessionId": "session-123"
  }'
```

**Response:**
```json
{
  "response": "I've analyzed your 9 S3 buckets and found 8 optimization opportunities:\n\n- Bucket: test-bucket-1 (missing lifecycle policy, $5/month savings)\n- Bucket: test-bucket-2 (missing lifecycle policy, $7/month savings)\n...\n\nTotal estimated monthly savings: $40",
  "sessionId": "session-123",
  "timestamp": "2025-10-19T12:34:56Z"
}
```

### Execute Optimizations

**Request:**
```bash
curl -X POST https://api.spendoptimo.com/v1/automation \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <cognito-token>" \
  -d '{
    "action": "optimize_resources",
    "context": {
      "recommendations": [
        {
          "resource_type": "S3",
          "bucket_name": "test-bucket-1",
          "recommendation": "Apply Intelligent-Tiering",
          "estimated_monthly_savings": "$5.00"
        }
      ]
    }
  }'
```

**Response (202 Accepted):**
```json
{
  "brand": "SpendOptimoWorkflow",
  "status": "accepted",
  "execution_id": "workflow-1729342496",
  "result": {
    "message": "**Execution Plan:**\n\n**S3 Buckets (1):**\n- Apply Intelligent-Tiering lifecycle policy to bucket `test-bucket-1`\n\n**Estimated Total Monthly Savings:** $5.00\n\n---\n\n**Status:** Workflow execution in progress\n**Estimated Time:** 3-5 minutes",
    "recommendations_processed": 1,
    "execution_details": "...",
    "status": "in_progress"
  }
}
```

## Logs

API request/response logs are in CloudWatch:
```bash
aws logs tail /aws/lambda/SpendOptimoApiFn --follow
```

Look for:
- `[INFO] Received request: POST /v1/agent/invoke`
- `[INFO] Invoking Analysis Agent: {agent_id}`
- `[INFO] Generated execution plan for workflow-{id}`
- `[INFO] Started async workflow execution: workflow-{id}`
- `[ERROR] Failed to invoke agent: {error}`

## Error Handling

All endpoints return structured error responses:

```json
{
  "error": "InvalidRequest",
  "message": "Missing required field: recommendations",
  "status": 400
}
```

Common error codes:
- `400 Bad Request`: Invalid input (missing fields, malformed JSON)
- `401 Unauthorized`: Missing or invalid Cognito token
- `500 Internal Server Error`: AWS API failures, agent invocation errors
- `503 Service Unavailable`: Agent runtime not ready

## Testing

### Local Testing (via AWS)
```bash
# Invoke API Lambda directly
aws lambda invoke \
  --function-name SpendOptimoApiFn \
  --payload '{"httpMethod":"POST","path":"/v1/agent/invoke","body":"{\"prompt\":\"test\"}"}' \
  response.json

cat response.json
```

### Integration Testing
```bash
# Use the deployed API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name SpendOptimoApi \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text)

curl -X POST $API_URL/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Get rightsizing recommendations"}'
```

## Extending the API

### Adding New Endpoints

1. Add route handler in `app.py`:
```python
elif path == '/v1/cost-forecast' and method == 'POST':
    # Get cost forecast from Cost Explorer
    body = json.loads(event.get('body', '{}'))
    days = body.get('days', 30)
    
    ce = boto3.client('ce')
    response = ce.get_cost_forecast(
        TimePeriod={
            'Start': start_date,
            'End': end_date
        },
        Metric='UNBLENDED_COST',
        Granularity='DAILY'
    )
    
    return JSONResponse({
        'forecast': response['Total']['Amount']
    }, status_code=200, headers=_cors_headers())
```

2. Update API Gateway in `infra/lib/api-stack.ts` (if needed for custom domains/auth)

3. Document in this README

## Performance

Typical response times:
- **Health check**: <50ms
- **Agent invocation**: 2-5 seconds (depends on agent reasoning)
- **Workflow trigger**: <500ms (returns 202 immediately)

For large recommendation sets (50+ resources):
- Execution plan generation: <1 second
- Total response time: Still <1 second (async execution)

## Security Best Practices

1. **Always validate Cognito tokens** before processing requests
2. **Sanitize user input** to prevent injection attacks
3. **Use least-privilege IAM** - only grant necessary permissions
4. **Enable CloudTrail** for audit logging of all API calls
5. **Implement rate limiting** to prevent abuse
6. **Use AWS WAF** for DDoS protection (in production)

## Troubleshooting

### Issue: "Agent not found" errors
**Cause**: Agent runtime not deployed or environment variable not set
**Fix**: Deploy agents first, then API: `npx cdk deploy SpendOptimoAgentCore SpendOptimoWorkflowAgent SpendOptimoApi`

### Issue: CORS errors in browser
**Cause**: Missing CORS headers or incorrect origin
**Fix**: Check `_cors_headers()` function returns proper headers for all responses

### Issue: "InvokeAgent timeout"
**Cause**: Agent taking too long to respond (>30 seconds)
**Fix**: Increase API Lambda timeout in `api-stack.ts`: `timeout: cdk.Duration.seconds(60)`


