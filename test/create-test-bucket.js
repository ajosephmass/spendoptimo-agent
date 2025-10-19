#!/usr/bin/env node

/**
 * Create Test S3 Bucket for Lifecycle Policy Testing
 * 
 * This script creates a new S3 bucket without any lifecycle policies configured.
 * This allows for testing the SpendOptimo agent's ability to identify and
 * apply lifecycle policies for cost optimization.
 */

const { execSync } = require('child_process');

console.log('🚀 Creating Test S3 Bucket for Lifecycle Policy Testing');
console.log('====================================================');

const bucketName = `spendoptimo-test-bucket-${Date.now()}`;
const region = process.env.AWS_REGION || 'us-east-1';

try {
  console.log(`\n📦 Creating S3 bucket: ${bucketName} in ${region}...`);
  
  // Note: us-east-1 doesn't need LocationConstraint
  let createCommand;
  if (region === 'us-east-1') {
    createCommand = `aws s3api create-bucket --bucket ${bucketName} --region ${region}`;
  } else {
    createCommand = `aws s3api create-bucket --bucket ${bucketName} --region ${region} --create-bucket-configuration LocationConstraint=${region}`;
  }

  console.log('Creating bucket with command:');
  console.log(createCommand);
  
  execSync(createCommand, { 
    stdio: 'inherit',
    encoding: 'utf8'
  });
  
  console.log(`\n✅ Test S3 bucket created: ${bucketName}`);
  
  // Add tags to identify it as a test bucket
  console.log('\n🏷️  Adding tags...');
  const tagCommand = `aws s3api put-bucket-tagging --bucket ${bucketName} --tagging "TagSet=[{Key=Purpose,Value=SpendOptimoTest},{Key=CreatedBy,Value=create-test-bucket.js},{Key=Environment,Value=Test}]"`;
  execSync(tagCommand, { stdio: 'inherit' });
  
  console.log('✅ Tags added');
  
  console.log('\n📋 Next Steps:');
  console.log('1. This bucket has NO lifecycle policy (violates company policy for testing)');
  console.log('2. Ask agent: "Analyze my S3 buckets for cost optimization"');
  console.log('3. Agent will detect the missing policy');
  console.log('4. Click "Execute Recommendations" button');
  console.log('5. Workflow Agent will apply Intelligent-Tiering policy');
  
  console.log('\n🔍 Monitor the bucket:');
  console.log(`aws s3api get-bucket-lifecycle-configuration --bucket ${bucketName} --region ${region}`);
  
  console.log('\n⚠️  Remember to delete the bucket when done testing:');
  console.log(`node test/delete-test-bucket.js ${bucketName}`);

} catch (error) {
  console.error('❌ Failed to create test S3 bucket:', error.message);
  process.exit(1);
}

