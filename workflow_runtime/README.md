# Workflow Agent Runtime

This directory contains the runtime code for the **SpendOptimo Workflow Agent**, powered by Amazon Bedrock AgentCore and Amazon Nova Lite.

## Purpose

The Workflow Agent is the execution specialist that:
- Receives recommendations from the Analysis Agent
- Orchestrates multi-step AWS resource modifications
- Executes optimizations safely (stop → modify → start → verify)
- Reports execution status and results

## Key Files

### `app.py`
Main agent runtime with execution tools:
- **EC2 Tools**: Stop, modify instance type, start, verify
- **S3 Tools**: Apply lifecycle policies, update storage classes
- **Lambda Tools**: Update memory, concurrency settings
- **RDS Tools**: Modify instance classes (placeholder)
- **EBS Tools**: Modify volume types (placeholder)

### Tool Categories

#### EC2 Instance Management
```python
ec2_stop_instance(instance_id)
ec2_modify_instance_type(instance_id, new_instance_type)
ec2_start_instance(instance_id)
ec2_verify_instance_running(instance_id)
```

#### S3 Lifecycle Management
```python
s3_put_lifecycle_policy(bucket_name, transition_days, storage_class)
```

#### Lambda Optimization
```python
lambda_update_memory(function_name, memory_size_mb)
lambda_update_concurrency(function_name, reserved_concurrent_executions)
```

## Environment Variables

- `AWS_REGION`: AWS region for resource modifications (default: us-east-1)
- `LOG_LEVEL`: Logging verbosity (default: INFO)

## Deployment

This runtime is deployed as a Docker-based Lambda function via AWS CDK:
```bash
cd infra
npx cdk deploy SpendOptimoWorkflowAgent
```

The CDK stack:
- Builds the Docker image with Python dependencies
- Creates IAM roles with **write permissions** for resource modifications
- Registers the agent with Bedrock AgentCore
- Configures the Nova Lite model

## IAM Permissions

The Workflow Agent requires elevated permissions to modify resources:

```typescript
// EC2 permissions
'ec2:StopInstances',
'ec2:StartInstances',
'ec2:ModifyInstanceAttribute',
'ec2:DescribeInstances',
'ec2:DescribeInstanceStatus',

// S3 permissions
's3:PutLifecycleConfiguration',
's3:GetLifecycleConfiguration',

// Lambda permissions
'lambda:UpdateFunctionConfiguration',
'lambda:PutFunctionConcurrency',
'lambda:GetFunctionConfiguration'
```

**⚠️ Security Note**: These are powerful permissions. In production:
- Restrict to specific resource ARNs (not `*`)
- Add resource tags for policy conditions
- Implement approval workflows for high-impact changes
- Enable CloudTrail for audit logging

## Workflow Execution Flow

```
API Gateway (/v1/automation)
    ↓
Lambda (generates execution plan)
    ↓
Async Lambda Invocation
    ↓
Workflow Agent (Nova Lite)
    ↓
├─→ Tool: ec2_stop_instance
├─→ Tool: ec2_modify_instance_type
├─→ Tool: ec2_start_instance
├─→ Tool: ec2_verify_instance_running
└─→ Returns: Execution results
```

## Model: Amazon Nova Lite

- **Context Window**: 300K tokens
- **Strengths**: Fast execution, low cost, tool orchestration
- **Cost**: ~$0.06 per 1M input tokens, ~$0.24 per 1M output tokens (13x cheaper than Nova Pro!)
- **Latency**: <1 second for tool calls
- **Use Case**: High-volume, repetitive tasks where speed and cost matter

## System Prompt

The agent is instructed to:
1. Process recommendations by resource_type (EC2, S3, Lambda)
2. Execute tools with correct parameters
3. Handle failures gracefully with clear error messages
4. Report status for each recommendation
5. Summarize total savings achieved

## Extending the Agent

### Adding New Tools

Example: Add EBS volume modification tool

```python
@tool
def ebs_modify_volume_type(volume_id: str, volume_type: str) -> str:
    """Modify EBS volume type (e.g., gp2 → gp3 for cost savings)."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        ec2 = boto3.client('ec2', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        logger.info(f"Modifying volume {volume_id} to {volume_type}")
        
        ec2.modify_volume(
            VolumeId=volume_id,
            VolumeType=volume_type
        )
        
        return f"Successfully modified volume {volume_id} to {volume_type}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        logger.error(f"Failed to modify volume: {error_code} - {error_msg}")
        return f"Failed to modify volume {volume_id}: {error_code} - {error_msg}"
```

### Update IAM Permissions

Add to `infra/lib/workflow-agent-stack.ts`:
```typescript
workflowAgentRole.addToPolicy(new iam.PolicyStatement({
  actions: ['ec2:ModifyVolume', 'ec2:DescribeVolumes'],
  resources: ['*'],
}));
```

### Update System Prompt

Add guidance for the new tool in `app.py`:
```python
system_prompt = (
    "You are SpendOptimoWorkflow, an AWS optimization execution agent. "
    "..."
    "- For EBS: Use ebs_modify_volume_type(volume_id, volume_type)\n"
    "..."
)
```

## Safety Features

### Built-in Safeguards

1. **No Deletions**: The agent never deletes resources (instances, buckets, functions)
2. **Verification Steps**: After modifying resources, verify they're in the expected state
3. **Error Handling**: All tools use try-except with detailed error messages
4. **Logging**: Every action is logged to CloudWatch for audit trails

### Recommended Additions for Production

1. **Dry-Run Mode**: Test workflows without actually modifying resources
2. **Rollback Capability**: Store previous configurations for easy rollback
3. **Health Checks**: Verify application health after modifications
4. **Change Windows**: Only execute during approved maintenance windows
5. **Approval Workflows**: Require human approval for high-impact changes

## Logs

Workflow execution logs are available in CloudWatch:
```bash
aws logs tail /aws/bedrock-agentcore/runtimes/SpendOptimoWorkflow-<runtime-id>-prod --follow
```

Look for:
- `[INFO] Starting workflow execution: {execution_id}`
- `[INFO] Stopping EC2 instance {instance_id}`
- `[INFO] Successfully applied lifecycle policy to {bucket_name}`
- `[ERROR] Failed to modify Lambda {function_name}: {error}`

## Testing

### Manual Testing via API
```bash
curl -X POST https://your-api-url/v1/automation \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### End-to-End Testing
1. Create test resources: `node test/create-test-bucket.js`
2. Get recommendations from Analysis Agent
3. Execute via UI "Execute Recommendations" button
4. Monitor CloudWatch logs
5. Verify changes: `aws s3api get-bucket-lifecycle-configuration --bucket test-bucket`

## Common Issues

### Issue: "AccessDenied" errors
**Cause**: Missing IAM permissions
**Fix**: Add required actions to `workflow-agent-stack.ts` and redeploy

### Issue: Agent doesn't call the right tool
**Cause**: Ambiguous system prompt or missing parameter examples
**Fix**: Add explicit instructions in system prompt with parameter examples

## Performance

Typical execution times:
- **EC2 Rightsizing**: 2-3 minutes (stop + modify + start + verify)
- **S3 Lifecycle Policy**: 5-10 seconds per bucket
- **Lambda Update**: 3-5 seconds per function

For large batches (50+ resources), consider:
- Parallel execution (modify tool to support batching)
- Progress updates (stream intermediate results)
- Timeout handling (split into multiple workflow executions)

