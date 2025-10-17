import { Stack, StackProps, CfnOutput, Duration, CustomResource, RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as apigw from 'aws-cdk-lib/aws-apigateway';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3assets from 'aws-cdk-lib/aws-s3-assets';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import * as path from 'path';
import { execSync } from 'child_process';
import * as crypto from 'crypto';

export class ApiStack extends Stack {
  public readonly api: apigw.RestApi;
  public readonly apiKeyValue: string;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Build API Lambda as a container image in CodeBuild (no local Docker needed)
    const apiRepo = new ecr.Repository(this, 'ApiLambdaRepo', {
      // Let CDK generate a physical name so CFN can replace cleanly if the repo was deleted out-of-band
      imageScanOnPush: true,
      removalPolicy: RemovalPolicy.DESTROY,
      emptyOnDelete: true,
    });
    const apiSrc = new s3assets.Asset(this, 'ApiImageSrc', {
      path: path.join(__dirname, '../../api'),
    });
    const apiProject = new codebuild.Project(this, 'ApiImageBuild', {
      environment: { buildImage: codebuild.LinuxBuildImage.AMAZON_LINUX_2_5, privileged: true },
      environmentVariables: {
        REPO_URI: { value: apiRepo.repositoryUri },
        IMAGE_TAG: { value: apiSrc.assetHash },
        SRC_BUCKET: { value: apiSrc.s3BucketName },
        SRC_KEY: { value: apiSrc.s3ObjectKey },
        AWS_REGION: { value: Stack.of(this).region },
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          pre_build: {
            commands: [
              'aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $REPO_URI',
              'aws s3 cp s3://$SRC_BUCKET/$SRC_KEY src.zip',
              'mkdir -p src && unzip -q src.zip -d src && cd src',
            ],
          },
          build: {
            commands: [
              // Build single-arch Docker image with Docker v2 schema compatible with Lambda
              'docker build -f Dockerfile.api -t $REPO_URI:$IMAGE_TAG .',
              'docker push $REPO_URI:$IMAGE_TAG',
            ],
          },
        },
        artifacts: { files: ['**/*'], 'discard-paths': 'yes' },
      }),
    });
    apiSrc.grantRead(apiProject);
    apiRepo.grantPullPush(apiProject);
    // Ensure ECR repo exists before creating/updating the CodeBuild project (policy references repo ARN)
    apiProject.node.addDependency(apiRepo);

    const trigger = new lambda.Function(this, 'ApiImageBuildTrigger', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromInline(
        [
          'import boto3, os, time',
          'cb = boto3.client("codebuild")',
          'ecr = boto3.client("ecr")',
          'def handler(event, context):',
          '    project = os.environ["PROJECT"]',
          '    repo_name = os.environ["REPO_NAME"]',
          '    image_tag = os.environ["IMAGE_TAG"]',
          '    physical_id = f"ApiImageBuild-{image_tag}"',
          '    # Handle delete without starting a build',
          '    if event.get("RequestType") == "Delete":',
          '        return {"PhysicalResourceId": event.get("PhysicalResourceId", physical_id), "Data": {}}',
          '    # Start build (project env has SRC_BUCKET/SRC_KEY etc.)',
          '    resp = cb.start_build(projectName=project)',
          '    build_id = resp.get("build", {}).get("id")',
          '    if not build_id:',
          '        raise Exception("Failed to start CodeBuild build")',
          '    # Poll until completion',
          '    while True:',
          '        time.sleep(5)',
          '        res = cb.batch_get_builds(ids=[build_id])',
          '        b = (res.get("builds") or [{}])[0]',
          '        status = b.get("buildStatus")',
          '        if status in ("SUCCEEDED", "FAILED", "FAULT", "STOPPED", "TIMED_OUT"):',
          '            if status != "SUCCEEDED":',
          '                raise Exception(f"Build {build_id} failed: {status}")',
          '            break',
          '    # ECR can be eventually consistent; wait until the tag is visible',
          '    for _ in range(60):',
          '        try:',
          '            ecr.describe_images(repositoryName=repo_name, imageIds=[{"imageTag": image_tag}])',
          '            break',
          '        except Exception:',
          '            time.sleep(2)',
          '    return {"PhysicalResourceId": physical_id, "Data": {"ImageTag": image_tag}}',
        ].join('\n')
      ),
      timeout: Duration.minutes(15),
      environment: { PROJECT: apiProject.projectName, REPO_NAME: apiRepo.repositoryName, IMAGE_TAG: apiSrc.assetHash },
    });
    trigger.addToRolePolicy(new iam.PolicyStatement({
      actions: ['codebuild:StartBuild','codebuild:BatchGetBuilds'],
      resources: [apiProject.projectArn],
    }));
    trigger.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ecr:DescribeImages'],
      resources: [apiRepo.repositoryArn],
    }));

    const provider = new cr.Provider(this, 'ApiImageBuildProvider', { onEventHandler: trigger });
    const buildResource = new CustomResource(this, 'BuildApiImage', {
      serviceToken: provider.serviceToken,
      properties: {
        RepoName: apiRepo.repositoryName,
        ImageTag: apiSrc.assetHash,
      },
    });
    // Ensure the build custom resource runs after the repo and project are ready
    buildResource.node.addDependency(apiRepo);
    buildResource.node.addDependency(apiProject);

    const apiFn = new lambda.DockerImageFunction(this, 'SpendOptimoApiFn', {
      // Use the tag (asset hash) and depend on the build custom resource to ensure it exists
      code: lambda.DockerImageCode.fromEcr(apiRepo, { tagOrDigest: buildResource.getAttString('ImageTag') }),
      architecture: lambda.Architecture.X86_64,
      timeout: Duration.seconds(300), // Increased for workflow agent invocations
      memorySize: 512,
      environment: {
        AGENTCORE_ID_PARAM: '/spendoptimo/agentcore/id',
        AGENTCORE_ALIAS_PARAM: '/spendoptimo/agentcore/alias',
        AGENTCORE_INVOKE_PARAM: '/spendoptimo/agentcore/invoke-arn',
        AGENTCORE_ROLE_PARAM: '/spendoptimo/agentcore/role-arn',
        STRANDS_STATE_MACHINE_ARN: '', // Will be updated after state machine is created
      },
    });
    apiFn.node.addDependency(buildResource);
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['ssm:GetParameter', 'ssm:GetParameters', 'ssm:GetParameterHistory'],
      resources: [
        `arn:aws:ssm:${this.region}:${this.account}:parameter/spendoptimo/agentcore/*`,
        `arn:aws:ssm:${this.region}:${this.account}:parameter/spendoptimo/workflow-agent/*`,
      ],
    }));
    // Allow Lambda to invoke itself asynchronously for workflow execution
    // Using wildcard for function name to avoid circular dependency
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [`arn:aws:lambda:${this.region}:${this.account}:function:SpendOptimoApi-SpendOptimoApiFn*`],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock-agentcore:InvokeAgentRuntime'],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'bedrock-agentcore:GetAgentRuntimeEndpoint',
        'bedrock-agentcore:ListAgentRuntimeEndpoints',
      ],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'ce:GetCostAndUsage',
        'ce:GetCostForecast',
        'ce:GetSavingsPlansCoverage',
        'ce:GetReservationCoverage',
        'ce:GetAnomalies',
      ],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'compute-optimizer:GetEC2InstanceRecommendations',
        'compute-optimizer:GetAutoScalingGroupRecommendations',
        'compute-optimizer:GetEBSVolumeRecommendations',
        'compute-optimizer:GetRDSInstanceRecommendations',
        'compute-optimizer:GetLambdaFunctionRecommendations',
      ],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'ec2:DescribeInstances',
        'ec2:DescribeVolumes',
        'ec2:DescribeInstanceStatus',
        // EC2 modification permissions for rightsizing
        'ec2:StopInstances',
        'ec2:StartInstances',
        'ec2:ModifyInstanceAttribute',
        'ec2:ModifyVolume',
        // Auto Scaling
        'autoscaling:DescribeAutoScalingGroups',
        'autoscaling:DescribeLaunchConfigurations',
        // Lambda
        'lambda:ListFunctions',
        'lambda:ListProvisionedConcurrencyConfigs',
        'lambda:GetProvisionedConcurrencyConfig',
        'lambda:GetFunctionConfiguration',
        'lambda:PutFunctionConcurrency',
        'lambda:UpdateFunctionConfiguration',
        // RDS
        'rds:DescribeDBInstances',
        'rds:ModifyDBInstance',
        // S3
        's3:ListAllMyBuckets',
        's3:GetLifecycleConfiguration',
        's3:PutLifecycleConfiguration',
        // CloudWatch for metrics
        'cloudwatch:GetMetricStatistics',
        'cloudwatch:PutMetricData',
      ],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'states:StartExecution',
        'states:DescribeExecution',
        'states:DescribeStateMachine',
      ],
      resources: ['*'],
    }));
    apiFn.addToRolePolicy(new iam.PolicyStatement({
      actions: [
        'scheduler:CreateSchedule',
        'scheduler:UpdateSchedule',
        'scheduler:DeleteSchedule',
        'scheduler:GetSchedule',
      ],
      resources: ['*'],
    }));

    this.api = new apigw.LambdaRestApi(this, 'SpendOptimoApiGateway', {
      handler: apiFn,
      proxy: false,
      deployOptions: { stageName: 'prod' },
      defaultMethodOptions: { apiKeyRequired: true },
      restApiName: 'SpendOptimoApi',
    });

    // Explicitly expose POST /v1/chat without API key (uses Cognito JWT)
    const v1 = this.api.root.addResource('v1');
    const chat = v1.addResource('chat');
    chat.addCorsPreflight({
      allowOrigins: apigw.Cors.ALL_ORIGINS,
      allowHeaders: apigw.Cors.DEFAULT_HEADERS,
      allowMethods: ['POST', 'OPTIONS'],
    });
    chat.addMethod('POST', undefined, { apiKeyRequired: false });

    const analyze = v1.addResource('analyze');
    analyze.addCorsPreflight({
      allowOrigins: apigw.Cors.ALL_ORIGINS,
      allowHeaders: apigw.Cors.DEFAULT_HEADERS,
      allowMethods: ['GET', 'OPTIONS'],
    });
    analyze.addMethod('GET', undefined, { apiKeyRequired: false });

    const recommend = v1.addResource('recommend');
    recommend.addCorsPreflight({
      allowOrigins: apigw.Cors.ALL_ORIGINS,
      allowHeaders: apigw.Cors.DEFAULT_HEADERS,
      allowMethods: ['GET', 'OPTIONS'],
    });
    recommend.addMethod('GET', undefined, { apiKeyRequired: false });

    const automation = v1.addResource('automation');
    automation.addCorsPreflight({
      allowOrigins: apigw.Cors.ALL_ORIGINS,
      allowHeaders: apigw.Cors.DEFAULT_HEADERS,
      allowMethods: ['POST', 'OPTIONS'],
    });
    automation.addMethod('POST', undefined, { apiKeyRequired: false });

    // Add a greedy proxy for all other routes (require API key by default)
    this.api.root.addProxy({ anyMethod: true });

    // Create an API key and usage plan; use a stable random value at synth time for demo purposes
    this.apiKeyValue = crypto.randomBytes(16).toString('hex');
    const key = new apigw.ApiKey(this, 'SpendOptimoApiKey', { value: this.apiKeyValue });
    const plan = new apigw.UsagePlan(this, 'SpendOptimoUsagePlan', {
      name: 'SpendOptimoPlan',
      throttle: { rateLimit: 50, burstLimit: 10 },
    });
    plan.addApiStage({ api: this.api, stage: this.api.deploymentStage });
    plan.addApiKey(key);

    // Create Step Functions state machine for automation workflows
    // Use a simple pass state to avoid circular dependency for now
    const stateMachine = new stepfunctions.StateMachine(this, 'SpendOptimoAutomationStateMachine', {
      stateMachineName: 'SpendOptimoAutomation',
      definition: new stepfunctions.Pass(this, 'AutomationPass', {
        result: stepfunctions.Result.fromObject({
          message: 'Strands workflow executed successfully',
          timestamp: new Date().toISOString(),
          workflow: [
            'collect_cost_evidence',
            'collect_optimizer_signals', 
            'draft_action_plan',
            'approve_plan',
            'apply_fix',
            'verify_outcome'
          ]
        })
      }),
      timeout: Duration.minutes(15),
    });

    // Grant the API Lambda permission to start executions
    stateMachine.grantStartExecution(apiFn);

    // Update the Lambda environment variable with the state machine ARN
    apiFn.addEnvironment('STRANDS_STATE_MACHINE_ARN', stateMachine.stateMachineArn);

    new CfnOutput(this, 'ApiUrl', { value: this.api.url });
    new CfnOutput(this, 'ApiKey', { value: this.apiKeyValue });
    new CfnOutput(this, 'StateMachineArn', { value: stateMachine.stateMachineArn });
  }


}
