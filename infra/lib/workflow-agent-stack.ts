import { Stack, StackProps, CfnOutput, Duration, CustomResource } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as path from 'path';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as ssm from 'aws-cdk-lib/aws-ssm';
// import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as s3assets from 'aws-cdk-lib/aws-s3-assets';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as fs from 'fs';
import { execSync } from 'child_process';

export interface WorkflowAgentProps extends StackProps {
  apiUrl: string;
  apiKeyValue?: string;
  cognitoUserPoolId: string;
  cognitoUserPoolClientId: string;
}

export class WorkflowAgentStack extends Stack {
  constructor(scope: Construct, id: string, props: WorkflowAgentProps) {
    super(scope, id, props);

    const agentRole = new iam.Role(this, 'WorkflowAgentRole', {
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('bedrock.amazonaws.com'),
        new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      ),
    });

    const provisionerPath = path.join(process.cwd(), 'custom-resources/agentcore_provisioner');
    const repoRootFromProvisioner = path.resolve(provisionerPath, '../../../');
    const manifestPath = path.join(repoRootFromProvisioner, 'agentcore/gateway.manifest.json');
    const onEvent = new lambda.Function(this, 'WorkflowAgentProvisionerFn', {
      code: lambda.Code.fromAsset(provisionerPath, {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          volumes: [
            {
              hostPath: path.dirname(manifestPath),
              containerPath: '/ext/agentcore',
            },
          ],
          command: [
            'bash', '-lc',
            [
              'python -m pip install -r /asset-input/requirements.txt -t /asset-output',
              '&&',
              'cp handler.py /asset-output/',
              '&&',
              'cp /ext/agentcore/gateway.manifest.json /asset-output/gateway.manifest.json',
            ].join(' '),
          ],
          // Prefer local bundling to avoid Docker requirement
          local: {
            tryBundle: (outputDir: string) => {
              try {
                const reqFile = path.join(provisionerPath, 'requirements.txt');
                const hasReq = fs.existsSync(reqFile) && fs.readFileSync(reqFile, 'utf-8').trim().length > 0;
                if (hasReq) {
                  execSync(`python -m pip install -r "${reqFile}" -t "${outputDir}"`, { stdio: 'inherit' });
                }
                fs.copyFileSync(path.join(provisionerPath, 'handler.py'), path.join(outputDir, 'handler.py'));
                fs.copyFileSync(manifestPath, path.join(outputDir, 'gateway.manifest.json'));
                return true;
              } catch (e) {
                console.warn('Local bundling failed, will fall back to Docker bundling.', e);
                return false;
              }
            },
          },
        },
      }),
      handler: 'handler.handler',
      runtime: lambda.Runtime.PYTHON_3_12,
      // Preparing an agent can take several minutes; allow ample time
      timeout: Duration.minutes(10),
    });

    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        // AgentCore control plane permissions (service prefix is bedrock-agentcore)
        'bedrock-agentcore:CreateGateway',
        'bedrock-agentcore:GetGateway',
        'bedrock-agentcore:UpdateGateway',
        'bedrock-agentcore:ListGateways',
        'bedrock-agentcore:CreateGatewayTarget',
        'bedrock-agentcore:ListGatewayTargets',
        'bedrock-agentcore:CreateAgentRuntime',
        'bedrock-agentcore:UpdateAgentRuntime',
        'bedrock-agentcore:ListAgentRuntimes',
        'bedrock-agentcore:CreateApiKeyCredentialProvider',
        'bedrock-agentcore:GetApiKeyCredentialProvider',
        'bedrock-agentcore:ListApiKeyCredentialProviders',
        // Workload identity used by Gateways/Targets
        'bedrock-agentcore:CreateWorkloadIdentity',
        'bedrock-agentcore:GetWorkloadIdentity',
        'bedrock-agentcore:ListWorkloadIdentities',
        'bedrock-agentcore:GetWorkloadIdentityDirectory',
        // Token vault access required by credential providers
        'bedrock-agentcore:GetTokenVault',
        'bedrock-agentcore:CreateTokenVault',
        'bedrock-agentcore:SetTokenVaultCMK',
      ],
      resources: ['*'],
    }));

    // As AgentCore evolves, unblock provisioning by allowing broader control-plane actions.
    // If you prefer least-privilege, we can refine once the exact set stabilizes in your account.
    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:*'],
      resources: ['*'],
    }));

    // Secrets Manager permissions needed when AgentCore stores API keys in your account's token vault
    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'secretsmanager:CreateSecret',
        'secretsmanager:PutSecretValue',
        'secretsmanager:TagResource',
        'secretsmanager:DescribeSecret',
        'secretsmanager:GetSecretValue',
        'secretsmanager:UpdateSecret',
        'secretsmanager:DeleteSecret',
      ],
      resources: ['*'],
    }));

    // Allow the provisioner to pass the dedicated Agent role to Bedrock
    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: ['iam:PassRole'],
      resources: [agentRole.roleArn],
      conditions: {
        StringEquals: { 'iam:PassedToService': ['bedrock.amazonaws.com', 'bedrock-agentcore.amazonaws.com'] },
      },
    }));
    // Allow creating the Bedrock AgentCore service-linked role programmatically
    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: ['iam:CreateServiceLinkedRole'],
      resources: ['*'],
    }));

    // Create a dedicated ECR repo for the runtime image and grant pull to AgentCore role
    const runtimeRepo = new ecr.Repository(this, 'WorkflowRuntimeRepo', {
      repositoryName: `spendoptimo-workflow-runtime-${this.account}-${this.region}`,
      imageScanOnPush: true,
    });
    agentRole.addToPolicy(new iam.PolicyStatement({ actions: ['ecr:GetAuthorizationToken'], resources: ['*'] }));
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ecr:BatchCheckLayerAvailability','ecr:GetDownloadUrlForLayer','ecr:BatchGetImage'],
      resources: [runtimeRepo.repositoryArn],
    }));

    // Grant CloudWatch logging permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'logs:CreateLogGroup',
        'logs:CreateLogStream',
        'logs:PutLogEvents',
        'logs:DescribeLogGroups',
        'logs:DescribeLogStreams'
      ],
      resources: ['*'],
    }));

    // Grant X-Ray tracing permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'xray:PutTraceSegments',
        'xray:PutTelemetryRecords'
      ],
      resources: ['*'],
    }));

    // Grant Bedrock permissions for Nova model
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'bedrock:InvokeModel',
        'bedrock:InvokeModelWithResponseStream',
        'bedrock:Converse',
        'bedrock:ConverseStream'
      ],
      resources: [
        'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0',
        'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
        'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0'
      ],
    }));

    // Grant EC2 modification permissions for rightsizing workflow
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'ec2:DescribeInstances',
        'ec2:DescribeVolumes',
        'ec2:DescribeSnapshots',
        'ec2:StopInstances',
        'ec2:StartInstances',
        'ec2:ModifyInstanceAttribute',
        'ec2:ModifyVolume',
        'cloudwatch:GetMetricStatistics',
        'cloudwatch:PutMetricData'
      ],
      resources: ['*'],
    }));

    // Grant S3 lifecycle management permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        's3:ListAllMyBuckets',
        's3:GetBucketLocation',
        's3:GetLifecycleConfiguration',
        's3:PutLifecycleConfiguration'
      ],
      resources: ['*'],
    }));

    // Grant Lambda concurrency management permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'lambda:ListFunctions',
        'lambda:GetFunctionConcurrency',
        'lambda:PutFunctionConcurrency',
        'lambda:UpdateFunctionConfiguration'
      ],
      resources: ['*'],
    }));

    // Grant RDS modification permissions
    agentRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'rds:DescribeDBInstances',
        'rds:DescribeDBClusters',
        'rds:ModifyDBInstance'
      ],
      resources: ['*'],
    }));

    const provider = new cr.Provider(this, 'WorkflowAgentProvider', {
      onEventHandler: onEvent,
    });


    // Package runtime source and build ARM64 image in CodeBuild (no local Docker required)
    const runtimeSrc = new s3assets.Asset(this, 'WorkflowRuntimeSrc', {
      path: path.join(__dirname, '../../workflow_runtime'),
    });
    const project = new codebuild.Project(this, 'WorkflowRuntimeBuild', {
      environment: { buildImage: codebuild.LinuxBuildImage.AMAZON_LINUX_2_5, privileged: true },
      environmentVariables: {
        REPO_URI: { value: runtimeRepo.repositoryUri },
        IMAGE_TAG: { value: runtimeSrc.assetHash },
        SRC_BUCKET: { value: runtimeSrc.s3BucketName },
        SRC_KEY: { value: runtimeSrc.s3ObjectKey },
        AWS_REGION: { value: this.region },
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          pre_build: {
            commands: [
              'echo Logging into ECR',
              'aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REPO_URI',
              'docker buildx create --use --name xbuilder || true',
              'aws s3 cp s3://$SRC_BUCKET/$SRC_KEY src.zip',
              'mkdir -p src && unzip -q src.zip -d src && cd src',
            ],
          },
          build: {
            commands: [
              'docker buildx build --platform linux/arm64 -t $REPO_URI:$IMAGE_TAG --push .',
            ],
          },
        },
        artifacts: { files: ['**/*'], 'discard-paths': 'yes' },
      }),
    });
    runtimeSrc.grantRead(project);
    runtimeRepo.grantPullPush(project);
    // Allow provisioner to start and poll CodeBuild
    onEvent.addToRolePolicy(new iam.PolicyStatement({
      actions: ['codebuild:StartBuild','codebuild:BatchGetBuilds'],
      resources: [project.projectArn],
    }));

    // Reuse the existing Cognito user pool from the analysis agent
    const userPool = cognito.UserPool.fromUserPoolId(this, 'ExistingUserPool', props.cognitoUserPoolId);
    const userPoolClient = cognito.UserPoolClient.fromUserPoolClientId(this, 'ExistingUserPoolClient', props.cognitoUserPoolClientId);
    const discoveryUrl = `https://cognito-idp.${this.region}.amazonaws.com/${props.cognitoUserPoolId}/.well-known/openid-configuration`;

    const resource = new CustomResource(this, 'WorkflowAgentResource', {
      serviceToken: provider.serviceToken,
      properties: {
        AgentName: 'SpendOptimoWorkflow',
        SystemPrompt: 'You are SpendOptimoWorkflow, an execution agent that applies cost optimization recommendations.',
        InferenceModel: 'amazon.nova-lite-v1:0',
        AgentRoleArn: agentRole.roleArn,
        ApiUrl: props.apiUrl,
        // Enable comprehensive logging
        EnableLogging: true,
        LogLevel: 'DEBUG',
        EnableTracing: true,
        // Details for runtime image build via CodeBuild
        RuntimeBuildProject: project.projectName,
        RuntimeRepoUri: runtimeRepo.repositoryUri,
        RuntimeImageTag: runtimeSrc.assetHash,
        RuntimeSrcBucket: runtimeSrc.s3BucketName,
        RuntimeSrcKey: runtimeSrc.s3ObjectKey,
        // Configure gateway to use JWT authorizer via Cognito
        AuthorizerType: 'CUSTOM_JWT',
        JwtDiscoveryUrl: discoveryUrl,
        JwtAllowedAudience: [props.cognitoUserPoolClientId],
        ApiKeyValue: props.apiKeyValue || undefined,
        // If you already created an API key credential provider in AgentCore Identity,
        // pass its ARN via context: -c apiKeyProviderArn=arn:aws:bedrock-agentcore:...:credential-provider/...
        ApiKeyProviderArn: Stack.of(this).node.tryGetContext('apiKeyProviderArn') || undefined,
        OAuthProviderArn: Stack.of(this).node.tryGetContext('oauthProviderArn') || undefined,
        Tools: [{ name: 'Ping', method: 'GET', path: props.apiUrl }],
        // Nonce lets you force-refresh the custom resource via --context agentCoreNonce=...
        Nonce: Stack.of(this).node.tryGetContext('workflowAgentNonce') || 'v1',
      },
    });
    // Bedrock AgentCore will automatically create its service-linked role during provisioning
    // when allowed by the provisioner role's iam:CreateServiceLinkedRole permission.

    new CfnOutput(this, 'WorkflowGatewayId', { value: resource.getAttString('GatewayId') });
    new CfnOutput(this, 'WorkflowAgentAlias', { value: resource.getAttString('AgentAlias') });
    new CfnOutput(this, 'WorkflowRuntimeEndpointArn', { value: resource.getAttString('RuntimeEndpointArn') });
    new CfnOutput(this, 'WorkflowAgentRuntimeId', { value: resource.getAttString('AgentRuntimeId') });
    new CfnOutput(this, 'WorkflowAgentRoleArn', { value: agentRole.roleArn });

    // Publish metadata to SSM so the API can discover it
    const ns = '/spendoptimo/workflow-agent';
    new ssm.StringParameter(this, 'WorkflowAgentIdParam', {
      parameterName: `${ns}/id`,
      stringValue: resource.getAttString('GatewayId'),
    });
    new ssm.StringParameter(this, 'WorkflowAgentAliasParam', {
      parameterName: `${ns}/alias`,
      stringValue: resource.getAttString('AgentAlias'),
    });
    new ssm.StringParameter(this, 'WorkflowAgentInvokeArnParam', {
      parameterName: `${ns}/invoke-arn`,
      stringValue: resource.getAttString('RuntimeEndpointArn'),
    });
    new ssm.StringParameter(this, 'WorkflowAgentRuntimeIdParam', {
      parameterName: `${ns}/runtime-id`,
      stringValue: resource.getAttString('AgentRuntimeId'),
    });
    new ssm.StringParameter(this, 'WorkflowAgentRoleArnParam', {
      parameterName: `${ns}/role-arn`,
      stringValue: agentRole.roleArn,
    });
    new ssm.StringParameter(this, 'WorkflowAgentRuntimeVersionParam', {
      parameterName: `${ns}/runtime-version`,
      stringValue: resource.getAttString('AgentRuntimeVersion'),
    });
  }
}
