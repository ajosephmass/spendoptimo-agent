# SpendOptimo – Multi-Agent Autonomous FinOps Platform

> **"What if your cloud costs optimized themselves?"**

SpendOptimo is a **multi-agent AI system** that doesn't just analyze your AWS costs—it **understands, recommends, and executes** optimizations autonomously. Built on AWS Bedrock AgentCore and Strands Agents SDK, it demonstrates intelligent cloud cost management using agentic workflows.

## 💼 The Vision

Traditional FinOps tools give you dashboards. **SpendOptimo gives you an AI co-pilot** that:

- **Analyzes** your AWS infrastructure using company policies, AWS Compute Optimizer, and cost trends
- **Converses** with you in natural language about optimization opportunities
- **Executes** approved recommendations autonomously across AWS Services
- **Verifies** every change it makes, ensuring safety and compliance

**The magic?** Two specialized AI agents working in tandem—one for intelligence, one for execution.

---

## ⚙️ Architecture

SpendOptimo uses a **separation of concerns** approach with two distinct AgentCore runtimes:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    [CloudFront] User Interface                      │
│                       React + Vite + Cognito                        │
│                                                                     │
│  • Conversational chat interface                                    │
│  • AWS Cognito authentication                                       │
│  • Dynamic action buttons                                           │
│  • Real-time workflow status                                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              [API Gateway + Lambda] Orchestrator                    │
│                    Python + Starlette + Mangum                      │
│                                                                     │
│  Routes:                                                            │
│  • POST /v1/chat        → Analysis Agent                            │
│  • GET  /v1/analyze     → Cost Explorer direct                      │
│  • POST /v1/automation  → Workflow Agent                            │
└─────────────┬─────────────────────────────┬─────────────────────────┘
              │                             │
              ▼                             ▼
┌─────────────────────────────┐   ┌─────────────────────────────────┐
│  [Bedrock] Analysis Agent   │   │  [Bedrock] Workflow Agent       │
│  AgentCore Runtime          │   │  AgentCore Runtime              │
│                             │   │                                 │
│  Runtime: SpendOptimo       │   │  Runtime: SpendOptimoWorkflow   │
│  Model: Amazon Nova Pro     │   │  Model: Amazon Nova Lite        │
│  Purpose: Intelligence      │   │  Purpose: Execution             │
│                             │   │                                 │
│  Tools:                     │   │  Tools:                         │
│  • analyze_aws_costs        │   │  • stop_ec2_instances           │
│  • get_cost_anomalies       │   │  • modify_ec2_instance_type     │
│  • get_rightsizing_recs     │   │  • start_ec2_instances          │
│  • execute_rightsizing      │   │  • apply_s3_lifecycle_policy    │
│                             │   │  • update_lambda_concurrency    │
│  Outputs:                   │   │  • modify_rds_instance          │
│  • Conversational insights  │   │  • resize_ebs_volumes           │
│  • Policy violations        │   │                                 │
│  • Recommendations JSON     │   │  Execution:                     │
│  • Dynamic action buttons   │   │  • Interprets recommendations   │
│                             │   │  • Performs AWS API calls       │
│                             │   │  • Validates changes            │
│                             │   │  • Reports results              │
└─────────────────────────────┘   └─────────────────────────────────┘
              │                             │
              ▼                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   [AWS Services] Evidence & Actuation               │
│                                                                     │
│  • Cost Explorer            • Compute Optimizer                     │
│  • CloudWatch               • EC2 / Lambda                          │
│  • Company Policies         • S3 / Lambda / EC2                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Two Agents?

**Analysis Agent (Nova Pro):**
- Higher intelligence for complex reasoning
- Understands company policies, cost trends, and optimization strategies
- Generates comprehensive, conversational recommendations
- Cost-effective for analysis (only runs when user asks questions)

**Workflow Agent (Nova Lite):**
- Lower latency, lower cost for repetitive execution tasks
- Receives structured recommendations and executes them
- Service-agnostic intelligence - can handle EC2, S3, Lambda, etc.
- Runs asynchronously in the background

This architecture achieves **separation of intelligence from execution**, enabling:
- **Scalability** - Analysis doesn't block execution
- **Cost optimization** - Right model for the right task
- **Flexibility** - Swap out models or add agents independently

---

## ✨ Key Features

