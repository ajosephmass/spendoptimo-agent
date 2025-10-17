import { Stack, StackProps, CfnOutput, RemovalPolicy } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as sagemaker from 'aws-cdk-lib/aws-sagemaker';
import * as path from 'path';

export class SageMakerStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const region = Stack.of(this).region || 'us-east-1';
    const imageRepoAccount = '763104351884';
    const imageRepoName = 'pytorch-inference';
    const imageUri = ` ${imageRepoAccount}.dkr.ecr.${region}.amazonaws.com/${imageRepoName}:2.5.1-cpu-py311-ubuntu22.04-sagemaker`.trim();

    // 1) Bucket for the model artifact (deleted on destroy)
    const modelBucket = new s3.Bucket(this, 'SpendOptimoModelBucket', {
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      enforceSSL: true,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // 2) Upload local artifact to s3://<bucket>/model/model.tar.gz
    const deploy = new s3deploy.BucketDeployment(this, 'UploadModelTarGz', {
      destinationBucket: modelBucket,
      destinationKeyPrefix: 'model',
      sources: [s3deploy.Source.asset(path.join(__dirname, '../../sagemaker_artifacts'))],
      retainOnDelete: false,
    });

    // 3) SageMaker execution role + permissions
    const smRole = new iam.Role(this, 'SpendOptimoSageMakerRole', {
      assumedBy: new iam.ServicePrincipal('sagemaker.amazonaws.com'),
    });

    // S3 read for model object
    modelBucket.grantRead(smRole);

    // ECR permissions to pull the DLC image
    smRole.addToPolicy(new iam.PolicyStatement({
      actions: ['ecr:GetAuthorizationToken'],
      resources: ['*'], // must be '*' for GetAuthorizationToken
    }));
    smRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        'ecr:BatchCheckLayerAvailability',
        'ecr:BatchGetImage',
        'ecr:GetDownloadUrlForLayer',
        'ecr:DescribeImages',
      ],
      resources: [`arn:aws:ecr:${region}:${imageRepoAccount}:repository/${imageRepoName}`],
    }));

    const modelDataUrl = modelBucket.s3UrlForObject('model/model.tar.gz');

    // 4) Model (depends on upload)
    const model = new sagemaker.CfnModel(this, 'SpendOptimoModel', {
      executionRoleArn: smRole.roleArn,
      primaryContainer: {
        image: imageUri,
        mode: 'SingleModel',
        modelDataUrl,
        environment: {
          SAGEMAKER_PROGRAM: 'inference.py',
          SAGEMAKER_SUBMIT_DIRECTORY: '/opt/ml/model/code',
        },
      },
    });
    model.node.addDependency(deploy);

    // 5) Endpoint config & endpoint
    const endpointConfig = new sagemaker.CfnEndpointConfig(this, 'SpendOptimoEndpointConfig', {
      productionVariants: [{
        initialInstanceCount: 1,
        instanceType: 'ml.m5.large', // switch to ml.t3.medium to reduce cost
        modelName: model.attrModelName,
        variantName: 'AllTraffic',
      }],
    });

    const endpoint = new sagemaker.CfnEndpoint(this, 'SpendOptimoEndpoint', {
      endpointConfigName: endpointConfig.attrEndpointConfigName,
    });

    new CfnOutput(this, 'SageMakerEndpointName', { value: endpoint.ref });
    new CfnOutput(this, 'ModelBucketName', { value: modelBucket.bucketName });
  }
}
