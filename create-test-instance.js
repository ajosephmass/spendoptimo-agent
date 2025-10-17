#!/usr/bin/env node

/**
 * Create Test EC2 Instance for Rightsizing Testing
 * 
 * This script creates a small EC2 instance that you can use to test
 * rightsizing recommendations. The instance will be intentionally
 * over-provisioned to generate optimization recommendations.
 */

const { execSync } = require('child_process');

console.log('🚀 Creating Test EC2 Instance for Rightsizing Testing');
console.log('====================================================');

try {
  // Create an r5.large instance (violates company policy for testing)
  console.log('\n📦 Creating r5.large instance (policy violation test)...');
  
  const userData = `#!/bin/bash
# Install stress-ng to simulate CPU load
yum update -y
yum install -y stress-ng

# Create a simple web server that uses minimal resources
cat > /var/www/html/index.html << 'EOF'
<html>
<head><title>Test Instance</title></head>
<body>
<h1>SpendOptimo Test Instance</h1>
<p>This instance is intentionally over-provisioned for rightsizing testing.</p>
<p>Instance ID: $(curl -s http://169.254.169.254/latest/meta-data/instance-id)</p>
<p>Instance Type: $(curl -s http://169.254.169.254/latest/meta-data/instance-type)</p>
</body>
</html>
EOF

# Start a simple web server
python3 -m http.server 80 --directory /var/www/html &

# Log instance creation
echo "Test instance created at $(date)" >> /var/log/test-instance.log
`;

  const createCommand = `aws ec2 run-instances \
    --image-id ami-0c02fb55956c7d316 \
    --instance-type r5.large \
    --key-name spendoptimo-test \
    --security-groups spendoptimo-test-sg \
    --user-data "${userData}" \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=SpendOptimo-Test-Instance},{Key=Purpose,Value=Rightsizing-Test},{Key=Environment,Value=test}]' \
    --region us-east-1`;

  console.log('Creating instance with command:');
  console.log(createCommand);
  
  const result = execSync(createCommand, { 
    stdio: 'pipe',
    encoding: 'utf8'
  });
  
  const instanceData = JSON.parse(result);
  const instanceId = instanceData.Instances[0].InstanceId;
  
  console.log(`✅ Test instance created: ${instanceId}`);
  console.log('\n📋 Next Steps:');
  console.log('1. Instance violates company policy (R5 family not allowed)');
  console.log('2. Ask agent: "Get rightsizing recommendations for my EC2 instances"');
  console.log('3. Agent will detect policy violation immediately (no waiting needed!)');
  console.log('4. Click "Execute Rightsizing Workflow" button');
  console.log('5. Strands workflow will downsize r5.large → t3.medium');
  
  console.log('\n🔍 Monitor the instance:');
  console.log(`aws ec2 describe-instances --instance-ids ${instanceId} --region us-east-1`);
  
  console.log('\n⚠️ Remember to terminate the instance when done testing:');
  console.log(`aws ec2 terminate-instances --instance-ids ${instanceId} --region us-east-1`);

} catch (error) {
  console.error('❌ Failed to create test instance:', error.message);
  console.log('\n🔧 Prerequisites:');
  console.log('1. Create a key pair: aws ec2 create-key-pair --key-name spendoptimo-test --region us-east-1');
  console.log('2. Create a security group: aws ec2 create-security-group --group-name spendoptimo-test-sg --description "Test security group" --region us-east-1');
  console.log('3. Add HTTP access: aws ec2 authorize-security-group-ingress --group-name spendoptimo-test-sg --protocol tcp --port 80 --cidr 0.0.0.0/0 --region us-east-1');
  process.exit(1);
}