### 1. Policy-Driven Intelligence

SpendOptimo enforces **company cost policies** defined in `agentcore_runtime/company_policies.py`:

```python
"EC2": {
    "allowed_instance_types": ["t3.micro", "t3.small", "t3.medium"],
    "disallowed_families": ["r5.*", "m5.*", "c5.*", "t2.*"],
    "max_instance_size": "medium",
    "policy_rationale": "Cost optimization - T3 instances provide best price/performance for our workloads"
}
```

**Immediate recommendations** without waiting for 14 days of data! The Analysis Agent also finds cost anomalies from AWS Cost Explorer, CloudWatch, and more.

### 2. Multi-Service Support

Using tools with the Workflow Agent, you can write rules and actions to perform the necessary optimization steps. For this starter kit, we have demonstrated the following capabilities:

- **EC2**: Instance type rightsizing, policy compliance
- **Lambda**: Memory and concurrency tuning
- **S3**: Lifecycle policies and storage class optimization

### 3. Autonomous Execution

The Workflow Agent can autonomously execute approved optimization recommendations, reducing manual effort and ensuring consistent application of cost policies.

**Example Scenario:**

1. Ask: _"What EC2 instances violate our cost policy?"_
2. Agent analyzes and responds with violations
3. Click **"Execute Recommendations"** button in chat
4. Workflow Agent autonomously:
   - Stops instances
   - Modifies instance types
   - Restarts instances
   - Verifies changes

### 4. Smart Recommendations

The Analysis Agent combines:
- **Company cost policies** (primary source)
- **AWS Compute Optimizer** (ML-based insights)
- **Cost Explorer trends** (historical spend patterns)
- **CloudWatch metrics** (actual utilization data)

### 5. Secure by Default

- **Cognito authentication** for all API calls
- **IAM least-privilege** roles for each component
- **Approval-based workflow** - no changes without user consent
- **Audit trail** in CloudWatch Logs

---

## 📂 Project Structure

```
spendoptimo/
│
├── infra/                          # AWS CDK Infrastructure (TypeScript)
│   ├── bin/
│   │   └── spendoptimo.ts         # CDK app entry point
│   ├── lib/
│   │   ├── iam-stack.ts           # IAM roles and policies
│   │   ├── sagemaker-stack.ts     # ML endpoint (optional)
│   │   ├── api-stack.ts           # API Gateway + Lambda
│   │   ├── agentcore-stack.ts     # Analysis Agent runtime
│   │   ├── workflow-agent-stack.ts # Workflow Agent runtime
│   │   └── ui-stack.ts            # CloudFront + S3 hosting
│   └── custom-resources/
│       └── agentcore_provisioner/ # AgentCore provisioning Lambda
│
├── agentcore_runtime/             # Analysis Agent Runtime
│   ├── app.py                     # Agent definition + tools
│   ├── company_policies.py        # Multi-service cost policies
│   ├── Dockerfile                 # Container for AgentCore
│   └── requirements.txt           # Python dependencies
│
├── workflow_runtime/              # Workflow Agent Runtime
│   ├── app.py                     # Execution agent + AWS tools
│   ├── Dockerfile                 # Container for AgentCore
│   └── requirements.txt           # Python dependencies
│
├── api/                           # API Lambda (Orchestrator)
│   ├── src/
│   │   ├── app.py                 # Starlette app with routes
│   │   ├── agentcore/
│   │   │   └── client.py          # AgentCore gateway client
│   │   ├── automation/
│   │   │   ├── strands_runner.py  # Strands SDK wrapper
│   │   │   └── strands_workflows.py # Workflow step definitions
│   │   └── services/
│   │       ├── cost_explorer.py   # Cost analysis logic
│   │       └── recommendations.py # Compute Optimizer integration
│   ├── Dockerfile                 # API Lambda container
│   └── requirements.txt
│
├── webapp/                        # React Frontend
│   ├── src/
│   │   └── main.js                # Chat UI + API integration
│   ├── index.html
│   └── package.json
│
├── deploy-ui.js                   # UI deployment script
└── create-test-instance.js        # Helper to create test instances
```

---

## 🔧 Technology Stack

