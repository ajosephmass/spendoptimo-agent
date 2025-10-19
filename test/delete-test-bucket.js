#!/usr/bin/env node

/**
 * Delete test S3 buckets created by create-test-bucket.js
 */

const { S3Client, ListBucketsCommand, ListObjectVersionsCommand, DeleteObjectsCommand, DeleteBucketCommand } = require("@aws-sdk/client-s3");

async function deleteTestBuckets() {
  const client = new S3Client({ region: process.env.AWS_REGION || 'us-east-1' });
  
  try {
    console.log('Searching for SpendOptimo test buckets...\n');
    
    // List all buckets
    const { Buckets } = await client.send(new ListBucketsCommand({}));
    
    // Find test buckets (those starting with spendoptimo-test-bucket-)
    const testBuckets = Buckets.filter(b => b.Name.startsWith('spendoptimo-test-bucket-'));
    
    if (testBuckets.length === 0) {
      console.log('No test buckets found.');
      return;
    }
    
    console.log(`Found ${testBuckets.length} test bucket(s):\n`);
    
    for (const bucket of testBuckets) {
      console.log(`Deleting bucket: ${bucket.Name}...`);
      
      try {
        // Empty the bucket first (delete all objects and versions)
        const versions = await client.send(new ListObjectVersionsCommand({ Bucket: bucket.Name }));
        
        if (versions.Versions || versions.DeleteMarkers) {
          const objectsToDelete = [
            ...(versions.Versions || []).map(v => ({ Key: v.Key, VersionId: v.VersionId })),
            ...(versions.DeleteMarkers || []).map(d => ({ Key: d.Key, VersionId: d.VersionId }))
          ];
          
          if (objectsToDelete.length > 0) {
            await client.send(new DeleteObjectsCommand({
              Bucket: bucket.Name,
              Delete: { Objects: objectsToDelete }
            }));
            console.log(`  Deleted ${objectsToDelete.length} object(s)/version(s)`);
          }
        }
        
        // Delete the bucket
        await client.send(new DeleteBucketCommand({ Bucket: bucket.Name }));
        console.log(`  ✅ Bucket deleted: ${bucket.Name}\n`);
        
      } catch (error) {
        console.error(`  ❌ Error deleting ${bucket.Name}:`, error.message, '\n');
      }
    }
    
    console.log('Cleanup complete!');
    
  } catch (error) {
    console.error('❌ Error:', error.message);
    process.exit(1);
  }
}

deleteTestBuckets();

