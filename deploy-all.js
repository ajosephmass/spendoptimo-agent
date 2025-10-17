#!/usr/bin/env node

/**
 * SpendOptimo - Complete Deployment Script
 * 
 * This script orchestrates the deployment of all SpendOptimo components
 * in the correct order with proper dependency management.
 * 
 * Usage: node deploy-all.js
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ANSI color codes for pretty output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
};

const log = {
  info: (msg) => console.log(`${colors.blue}ℹ${colors.reset} ${msg}`),
  success: (msg) => console.log(`${colors.green}✓${colors.reset} ${msg}`),
  warn: (msg) => console.log(`${colors.yellow}⚠${colors.reset} ${msg}`),
  error: (msg) => console.log(`${colors.red}✗${colors.reset} ${msg}`),
  step: (msg) => console.log(`\n${colors.bright}${colors.cyan}▶ ${msg}${colors.reset}\n`),
  divider: () => console.log(`${colors.cyan}${'─'.repeat(70)}${colors.reset}`),
};

// Helper to run commands with proper error handling
function run(command, options = {}) {
  try {
    const result = execSync(command, {
      stdio: options.silent ? 'pipe' : 'inherit',
      cwd: options.cwd || process.cwd(),
      encoding: 'utf-8',
    });
    return result;
  } catch (error) {
    if (!options.ignoreError) {
      log.error(`Command failed: ${command}`);
      throw error;
    }
    return null;
  }
}

// Check prerequisites
function checkPrerequisites() {
  log.step('Checking Prerequisites');
  
  const checks = [
    { cmd: 'node --version', name: 'Node.js', min: '18.0.0' },
    { cmd: 'python --version', name: 'Python', min: '3.11' },
    { cmd: 'aws --version', name: 'AWS CLI', min: '2.0' },
    { cmd: 'cdk --version', name: 'AWS CDK', min: '2.0' },
    { cmd: 'docker --version', name: 'Docker', optional: true },
  ];

  for (const check of checks) {
    try {
      const version = run(check.cmd, { silent: true });
      log.success(`${check.name}: ${version.trim()}`);
    } catch (error) {
      if (check.optional) {
        log.warn(`${check.name} not found (optional)`);
      } else {
        log.error(`${check.name} is required but not found`);
        process.exit(1);
      }
    }
  }
}

// Install dependencies
function installDependencies() {
  log.step('Installing Dependencies');
  
  // CDK/Infrastructure
  log.info('Installing CDK dependencies...');
  run('npm install', { cwd: 'infra' });
  log.success('CDK dependencies installed');
  
  // API Lambda (just validate requirements.txt exists)
  log.info('Validating API dependencies...');
  if (!fs.existsSync('api/requirements.txt')) {
    log.error('api/requirements.txt not found');
    process.exit(1);
  }
  log.success('API dependencies validated');
  
  // Webapp
  log.info('Installing webapp dependencies...');
  run('npm install', { cwd: 'webapp' });
  log.success('Webapp dependencies installed');
}

// Bootstrap CDK
function bootstrapCDK() {
  log.step('Bootstrapping AWS CDK');
  
  try {
    // Check if already bootstrapped
    run('aws cloudformation describe-stacks --stack-name CDKToolkit', 
        { silent: true, ignoreError: true });
    log.info('CDK already bootstrapped in this region');
  } catch {
    log.info('Bootstrapping CDK for the first time...');
    run('npx cdk bootstrap', { cwd: 'infra' });
    log.success('CDK bootstrapped successfully');
  }
}

// Deploy a single stack
function deployStack(stackName, description) {
  log.info(`Deploying ${stackName}...`);
  log.info(`Description: ${description}`);
  
  const startTime = Date.now();
  run(`npx cdk deploy ${stackName} --require-approval never`, { cwd: 'infra' });
  const duration = ((Date.now() - startTime) / 1000).toFixed(1);
  
  log.success(`${stackName} deployed successfully (${duration}s)`);
}

// Deploy all stacks
function deployStacks() {
  log.step('Deploying CloudFormation Stacks');
  
  const stacks = [
    {
      name: 'SpendOptimoIam',
      description: 'IAM roles and policies for read/execute permissions',
    },
    {
      name: 'SpendOptimoSageMaker',
      description: 'SageMaker endpoint for ML-based cost forecasting (optional)',
    },
    {
      name: 'SpendOptimoApi',
      description: 'API Gateway + Lambda orchestrator with Cost Explorer/Compute Optimizer integration',
    },
    {
      name: 'SpendOptimoAgentCore',
      description: 'Analysis Agent runtime (Nova Pro) - handles user queries and recommendations',
    },
    {
      name: 'SpendOptimoWorkflowAgent',
      description: 'Workflow Agent runtime (Nova Lite) - executes optimization workflows',
    },
    {
      name: 'SpendOptimoUi',
      description: 'CloudFront + S3 hosting for React web interface',
    },
  ];

  for (const stack of stacks) {
    try {
      deployStack(stack.name, stack.description);
    } catch (error) {
      log.error(`Failed to deploy ${stack.name}`);
      log.error('Deployment halted. Fix errors and re-run this script.');
      process.exit(1);
    }
  }
}

// Get stack outputs
function getStackOutputs() {
  log.step('Retrieving Deployment Outputs');
  
  const outputs = {};
  const stacks = [
    'SpendOptimoApi',
    'SpendOptimoAgentCore',
    'SpendOptimoWorkflowAgent',
    'SpendOptimoUi',
  ];

  for (const stackName of stacks) {
    try {
      const result = run(
        `aws cloudformation describe-stacks --stack-name ${stackName} --query "Stacks[0].Outputs" --output json`,
        { silent: true }
      );
      
      const stackOutputs = JSON.parse(result);
      outputs[stackName] = {};
      
      for (const output of stackOutputs || []) {
        outputs[stackName][output.OutputKey] = output.OutputValue;
      }
    } catch (error) {
      log.warn(`Could not retrieve outputs for ${stackName}`);
    }
  }
  
  return outputs;
}

// Deploy UI
function deployUI() {
  log.step('Deploying Web Interface');
  
  log.info('Building and uploading UI to S3...');
  run('node deploy-ui.js');
  log.success('UI deployed to CloudFront');
}

// Display summary
function displaySummary(outputs) {
  log.divider();
  log.step('🎉 Deployment Complete!');
  log.divider();
  
  console.log(`
${colors.bright}SpendOptimo is now live!${colors.reset}

${colors.cyan}📍 Important URLs:${colors.reset}
`);

  if (outputs.SpendOptimoUi?.WebUrl) {
    console.log(`  🌐 Web Interface:     ${colors.green}${outputs.SpendOptimoUi.WebUrl}${colors.reset}`);
  }
  
  if (outputs.SpendOptimoApi?.ApiUrl) {
    console.log(`  🔌 API Gateway:       ${outputs.SpendOptimoApi.ApiUrl}`);
  }
  
  if (outputs.SpendOptimoAgentCore?.CognitoDomain) {
    const domain = outputs.SpendOptimoAgentCore.CognitoDomain;
    const clientId = outputs.SpendOptimoAgentCore.CognitoUserPoolClientId;
    const redirectUri = outputs.SpendOptimoUi?.WebUrl || 'https://localhost:5173';
    
    console.log(`  🔐 Cognito Login:     https://${domain}/login?client_id=${clientId}&response_type=token&redirect_uri=${redirectUri}`);
  }

  console.log(`
${colors.cyan}🤖 Agent Runtimes:${colors.reset}
`);

  if (outputs.SpendOptimoAgentCore?.AgentRuntimeId) {
    console.log(`  🧠 Analysis Agent:    ${outputs.SpendOptimoAgentCore.AgentRuntimeId} (Nova Pro)`);
    console.log(`     Gateway ID:        ${outputs.SpendOptimoAgentCore.GatewayId || 'N/A'}`);
  }
  
  if (outputs.SpendOptimoWorkflowAgent?.WorkflowAgentRuntimeId) {
    console.log(`  ⚡ Workflow Agent:    ${outputs.SpendOptimoWorkflowAgent.WorkflowAgentRuntimeId} (Nova Lite)`);
    console.log(`     Gateway ID:        ${outputs.SpendOptimoWorkflowAgent.WorkflowGatewayId || 'N/A'}`);
  }

  console.log(`
${colors.cyan}🔑 Authentication:${colors.reset}
`);

  if (outputs.SpendOptimoAgentCore?.CognitoUserPoolId) {
    console.log(`  User Pool ID:         ${outputs.SpendOptimoAgentCore.CognitoUserPoolId}`);
  }
  
  if (outputs.SpendOptimoAgentCore?.CognitoUserPoolClientId) {
    console.log(`  Client ID:            ${outputs.SpendOptimoAgentCore.CognitoUserPoolClientId}`);
  }

  if (outputs.SpendOptimoApi?.ApiKey) {
    console.log(`  API Key:              ${outputs.SpendOptimoApi.ApiKey}`);
  }

  console.log(`
${colors.cyan}📝 Next Steps:${colors.reset}

  1. Visit the Web Interface URL above
  2. Click "Sign in with Cognito" and create an account
  3. Start chatting with SpendOptimo!

${colors.cyan}🧪 Try These Questions:${colors.reset}

  • "Get rightsizing recommendations for all my EC2 instances"
  • "Show me AWS spending trends for the last 30 days"
  • "Find cost anomalies in my account"
  • "What S3 buckets should use lifecycle policies?"
  • "Analyze my Lambda functions for cost optimization"

${colors.cyan}📚 Documentation:${colors.reset}

  • README.md           - Complete architecture and usage guide
  • CloudWatch Logs     - Agent execution logs and debugging
  • EC2 Console         - Verify workflow execution results

${colors.yellow}⚠ Important Notes:${colors.reset}

  • Enable Compute Optimizer in your AWS account for ML-based recommendations
  • Cost Explorer is required for spend analytics
  • AgentCore builds take 7-8 minutes (Docker image compilation)
  • Workflow execution runs in background (3-5 minutes typically)
  • Check CloudWatch Logs for detailed agent conversation traces

`);
  
  log.divider();
  console.log(`${colors.green}${colors.bright}Happy optimizing with SpendOptimo! 🚀${colors.reset}\n`);
}

// Main deployment flow
async function main() {
  console.log(`
${colors.bright}${colors.cyan}
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║               🚀 SpendOptimo Deployment Wizard                    ║
║                                                                   ║
║         Multi-Agent Autonomous FinOps Platform on AWS             ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
${colors.reset}
`);

  const startTime = Date.now();

  try {
    // Step 1: Check prerequisites
    checkPrerequisites();
    
    // Step 2: Install dependencies
    installDependencies();
    
    // Step 3: Bootstrap CDK
    bootstrapCDK();
    
    // Step 4: Deploy all stacks
    deployStacks();
    
    // Step 5: Deploy UI
    deployUI();
    
    // Step 6: Get outputs
    const outputs = getStackOutputs();
    
    // Step 7: Display summary
    const totalTime = ((Date.now() - startTime) / 60000).toFixed(1);
    displaySummary(outputs);
    
    log.success(`Total deployment time: ${totalTime} minutes`);
    
  } catch (error) {
    log.divider();
    log.error('Deployment failed');
    log.error(error.message);
    log.divider();
    process.exit(1);
  }
}

// Run deployment
main();