### Core Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Analysis Agent** | AWS Bedrock AgentCore + Amazon Nova Pro | High-intelligence reasoning for cost analysis |
| **Workflow Agent** | AWS Bedrock AgentCore + Amazon Nova Lite | Lightweight execution engine |
| **Orchestration** | AWS Strands Agents SDK | Multi-step workflow coordination |
| **API Layer** | Python (Starlette + Mangum) | Lambda-based REST API |
| **Frontend** | React + Vite | Modern, fast web interface |
| **Infrastructure** | AWS CDK v2 (TypeScript) | Infrastructure as code |
| **Authentication** | Amazon Cognito | User identity and JWT tokens |
| **Storage** | CloudFront + S3 | Static site hosting |
| **Container Registry** | Amazon ECR | Docker image storage for Lambda |

### AWS Services Used

- **Bedrock AgentCore** - Agent runtimes and orchestration
- **Cost Explorer** - Historical cost data and anomalies
- **Compute Optimizer** - ML-based rightsizing recommendations
- **CloudWatch** - Metrics and logging
- **EC2, RDS, Lambda, S3, EBS** - Resource optimization targets
- **IAM** - Security and permissions
- **API Gateway** - HTTP endpoints
- **Lambda** - Serverless compute
- **Systems Manager (SSM)** - Parameter store for configuration

---

## 🚀 Quick Start Deployment

### Prerequisites

```bash
# Required tools
node --version        # v18 or higher
python --version      # 3.11 or higher
aws --version         # AWS CLI v2
cdk --version         # AWS CDK v2

# Install CDK globally if needed
npm install -g aws-cdk

# Configure AWS credentials
aws configure
```

### One-Command Deployment

We've created a comprehensive deployment script that handles everything:

```bash
node deploy-all.js
```

This script will:
1. ✅ Bootstrap CDK (if needed)
2. ✅ Deploy IAM roles
3. ✅ Deploy SageMaker endpoint (optional)
4. ✅ Deploy API stack with Lambda functions
5. ✅ Deploy Analysis Agent (AgentCore runtime)
6. ✅ Deploy Workflow Agent (AgentCore runtime)
7. ✅ Deploy UI to CloudFront
8. ✅ Display all endpoints and credentials

**Estimated deployment time:** 15-20 minutes (mostly building Docker images)

### Manual Deployment (Step-by-Step)

If you prefer manual control:

```bash
# 1. Install dependencies
cd infra && npm install && cd ..
cd api && pip install -r requirements.txt && cd ..
cd webapp && npm install && cd ..

# 2. Bootstrap CDK (once per account/region)
cd infra
npx cdk bootstrap

# 3. Deploy stacks in order
npx cdk deploy SpendOptimoIam --require-approval never
npx cdk deploy SpendOptimoSageMaker --require-approval never
npx cdk deploy SpendOptimoApi --require-approval never
npx cdk deploy SpendOptimoAgentCore --require-approval never
npx cdk deploy SpendOptimoWorkflowAgent --require-approval never
npx cdk deploy SpendOptimoUi --require-approval never

# 4. Deploy frontend
cd ..
node deploy-ui.js
```

---

## 💻 How to Use

### 1. Access the UI

Navigate to your CloudFront URL (output from deployment):
```
https://d293f08cklhjup.cloudfront.net
```

### 2. Authenticate

1. Click **"Sign in with Cognito"**
2. Create an account or sign in
3. Your ID token is automatically saved in the session

### 3. Ask Questions

Try these conversational queries:

**Cost Analysis:**
```
"Show me my AWS spending trends for the last 30 days"
"Find cost anomalies in my account"
"What's causing my EC2 costs to spike?"
```

**Optimization:**
```
"Get rightsizing recommendations for all my EC2 instances"
"What resources violate our company cost policy?"
"Analyze my S3 buckets for cost savings"
"Are my Lambda functions over-provisioned?"
```

**Multi-Service:**
```
"Give me all cost optimization opportunities across EC2, RDS, and Lambda"
"What are my top 5 cost savings recommendations?"
```

### 4. Execute Recommendations

1. Agent responds with detailed analysis
2. **"Execute Recommendations"** button appears in chat (only if recommendations exist)
3. Click button → Workflow Agent executes changes in background
4. Check EC2 console to see instances being optimized (3-5 minutes)

---

## 🔄 How It Works

### The Recommendation Flow

