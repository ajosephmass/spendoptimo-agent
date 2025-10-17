# SpendOptimoWorkflow Agent

**Execution Agent for AWS Cost Optimizations**

## Overview

The SpendOptimoWorkflow agent is a **separate AgentCore runtime** that executes optimization recommendations using Amazon Nova Lite. It works in tandem with the SpendOptimo analysis agent.

## Architecture

```
SpendOptimo Agent (Analysis)
├─ Model: Amazon Nova Pro
├─ Purpose: Analyze costs, provide recommendations
└─ Returns: Recommendations + Execute button

User clicks "Execute Workflow"
    ↓
SpendOptimoWorkflow Agent (Execution)
├─ Model: Amazon Nova Lite (cheaper, faster)
├─ Input: Recommendations from analysis agent
├─ Tools: AWS service modification tools
└─ Output: Execution results
```

## Capabilities

### Supported AWS Services

- **EC2**: Stop, modify instance type, start, verify
- **S3**: Apply lifecycle policies for storage tiering
- **Lambda**: Update reserved concurrency
- **RDS**: Modify database instance classes
- **EBS**: Modify volume types and sizes

### Tool List

| Tool | Service | Action |
|------|---------|--------|
| `ec2_stop_instance` | EC2 | Stop an instance |
| `ec2_modify_instance_type` | EC2 | Change instance type |
| `ec2_start_instance` | EC2 | Start an instance |
| `ec2_verify_instance_type` | EC2 | Verify modification |
| `s3_put_lifecycle_policy` | S3 | Apply lifecycle policy |
| `lambda_update_concurrency` | Lambda | Update concurrency |
| `rds_modify_instance` | RDS | Modify instance class |
| `ebs_modify_volume` | EBS | Modify volume type/size |

## How It Works

### 1. Recommendation Format

The analysis agent provides recommendations in this format:

```json
{
  "resource_type": "EC2",
  "instance_id": "i-0323c4a8ca47edc2f",
  "current_instance_type": "r5.large",
  "recommended_instance_type": "t3.medium",
  "estimated_monthly_savings": "$50.00",
  "reason": "Policy violation"
}
```

### 2. Workflow Agent Processing

The workflow agent receives these recommendations and:

1. **Identifies the resource type** (EC2, S3, Lambda, etc.)
2. **Selects appropriate tools** based on the action needed
3. **Executes the changes** using AWS APIs
4. **Handles errors intelligently** using LLM reasoning
5. **Verifies the results** to ensure success

### 3. Example Execution

**For EC2 Rightsizing:**
```
User recommendation: r5.large → t3.medium

Workflow Agent thinks:
"I need to rightsize this EC2 instance. Let me:
1. Stop the instance using ec2_stop_instance
2. Modify the type using ec2_modify_instance_type
3. Start it using ec2_start_instance
4. Verify with ec2_verify_instance_type"

Result: ✅ Instance modified successfully
```

**For S3 Storage Tiering:**
```
User recommendation: Apply GLACIER transition after 90 days

Workflow Agent thinks:
"I need to apply a lifecycle policy. Let me:
1. Use s3_put_lifecycle_policy with the bucket name
2. Set transition to GLACIER after 90 days"

Result: ✅ Lifecycle policy applied
```

## Benefits

### 1. **Service-Agnostic**
- No hardcoded workflows needed
- LLM figures out which tools to call
- Easy to add new AWS services

### 2. **Intelligent Error Handling**
```
Scenario: Instance has EBS volume incompatibility

Without LLM:
❌ Hard failure, workflow stops

With Workflow Agent:
✅ "I see this instance has an io2 volume incompatible with t3.medium.
   Let me first modify the volume to gp3, then modify the instance."
```

### 3. **Cost Optimized**
- Uses **Nova Lite** (much cheaper than Nova Pro)
- Only pays for execution time
- No idle costs (serverless)

### 4. **Natural Language Results**
Instead of JSON error codes, you get:
> "Successfully modified instance i-abc123 from r5.large to t3.medium. The instance is now running and verified. Estimated savings: $50/month."

## Deployment

Deploy using the automated script:

```bash
node deploy-enhanced-agent.js
```

Or manually:

```bash
cd infra

# 1. Deploy workflow agent
npx cdk deploy SpendOptimoWorkflowAgent --require-approval never

# 2. Get the endpoint
ENDPOINT=$(aws cloudformation describe-stacks --stack-name SpendOptimoWorkflowAgent --query "Stacks[0].Outputs[?OutputKey=='WorkflowAgentEndpoint'].OutputValue" --output text)

# 3. Update API Lambda
LAMBDA_NAME=$(aws lambda list-functions --query "Functions[?contains(FunctionName, 'SpendOptimoApi')].FunctionName" --output text)
aws lambda update-function-configuration \
  --function-name $LAMBDA_NAME \
  --environment "Variables={...,WORKFLOW_AGENT_ENDPOINT=$ENDPOINT}"

# 4. Deploy API
npx cdk deploy SpendOptimoApi --require-approval never
```

## IAM Permissions

The workflow agent requires permissions to modify AWS resources:

- **EC2**: `StopInstances`, `StartInstances`, `ModifyInstanceAttribute`, `DescribeInstances`
- **S3**: `PutLifecycleConfiguration`, `GetLifecycleConfiguration`
- **Lambda**: `PutFunctionConcurrency`, `UpdateFunctionConfiguration`
- **RDS**: `ModifyDBInstance`, `DescribeDBInstances`
- **EBS**: `ModifyVolume`, `DescribeVolumes`

These are configured in `infra/lib/workflow-agent-stack.ts`.

## Extending with New Services

To add support for a new AWS service:

1. **Add a tool** in `workflow_runtime/app.py`:
```python
@tool
def dynamodb_update_capacity(table_name: str, read_capacity: int, write_capacity: int) -> str:
    """Update DynamoDB table capacity."""
    # Implementation
```

2. **Add to agent tools list**:
```python
Agent(
    model=model,
    tools=[
        # ... existing tools
        dynamodb_update_capacity,
    ]
)
```

3. **Add IAM permissions** in CDK stack

4. **Redeploy**:
```bash
npx cdk deploy SpendOptimoWorkflowAgent --require-approval never
```

That's it! The LLM will automatically know when to call your new tool.

## Testing

Test the workflow agent directly:

```python
import requests

response = requests.post(
    "https://<workflow-agent-endpoint>/invocations",
    json={
        "recommendations": [{
            "resource_type": "EC2",
            "instance_id": "i-abc123",
            "current_instance_type": "r5.large",
            "recommended_instance_type": "t3.medium"
        }]
    }
)

print(response.json())
```

## Troubleshooting

### Workflow does nothing
- Check that recommendations are being passed: Look at CloudWatch logs for "Workflow agent received X recommendations"
- Verify IAM permissions: Agent role must have permissions to modify resources

### Tool execution fails
- Check CloudWatch logs for the specific error
- The agent will explain what went wrong in natural language

### Timeout errors
- Increase the timeout in `api/src/app.py` (default: 300 seconds)
- Or configure async execution if workflows take longer

## Cost Optimization

The workflow agent uses **Amazon Nova Lite** which is significantly cheaper than Nova Pro:

- **Analysis Agent (Nova Pro)**: ~$0.003 per 1K input tokens
- **Workflow Agent (Nova Lite)**: ~$0.0006 per 1K input tokens (5x cheaper!)

By separating analysis from execution, we optimize costs while maintaining intelligent behavior.


