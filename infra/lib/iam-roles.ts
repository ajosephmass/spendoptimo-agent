import { Stack, StackProps, CfnOutput } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';

export class IamRolesStack extends Stack {
  public readonly outputs: any;
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const executorRole = new iam.Role(this, 'SpendOptimoExecutorRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com')
    });
    executorRole.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'));
    executorRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        "ec2:StopInstances","ec2:StartInstances","ec2:ModifyInstanceAttribute",
        "autoscaling:PutScheduledUpdateGroupAction",
        "s3:PutLifecycleConfiguration","s3:GetLifecycleConfiguration",
        "rds:StopDBInstance","rds:StartDBInstance","rds:ModifyDBInstance",
        "eks:UpdateNodegroupConfig","eks:DescribeNodegroup"
      ],
      resources: ["*"],
      conditions: { "StringEquals": { "aws:ResourceTag/project": "spendoptimo" } }
    }));

    const readRole = new iam.Role(this, 'SpendOptimoReadOnlyRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com')
    });
    readRole.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'));
    readRole.addToPolicy(new iam.PolicyStatement({
      actions: [
        "ce:*","athena:*","glue:*","s3:Get*","s3:List*",
        "compute-optimizer:*","budgets:View*","tag:Get*",
        "cloudwatch:GetMetricData","cloudwatch:ListMetrics",
        "rds:Describe*","eks:List*","eks:Describe*"
      ],
      resources: ["*"]
    }));

    new CfnOutput(this, 'ExecutorRoleArn', { value: executorRole.roleArn });
    new CfnOutput(this, 'ReadOnlyRoleArn', { value: readRole.roleArn });

    this.outputs = { executorRoleArn: executorRole.roleArn, readOnlyRoleArn: readRole.roleArn };
  }
}