```mermaid
sequenceDiagram
    User->>Analysis Agent: "Get EC2 rightsizing recommendations"
    Analysis Agent->>EC2: List running instances
    Analysis Agent->>Company Policies: Check policy compliance
    Analysis Agent->>Compute Optimizer: Get ML recommendations
    Analysis Agent->>Cost Explorer: Analyze spending trends
    Analysis Agent->>User: Detailed analysis + [Execute Button]
    User->>Workflow Agent: Clicks "Execute Recommendations"
    Workflow Agent->>Workflow Agent: Parse recommendations JSON
    Workflow Agent->>EC2: Stop instance i-xxx
    Workflow Agent->>EC2: Modify instance type
    Workflow Agent->>EC2: Start instance i-xxx
    Workflow Agent->>EC2: Verify new instance type
    Workflow Agent->>User: "✅ Workflow completed successfully"
```

### The Intelligence

**Analysis Agent System Prompt** (excerpt):
```
"When users ask about rightsizing, you MUST:
1. Use get_rightsizing_recommendations to check company policies
2. Write a CONVERSATIONAL, well-explained response
3. Include resource inventory, policy violations, and estimated savings
4. End with [RECOMMENDATIONS_JSON]...[/RECOMMENDATIONS_JSON] and [BUTTON:Execute Recommendations]"
```

**Workflow Agent System Prompt** (excerpt):
```
"You receive recommendations as JSON. Your job:
1. Parse and understand what needs to be done
2. Use your tools to execute changes (EC2, S3, Lambda)
3. Verify each change was successful
4. Report results in natural language"
```

---

## 📋 Company Cost Policies

Define your optimization rules in `agentcore_runtime/company_policies.py`:

```python
COMPANY_COST_POLICIES = {
    "EC2": {
        "allowed_instance_types": ["t3.micro", "t3.small", "t3.medium"],
        "disallowed_families": ["r5.*", "m5.*", "c5.*", "t2.*"],
        "max_instance_size": "medium",
        "policy_rationale": "T3 instances provide best price/performance",
        "estimated_savings_per_violation": "$50.00/month"
    },
    "RDS": {
        "allowed_instance_classes": ["db.t3.*", "db.t4g.*"],
        "disallowed_engines_for_large_instances": ["aurora-postgresql", "aurora-mysql"],
        "max_allocated_storage_gb": 500
    },
    "Lambda": {
        "max_memory_mb": 1024,
        "max_timeout_seconds": 300,
        "reserved_concurrency_policy": "discouraged"
    },
    "S3": {
        "lifecycle_policy_required": True,
        "disallowed_storage_classes": ["GLACIER_IR", "DEEP_ARCHIVE"],
        "transition_to_ia_after_days": 90
    },
    "EBS": {
        "allowed_volume_types": ["gp3"],
        "disallowed_volume_types": ["io1", "io2"],
        "max_volume_size_gb": 500
    }
}
```

The agent **automatically checks these policies** and provides immediate recommendations—no metrics needed!

---

## ⚙️ Configuration

### Enable AWS Services

**1. Compute Optimizer** (required for ML-based recommendations):
  ```bash
  aws compute-optimizer update-enrollment-status \
    --status Active \
    --include-member-accounts \
    --region us-east-1
  ```

**2. Cost Explorer** (automatically enabled, but check):
```bash
aws ce get-cost-and-usage \
  --time-period Start=2025-01-01,End=2025-01-02 \
  --granularity DAILY \
  --metrics BlendedCost
```

### Environment Variables

After deployment, these are automatically configured in SSM Parameter Store:

| Parameter | Description |
|-----------|-------------|
| `/spendoptimo/agentcore/id` | Analysis Agent ID |
| `/spendoptimo/agentcore/alias` | Analysis Agent alias (prod) |
| `/spendoptimo/agentcore/invoke-arn` | Analysis Agent endpoint ARN |
| `/spendoptimo/workflow-agent/id` | Workflow Agent ID |
| `/spendoptimo/workflow-agent/invoke-arn` | Workflow Agent endpoint ARN |

---

## ✅ Testing & Validation

### Create a Test Instance

Run the helper script to create a policy-violating instance:

```bash
node create-test-instance.js
```

This creates an `r5.large` instance (violates policy → should recommend `t3.medium`).

### Test the Full Flow

