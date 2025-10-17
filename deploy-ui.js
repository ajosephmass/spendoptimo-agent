#!/usr/bin/env node

/**
 * Deploy SpendOptimo UI
 * 
 * This script builds the webapp and deploys it to S3/CloudFront
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

console.log('🚀 Deploying SpendOptimo UI');
console.log('==========================');

try {
  // 1. Build the webapp
  console.log('\n📦 Building webapp...');
  execSync('npm run build', { 
    cwd: path.join(__dirname, 'webapp'),
    stdio: 'inherit'
  });

  // 2. Use known S3 bucket name (from your previous deployment)
  console.log('\n🔍 Using S3 bucket name...');
  const bucketName = 'spendoptimoui-spendoptimowebbucketaa1edeb5-ffllzwl99lxc';

  // 3. Get CloudFront distribution ID
  console.log('\n🔍 Getting CloudFront distribution ID...');
  const domain = 'd293f08cklhjup.cloudfront.net';
  const distId = execSync(`aws cloudfront list-distributions --query "DistributionList.Items[?DomainName=='${domain}'].Id" --output text`, {
    encoding: 'utf8'
  }).trim();

  if (!distId) {
    throw new Error('Could not find CloudFront distribution ID');
  }

  console.log(`📦 S3 Bucket: ${bucketName}`);
  console.log(`🌐 CloudFront Distribution: ${distId}`);

  // 4. Sync files to S3
  console.log('\n📤 Uploading files to S3...');
  execSync(`aws s3 sync webapp/dist s3://${bucketName} --region us-east-1 --delete --exclude index.html --cache-control "public,max-age=31536000,immutable"`, {
    stdio: 'inherit'
  });
  
  execSync(`aws s3 cp webapp/dist/index.html s3://${bucketName}/index.html --region us-east-1 --cache-control "no-cache"`, {
    stdio: 'inherit'
  });

  // 5. Invalidate CloudFront
  console.log('\n🔄 Invalidating CloudFront cache...');
  execSync(`aws cloudfront create-invalidation --distribution-id ${distId} --paths "/*"`, {
    stdio: 'inherit'
  });

  console.log('\n✅ UI deployed successfully!');
  console.log(`🌐 URL: https://${domain}`);
  console.log('\n🎯 What\'s new:');
  console.log('- Send button right next to message input');
  console.log('- Lighter message area background');
  console.log('- Action buttons appear after first message');
  console.log('- Fixed Cognito login URL');

} catch (error) {
  console.error('❌ Deployment failed:', error.message);
  process.exit(1);
}
