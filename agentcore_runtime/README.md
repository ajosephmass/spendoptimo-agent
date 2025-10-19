# Analysis Agent Runtime

This directory contains the runtime code for the **SpendOptimo Analysis Agent**, powered by Amazon Bedrock AgentCore and Amazon Nova Pro.

## Purpose

The Analysis Agent is the primary user-facing agent that:
- Analyzes AWS resources (EC2, S3, Lambda, RDS, etc.)
- Enforces company cost optimization policies
- Generates cost-saving recommendations with realistic estimates
- Orchestrates workflow execution via the Workflow Agent

## Key Files

### `app.py`
Main agent runtime with core tools and logic:
- **Tools**: AWS resource analysis tools (EC2, S3, Lambda, Cost Explorer, Compute Optimizer)
- **Policy Enforcement**: Validates resources against company policies
- **Savings Calculation**: Uses CloudWatch metrics and Cost Explorer for accurate estimates
- **Workflow Orchestration**: Sends approved recommendations to the Workflow Agent

### `company_policies.py`
Defines organization-specific cost optimization policies:
- EC2 instance type restrictions (e.g., "only T3 family up to medium")
- S3 lifecycle policy requirements
- Lambda memory and concurrency limits
- RDS instance class rules

**🔧 Customize this file** to match your organization's policies!

### `automation_workflows.py`
Legacy workflow definitions (mostly deprecated in favor of Workflow Agent).

## Environment Variables

- `API_URL`: API Gateway endpoint for workflow execution
- `AWS_REGION`: AWS region for resource queries (default: us-east-1)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Deployment

This runtime is deployed as a Docker-based Lambda function via AWS CDK:
```bash
cd infra
npx cdk deploy SpendOptimoAgentCore
```

The CDK stack:
- Builds the Docker image with Python dependencies
- Creates IAM roles with read-only AWS permissions
- Registers the agent with Bedrock AgentCore
- Configures the Nova Pro model

## Extending the Agent

### Adding New Tools

1. Define a new tool function in `app.py`:
```python
@tool
def analyze_rds_instances() -> str:
    """Analyze RDS instances for cost optimization."""
    rds = boto3.client('rds')
    instances = rds.describe_db_instances()
    # ... analysis logic
    return json.dumps(results)
```

2. The tool is automatically registered with AgentCore via the `@tool` decorator

3. Update IAM permissions in `infra/lib/agentcore-stack.ts` if needed:
```typescript
agentRole.addToPolicy(new iam.PolicyStatement({
  actions: ['rds:DescribeDBInstances'],
  resources: ['*'],
}));
```

### Adding New Policies

Edit `company_policies.py` to add new rules:
```python
COMPANY_POLICIES = {
    "rds_instance_classes": {
        "allowed_classes": ["db.t3.micro", "db.t3.small"],
        "rationale": "Cost optimization - use T3 instances for non-production"
    }
}
```

Then reference the policy in your tool logic.

## Dependencies

See `requirements.txt` for Python packages:
- `boto3`: AWS SDK
- `requests`: HTTP client for API calls
- Standard library modules (json, logging, datetime, etc.)

Dependencies are installed during Docker image build.

## Logs

Agent execution logs are available in CloudWatch:
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/SpendOptimoAnalysis-<runtime-id>-prod --follow
```

## Architecture

```
User Query
    ↓
API Gateway
    ↓
Analysis Agent (Nova Pro)
    ↓
├─→ AWS APIs (EC2, S3, Lambda, etc.)
├─→ Cost Explorer
├─→ Compute Optimizer
└─→ Company Policies
    ↓
Recommendations
    ↓
Workflow Agent (for execution)
```

## Model: Amazon Nova Pro

- **Context Window**: 300K tokens
- **Strengths**: Complex reasoning, multi-service analysis, conversational understanding
- **Cost**: ~$0.80 per 1M input tokens, ~$3.20 per 1M output tokens
- **Latency**: 2-5 seconds for typical queries

## Testing

Create test resources and query the agent:
```bash
# Create test EC2 instance
node test/create-test-instance.js

# Create test S3 bucket
node test/create-test-bucket.js

# Query via UI or API
curl -X POST https://your-api-url/v1/agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze my S3 buckets for cost optimization"}'
```