1. **Ask**: _"Get rightsizing recommendations for all my EC2 instances"_
   
   **Expected**: Agent finds the `r5.large` violation and recommends `t3.medium`

2. **Click**: "Execute Recommendations" button

   **Expected**: Workflow starts, instance is stopped → modified → restarted

3. **Verify**: Check EC2 console - instance type changed to `t3.medium`

4. **Ask again**: _"Get rightsizing recommendations for all my EC2 instances"_

   **Expected**: Agent says "All instances are compliant" with **NO button**

### Sample Questions for Testing

**EC2:**
```
"Show me all EC2 instances that violate company policy"
"What's the estimated savings from rightsizing my instances?"
"Get EC2 optimization recommendations"
```

**S3:**
```
"Analyze my S3 buckets for cost optimization"
"Which S3 buckets should use lifecycle policies?"
```

**Lambda:**
```
"Optimize my Lambda functions for cost"
"Which Lambda functions are over-provisioned?"
```

**Multi-Service:**
```
"Give me all cost optimization recommendations"
"What are my top cost savings opportunities?"
```

---

## 🔐 Authentication Flow

```
1. User visits CloudFront URL
   ↓
2. Clicks "Sign in with Cognito"
   ↓
3. Cognito Hosted UI (OAuth2)
   ↓
4. Returns ID token in URL fragment
   ↓
5. Frontend extracts and stores token
   ↓
6. All API calls include: Authorization: Bearer <token>
   ↓
7. API Lambda validates token with Cognito
   ↓
8. Agents receive authenticated context
```

**Both agents share the same Cognito User Pool** for seamless authentication.

---

## 🤖 Agent Details

### Analysis Agent (SpendOptimo)

**Location:** `agentcore_runtime/app.py`

**Model:** `amazon.nova-pro-v1:0`

**Tools:**
- `analyze_aws_costs` - Cost Explorer trends and anomalies
- `get_cost_anomalies` - Detect spending spikes
- `get_rightsizing_recommendations` - Policy + Optimizer insights
- `execute_rightsizing_workflow` - Trigger Workflow Agent

**Response Format:**
```json
{
  "brand": "SpendOptimo",
  "message": "Conversational analysis with markdown formatting...",
  "button": {
    "text": "Execute Recommendations",
    "action": "rightsizing_workflow",
    "recommendations": [
      {
        "resource_type": "EC2",
        "instance_id": "i-xxx",
        "current_instance_type": "r5.large",
        "recommended_instance_type": "t3.medium",
        "estimated_monthly_savings": "$50.00"
      }
    ]
  }
}
```

### Workflow Agent (SpendOptimoWorkflow)

**Location:** `workflow_runtime/app.py`

**Model:** `amazon.nova-lite-v1:0`

**Tools:**
- `stop_ec2_instances` - Gracefully stop instances
- `modify_ec2_instance_type` - Change instance type
- `start_ec2_instances` - Restart instances
- `verify_ec2_instance_type` - Confirm changes
- `apply_s3_lifecycle_policy` - Update S3 lifecycle
- `update_lambda_concurrency` - Adjust Lambda settings

**Execution Pattern:**
```
Input: Recommendations JSON array
  ↓
LLM interprets what needs to be done
  ↓
Calls appropriate tools (ec2_stop, ec2_modify, etc.)
  ↓
Verifies changes were applied
  ↓
Returns natural language summary
```

---

## 📊 Monitoring & Debugging

### CloudWatch Logs

**Analysis Agent Logs:**
```
/aws/bedrock-agentcore/SpendOptimo-bFMEwZGAVW
```

**Workflow Agent Logs:**
```
/aws/bedrock-agentcore/SpendOptimoWorkflow-7lNTl14agv
```

**API Lambda Logs:**
```
/aws/lambda/SpendOptimoApi-SpendOptimoApiFn-*
```

### Useful Log Queries

**Find workflow executions:**
```
fields @timestamp, @message
| filter @message like /Workflow execution/
| sort @timestamp desc
```

**Track recommendation processing:**
```
fields @timestamp, @message
| filter @message like /recommendations/
| sort @timestamp desc
```

---

## ⚡ Workflow Execution Details

### Synchronous vs. Asynchronous

**Current Implementation:**

