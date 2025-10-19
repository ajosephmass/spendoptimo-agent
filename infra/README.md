# Infrastructure as Code (AWS CDK)

This directory contains AWS CDK stacks for deploying SpendOptimo's complete infrastructure.

## Purpose

Defines and deploys:
- Bedrock AgentCore runtimes for Analysis and Workflow agents
- API Gateway with Lambda orchestration
- S3 + CloudFront for web UI hosting
- IAM roles and policies
- Cognito authentication
- CloudWatch logging

## Stacks

### 1. `SpendOptimoIam` (`lib/iam-stack.ts`)
Creates IAM roles and policies:
- **Analysis Agent Role**: Read-only access to AWS resources
- **Workflow Agent Role**: Write access for resource modifications
- **API Lambda Role**: Permission to invoke agents

**Deploy:**
```bash
npx cdk deploy SpendOptimoIam
```

### 2. `SpendOptimoAgentCore` (`lib/agentcore-stack.ts`)
Deploys the Analysis Agent:
- Docker-based Lambda runtime with Python dependencies
- Bedrock AgentCore registration with Nova Pro model
- IAM role with read permissions for EC2, S3, Lambda, Cost Explorer, Compute Optimizer
- CloudWatch log group

**Deploy:**
```bash
npx cdk deploy SpendOptimoAgentCore
```

**Build time**: 7-8 minutes (Docker image compilation)

### 3. `SpendOptimoWorkflowAgent` (`lib/workflow-agent-stack.ts`)
Deploys the Workflow Agent:
- Docker-based Lambda runtime with Python dependencies
- Bedrock AgentCore registration with Nova Lite model
- IAM role with write permissions for resource modifications
- CloudWatch log group

**Deploy:**
```bash
npx cdk deploy SpendOptimoWorkflowAgent
```

**Build time**: 7-8 minutes (Docker image compilation)

### 4. `SpendOptimoApi` (`lib/api-stack.ts`)
Deploys the API Gateway and orchestration layer:
- Lambda function with Python 3.11 runtime
- API Gateway REST API with CORS
- Cognito User Pool for authentication
- SSM parameters for agent endpoints

**Deploy:**
```bash
npx cdk deploy SpendOptimoApi
```

### 5. `SpendOptimoSageMaker` (`lib/sagemaker-stack.ts`)
Optional: ML-based cost forecasting endpoint
- SageMaker endpoint (optional, not required for core functionality)

**Deploy:**
```bash
npx cdk deploy SpendOptimoSageMaker
```

### 6. `SpendOptimoUi` (`lib/ui-stack.ts`)
Deploys the web interface:
- S3 bucket for static website hosting
- CloudFront distribution for global CDN
- Origin Access Identity for secure S3 access

**Deploy:**
```bash
npx cdk deploy SpendOptimoUi
```

## Deployment Order

Deploy stacks in this order to satisfy dependencies:

```bash
# 1. IAM roles (optional, can be created by other stacks)
npx cdk deploy SpendOptimoIam

# 2. Agents (can be deployed in parallel)
npx cdk deploy SpendOptimoAgentCore SpendOptimoWorkflowAgent

# 3. API (depends on agents)
npx cdk deploy SpendOptimoApi

# 4. UI (depends on API for configuration)
npx cdk deploy SpendOptimoUi

# 5. Optional: SageMaker
npx cdk deploy SpendOptimoSageMaker
```

Or deploy all at once (recommended):
```bash
npx cdk deploy --all
```

## CDK App Entry Point

### `bin/infra.ts`
Main CDK app that instantiates all stacks:
```typescript
const app = new cdk.App();

new IamStack(app, 'SpendOptimoIam');
new AgentCoreStack(app, 'SpendOptimoAgentCore');
new WorkflowAgentStack(app, 'SpendOptimoWorkflowAgent');
new ApiStack(app, 'SpendOptimoApi');
new UiStack(app, 'SpendOptimoUi');
```

## Configuration

### `cdk.json`
CDK configuration file:
- Feature flags for CDK behavior
- Context values for stack customization

### Environment Variables
Set these before deploying:
```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012
export CDK_DEFAULT_REGION=us-east-1
export CDK_DEFAULT_ACCOUNT=123456789012
```

Or let CDK use your current AWS CLI profile:
```bash
export AWS_PROFILE=my-profile
npx cdk deploy --all
```

## Key Files

### `lib/agentcore-stack.ts`
Analysis Agent deployment:
- **Docker Image**: Built from `../agentcore_runtime/`
- **Model**: Amazon Nova Pro (`amazon.nova-pro-v1:0`)
- **Memory**: 3GB Lambda
- **Timeout**: 300 seconds
- **IAM Permissions**: Read-only access to AWS services

Key code:
```typescript
const agentRole = new iam.Role(this, 'AgentRole', {
  assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
});

agentRole.addToPolicy(new iam.PolicyStatement({
  actions: [
    'ec2:DescribeInstances',
    's3:ListAllMyBuckets',
    'lambda:ListFunctions',
    'ce:GetCostAndUsage',
    'compute-optimizer:GetEC2InstanceRecommendations',
    'cloudwatch:GetMetricStatistics'
  ],
  resources: ['*'],
}));
```

### `lib/workflow-agent-stack.ts`
Workflow Agent deployment:
- **Docker Image**: Built from `../workflow_runtime/`
- **Model**: Amazon Nova Lite (`amazon.nova-lite-v1:0`)
- **Memory**: 2GB Lambda
- **Timeout**: 300 seconds
- **IAM Permissions**: Write access for resource modifications

