#!/usr/bin/env node

/**
 * Create a test S3 bucket WITHOUT Intelligent-Tiering lifecycle policy
 * for testing SpendOptimo's S3 optimization recommendations
 */

const { S3Client, CreateBucketCommand, PutBucketTaggingCommand } = require("@aws-sdk/client-s3");

async function createTestBucket() {
  const client = new S3Client({ region: process.env.AWS_REGION || 'us-east-1' });
  
  // Generate a unique bucket name
  const timestamp = Date.now();
  const bucketName = `spendoptimo-test-bucket-${timestamp}`;
  
  try {
    console.log(`Creating test S3 bucket: ${bucketName}...`);
    
    // Create bucket
    await client.send(new CreateBucketCommand({
      Bucket: bucketName,
    }));
    
    console.log(`✅ Bucket created: ${bucketName}`);
    
    // Add tags to identify it as a test bucket
    await client.send(new PutBucketTaggingCommand({
      Bucket: bucketName,
      Tagging: {
        TagSet: [
          { Key: 'Purpose', Value: 'SpendOptimoTest' },
          { Key: 'CreatedBy', Value: 'create-test-bucket.js' },
          { Key: 'Environment', Value: 'Test' }
        ]
      }
    }));
    
    console.log(`✅ Tags added to bucket`);
    console.log('\n📋 Bucket Details:');
    console.log(`   Name: ${bucketName}`);
    console.log(`   Region: ${process.env.AWS_REGION || 'us-east-1'}`);
    console.log(`   Lifecycle Policy: None (intentionally omitted for testing)`);
    console.log('\n💡 This bucket should be flagged by SpendOptimo for missing lifecycle policy.');
    console.log('   Run "Analyze my S3 buckets" to see it in recommendations.\n');
    
  } catch (error) {
    console.error('❌ Error creating test bucket:', error.message);
    process.exit(1);
  }
}

createTestBucket();