1. **User clicks button** → Frontend calls `/v1/automation`
2. **API Lambda** → Invokes itself asynchronously with recommendations
3. **API Lambda (async)** → Calls Workflow Agent
4. **API Lambda** → Returns `202 Accepted` immediately to frontend
5. **Workflow Agent** → Executes in background (3-5 minutes)

**Benefit:** No timeout errors, fast UI response

**Trade-off:** Generic static message, not intelligent Workflow Agent response

### Timeout Behavior

- **API Gateway timeout:** 29 seconds (hard limit)
- **Lambda timeout:** 300 seconds (5 minutes)
- **Workflow execution time:** 3-5 minutes typically

If workflow takes > 29 seconds, API Gateway returns `504 Gateway Timeout`, but:
- ✅ **Lambda keeps running** in the background
- ✅ **Changes still get applied** to AWS resources
- ✅ **Results logged** to CloudWatch

---

## 🔒 IAM Permissions

### Analysis Agent Role

```yaml
Permissions:
  - cost-explorer:GetCostAndUsage
  - cost-explorer:GetAnomalies
  - compute-optimizer:GetEC2InstanceRecommendations
  - ec2:DescribeInstances
  - cloudwatch:GetMetricStatistics
  - ssm:GetParameter
```

### Workflow Agent Role

```yaml
Permissions:
  - ec2:StopInstances
  - ec2:StartInstances
  - ec2:ModifyInstanceAttribute
  - s3:PutLifecycleConfiguration
  - lambda:UpdateFunctionConfiguration
  - rds:ModifyDBInstance
  - ec2:ModifyVolume
  - cloudwatch:GetMetricStatistics
```

### API Lambda Role

```yaml
Permissions:
  - bedrock-agentcore:InvokeAgentRuntime
  - ssm:GetParameter
  - lambda:InvokeFunction (self-invoke for async)
```

---

## 🔌 Extending SpendOptimo

### Adding a New Service (e.g., DynamoDB)

**1. Define Policy** (`agentcore_runtime/company_policies.py`):
```python
"DynamoDB": {
    "on_demand_vs_provisioned": "on_demand_preferred",
    "max_provisioned_rcu": 100,
    "max_provisioned_wcu": 100
}
```

**2. Add Analysis Tool** (`agentcore_runtime/app.py`):
```python
@tool
def get_dynamodb_recommendations() -> Dict[str, Any]:
    """Get DynamoDB cost optimization recommendations."""
    # Check tables against policy
    # Return recommendations
```

**3. Add Workflow Tool** (`workflow_runtime/app.py`):
```python
@tool
def update_dynamodb_capacity(table_name: str, mode: str) -> Dict[str, Any]:
    """Switch DynamoDB table to on-demand billing."""
    # Update table billing mode
    # Verify change
```

**4. Update System Prompts** - Teach both agents about DynamoDB

**5. Deploy** - Both agents auto-reload with new capabilities

---

## 💰 Cost Optimization Strategies

SpendOptimo implements industry best practices:

### 1. **Policy-First Approach**
- Define guardrails upfront (instance types, sizes, families)
- Get **immediate recommendations** without historical data
- Enforce consistency across teams

### 2. **Multi-Source Evidence**
- Company policies (organizational rules)
- Compute Optimizer (AWS ML insights)
- CloudWatch metrics (actual usage)
- Cost Explorer (spending patterns)

### 3. **Safe Automation**
- **Approval required** before any changes
- **Graceful stop** → modify → start sequence
- **Verification step** after each change
- **CloudWatch logging** for audit trail

### 4. **Service-Agnostic Design**
- Same workflow pattern for EC2, Lambda, S3
- Workflow Agent interprets any recommendation type
- Easy to extend to new services

---

## 📚 Learning Resources

### Understanding the Code

**Start here:**
1. `agentcore_runtime/app.py` - Analysis Agent definition
2. `workflow_runtime/app.py` - Workflow Agent definition
3. `api/src/app.py` - API orchestration logic
4. `webapp/src/main.js` - Frontend chat implementation

**Key concepts:**
- **AgentCore Entrypoints**: Functions decorated with `@bedrock_agentcore_app.entrypoint()`
- **Strands Tools**: Functions decorated with `@tool` that agents can invoke
- **Button Markers**: Special strings in responses that trigger UI buttons
- **Async Workflows**: Lambda self-invocation pattern for long-running tasks

