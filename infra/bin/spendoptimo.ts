#!/usr/bin/env node
import 'source-map-support/register';
import { App, Environment } from 'aws-cdk-lib';
import { IamRolesStack } from '../lib/iam-roles';
import { SageMakerStack } from '../lib/sagemaker-stack';
import { ApiStack } from '../lib/api-stack';
import { UiHostingStack } from '../lib/ui-hosting-stack';
import { AgentCoreStack } from '../lib/agentcore-stack';
import { WorkflowAgentStack } from '../lib/workflow-agent-stack';

const app = new App();

const env: Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

const iam = new IamRolesStack(app, 'SpendOptimoIam', { env });
const iamRefs = iam.outputs as { executorRoleArn: string; readOnlyRoleArn: string };

const sagemaker = new SageMakerStack(app, 'SpendOptimoSageMaker', { env });

const api = new ApiStack(app, 'SpendOptimoApi', { env });

const apiUrlFromCtx = app.node.tryGetContext('apiUrl');
if (!apiUrlFromCtx) {
  console.warn('WARNING: No --context apiUrl provided; SpendOptimoAgentCore requires an API Gateway URL.');
}

const agentCore = new AgentCoreStack(app, 'SpendOptimoAgentCore', {
  env,
  apiUrl: apiUrlFromCtx || 'https://example.execute-api.us-east-1.amazonaws.com/prod',
});

// Workflow Agent Runtime (separate from analysis agent, shares Cognito)
const workflowAgent = new WorkflowAgentStack(app, 'SpendOptimoWorkflowAgent', {
  env,
  apiUrl: apiUrlFromCtx || 'https://example.execute-api.us-east-1.amazonaws.com/prod',
  cognitoUserPoolId: agentCore.cognitoUserPoolId,
  cognitoUserPoolClientId: agentCore.cognitoUserPoolClientId,
});

const ui = new UiHostingStack(app, 'SpendOptimoUi', {
  env,
  apiUrl: api.api.url,
  apiKeyValue: api.apiKeyValue,
  cognitoDomain: agentCore.cognitoDomain,
  userPoolClientId: agentCore.cognitoUserPoolClientId,
  userPoolId: agentCore.cognitoUserPoolId,
});

agentCore.addDependency(api);
agentCore.addDependency(sagemaker);
workflowAgent.addDependency(agentCore); // Needs Cognito from agentCore
ui.addDependency(api);
ui.addDependency(agentCore);