Key code:
```typescript
workflowAgentRole.addToPolicy(new iam.PolicyStatement({
  actions: [
    'ec2:StopInstances',
    'ec2:StartInstances',
    'ec2:ModifyInstanceAttribute',
    's3:PutLifecycleConfiguration',
    'lambda:UpdateFunctionConfiguration',
    'lambda:PutFunctionConcurrency'
  ],
  resources: ['*'],
}));
```

### `lib/api-stack.ts`
API Gateway and Lambda orchestration:
- **Runtime**: Python 3.11
- **Memory**: 512MB
- **Timeout**: 60 seconds
- **API**: REST API with CORS enabled
- **Auth**: Cognito User Pool

Key code:
```typescript
const api = new apigateway.RestApi(this, 'SpendOptimoApi', {
  restApiName: 'SpendOptimo API',
  defaultCorsPreflightOptions: {
    allowOrigins: apigateway.Cors.ALL_ORIGINS,
    allowMethods: apigateway.Cors.ALL_METHODS,
  },
});

const agentResource = api.root.addResource('v1').addResource('agent');
agentResource.addMethod('POST', new apigateway.LambdaIntegration(apiFn));
```

## Outputs

After deployment, CDK outputs important values:

**SpendOptimoApi:**
- `ApiUrl`: API Gateway endpoint (e.g., https://abc123.execute-api.us-east-1.amazonaws.com/prod)
- `ApiKey`: API key for authenticated requests

**SpendOptimoAgentCore:**
- `AgentRuntimeId`: Bedrock AgentCore runtime ID
- `GatewayId`: Agent gateway ID
- `CognitoUserPoolId`: Cognito User Pool ID
- `CognitoUserPoolClientId`: Client ID for authentication

**SpendOptimoWorkflowAgent:**
- `WorkflowAgentRuntimeId`: Workflow agent runtime ID
- `WorkflowGatewayId`: Workflow agent gateway ID

**SpendOptimoUi:**
- `WebUrl`: CloudFront URL for web interface
- `S3BucketName`: S3 bucket name for static assets

Retrieve outputs:
```bash
aws cloudformation describe-stacks \
  --stack-name SpendOptimoApi \
  --query 'Stacks[0].Outputs'
```

## Dependencies

### Node.js Packages
```json
{
  "aws-cdk-lib": "^2.100.0",
  "constructs": "^10.0.0",
  "@types/node": "^20.0.0",
  "typescript": "^5.0.0"
}
```

Install:
```bash
npm install
```

### Python Packages
Agent runtimes require Python dependencies (installed during Docker build):
- `boto3`: AWS SDK
- `requests`: HTTP client

## Useful CDK Commands

```bash
# List all stacks
npx cdk list

# Show CloudFormation template
npx cdk synth SpendOptimoApi

# Compare deployed vs. local changes
npx cdk diff SpendOptimoApi

# Deploy specific stack
npx cdk deploy SpendOptimoApi

# Deploy all stacks without approval prompts
npx cdk deploy --all --require-approval never

# Destroy all stacks (cleanup)
npx cdk destroy --all
```

## Bootstrap

First-time CDK setup in a new AWS account/region:

```bash
npx cdk bootstrap aws://ACCOUNT_ID/REGION
```

This creates:
- S3 bucket for CDK assets (Lambda code, Docker images)
- ECR repository for Docker images
- IAM roles for CloudFormation

## Cost Estimation

Approximate monthly costs for SpendOptimo:

| Service | Usage | Cost |
|---------|-------|------|
| Bedrock Nova Pro | 1M input + 200K output tokens | $3.50 |
| Bedrock Nova Lite | 10M input + 2M output tokens | $1.10 |
| Lambda (API) | 100K invocations, 512MB, 1s avg | $0.50 |
| Lambda (Agents) | Included in Bedrock AgentCore | $0 |
| API Gateway | 100K requests | $0.35 |
| CloudFront | 10GB transfer | $0.85 |
| S3 | 5GB storage | $0.12 |
| CloudWatch Logs | 5GB logs | $2.50 |
| **Total** | | **~$9/month** |

**Savings ROI**: If SpendOptimo saves $100/month in AWS costs, ROI is **11x**.

## Troubleshooting

### Issue: "CDK bootstrap required"
**Fix:** Run `npx cdk bootstrap`

### Issue: Docker build fails
**Fix:** Ensure Docker is running: `docker info`

### Issue: "Resource already exists"
**Fix:** Destroy and redeploy: `npx cdk destroy SpendOptimoApi && npx cdk deploy SpendOptimoApi`

### Issue: "Insufficient permissions"
**Fix:** Ensure your AWS credentials have Admin or PowerUser permissions

### Issue: Agent build takes too long (>10 minutes)
**Cause:** Slow Docker image build (installing Python packages)
**Fix:** Use `--no-cache` flag or pre-build base image

## Security Best Practices

1. **Least Privilege IAM**: Only grant necessary permissions
2. **Resource Tagging**: Tag all resources for cost tracking
3. **Enable CloudTrail**: Audit all API calls
4. **VPC Integration**: Run Lambdas in private subnets (for production)
5. **Secrets Manager**: Store sensitive config (not environment variables)
6. **WAF Protection**: Add AWS WAF to API Gateway (for production)

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
name: Deploy SpendOptimo
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 20
      - name: Install dependencies
        run: cd infra && npm install
      - name: Deploy to AWS
        run: cd infra && npx cdk deploy --all --require-approval never
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1
```

## Extending Infrastructure

### Adding New Stacks

1. Create new stack file: `lib/my-new-stack.ts`
```typescript
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

export class MyNewStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    
    // Add resources here
  }
}
```

2. Import in `bin/infra.ts`:
```typescript
import { MyNewStack } from '../lib/my-new-stack';
new MyNewStack(app, 'MyNewStack');
```

3. Deploy:
```bash
npx cdk deploy MyNewStack
```