### AWS Documentation

- [Bedrock AgentCore Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-agentcore.html)
- [Strands Agents SDK](https://docs.aws.amazon.com/bedrock/latest/userguide/agents-strands.html)
- [Cost Explorer API](https://docs.aws.amazon.com/cost-management/latest/APIReference/)
- [Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/)

---

## 🔍 Troubleshooting

### Common Issues

**1. "No response generated"**
- **Cause:** AgentCore runtime not deployed or failed
- **Fix:** Check CloudFormation stack status, redeploy AgentCore

**2. "504 Gateway Timeout" when executing workflow**
- **Cause:** Workflow takes > 29 seconds (expected behavior)
- **Status:** Workflow still runs in background, check EC2 console

**3. Button doesn't appear**
- **Cause:** Agent's response doesn't contain button marker
- **Fix:** Check CloudWatch logs for Analysis Agent, ensure `[BUTTON:Execute Recommendations]` is in response

**4. "Access Denied" errors**
- **Cause:** Missing IAM permissions
- **Fix:** Check agent role has required permissions for the service

**5. Circular dependency during deployment**
- **Cause:** Lambda trying to reference itself
- **Fix:** Use wildcard ARN pattern instead of `functionArn`

### Debug Mode

View full responses in the UI by clicking "Show Details" under each message.

---

## 🎯 Future Enhancements

### Recommended Roadmap

**Phase 1: Enhanced Intelligence** (Current)
- ✅ Multi-agent architecture
- ✅ Policy-based recommendations
- ✅ EC2 rightsizing automation

**Phase 2: Additional Services**
- ⏳ RDS database instance optimization (code available as reference in `agentcore_runtime/app.py`)
- ⏳ EBS volume type and unattached volume cleanup (code available as reference in `agentcore_runtime/app.py`)

**Phase 3: Advanced Features**
- ⏰ Scheduled optimizations (nightly shutdowns)
- 📊 Workflow execution history (DynamoDB table)
- 🔔 SNS notifications for completed workflows
- 📈 Cost savings dashboard
- 🔄 Real-time progress updates (WebSocket or polling)

**Phase 4: Enterprise Features**
- 👥 Multi-user support with RBAC
- 🏢 Multi-account optimization (AWS Organizations)
- 📝 Approval workflows (manager sign-off)
- 📊 Executive reporting and KPIs

---

## 💡 Why SpendOptimo Matters

### The Problem with Traditional FinOps

- ❌ **Dashboards show data, not insights** - "Here's your spend... now what?"
- ❌ **Recommendations require expertise** - DevOps teams must interpret and act
- ❌ **Manual execution is error-prone** - Console clicking leads to mistakes
- ❌ **Policies are informal** - "We should use t3 instances" = tribal knowledge

### The SpendOptimo Solution

- ✅ **Conversational intelligence** - Ask questions, get answers
- ✅ **Automated execution** - One click to optimize
- ✅ **Policy enforcement** - Codified rules, not suggestions
- ✅ **Multi-service coverage** - EC2, S3, Lambda, etc
- ✅ **Autonomous agents** - Runs 24/7, never sleeps

### Real-World Impact

**Before SpendOptimo:**
- DevOps engineer spends 4 hours/week reviewing cost reports
- Manual rightsizing of 20 instances: 2 hours
- Policy violations discovered weeks later
- **Total time:** 6+ hours/week

**After SpendOptimo:**
- Ask agent: "What should I optimize?" - 30 seconds
- Click "Execute Recommendations" - 5 seconds
- Workflow runs in background - 0 engineer time
- **Total time:** 35 seconds/week

**Savings: 35 hours/month of engineering time** 🎉

---

## 🤝 Contributing

This is a reference implementation showcasing:
- Multi-agent architecture patterns
- AgentCore + Strands integration
- Policy-driven automation
- Service-agnostic workflow design

**Ideas for contributions:**
- Additional AWS service integrations (EKS, ECS, ElastiCache)
- Enhanced UI features (charts, graphs, history)
- Workflow execution tracking (DynamoDB state management)
- Cost allocation tag analysis
- Budget threshold automation

---

## 📄 License

MIT License - See LICENSE file

---

<div align="center">

**SpendOptimo** - *Where AI meets FinOps*


</div>
