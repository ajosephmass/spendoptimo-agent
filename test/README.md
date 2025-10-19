# Test Scripts

This directory contains utility scripts for creating AWS test resources to validate SpendOptimo's optimization capabilities.

## Purpose

These scripts help you:
- Quickly provision AWS resources that violate cost policies
- Test the Analysis Agent's detection capabilities
- Verify the Workflow Agent's execution of optimizations
- Clean up test resources after validation

## Scripts

### `create-test-instance.js`
Creates an EC2 instance that violates company cost policy.

**What it does:**
- Launches an R5.large instance (violates "T3 only" policy)
- Tags it as a test resource
- Provides instructions for testing optimization

**Usage:**
```bash
node test/create-test-instance.js
```

**Expected Output:**
```
🚀 Creating Test EC2 Instance
====================================================
✓ Created test EC2 instance: i-0abc123def456
✓ Instance type: r5.large (violates policy)
✓ Region: us-east-1
✓ Tags: Purpose=SpendOptimoTest, Environment=Test

📋 Next Steps:
1. Ask agent: "Get rightsizing recommendations"
2. Agent will detect R5.large violates policy (only T3 up to medium allowed)
3. Recommendation: Switch to T3.medium to save ~$50/month
4. Click "Execute Recommendations"
5. Workflow Agent will stop → modify → start → verify

⏱️ Wait 2-3 minutes for instance to reach 'running' state
```

**Policy Violation:**
- Instance family: R5 (only T3 allowed)
- Size: large (max allowed: medium)
- Estimated savings: ~$50/month

**Cleanup:**
```bash
aws ec2 terminate-instances --instance-ids i-0abc123def456
```

---

### `create-test-bucket.js`
Creates an S3 bucket without lifecycle policies.

**What it does:**
- Creates a new S3 bucket with unique name
- Adds tags to identify it as a test resource
- Does NOT apply lifecycle policies (intentional violation)

**Usage:**
```bash
node test/create-test-bucket.js
```

**Expected Output:**
```
🚀 Creating Test S3 Bucket for Lifecycle Policy Testing
====================================================
📦 Creating S3 bucket: spendoptimo-test-bucket-1729342496 in us-east-1...

✅ Test S3 bucket created: spendoptimo-test-bucket-1729342496
✅ Tags added

📋 Next Steps:
1. This bucket has NO lifecycle policy (violates company policy for testing)
2. Ask agent: "Analyze my S3 buckets for cost optimization"
3. Agent will detect the missing policy
4. Click "Execute Recommendations" button
5. Workflow Agent will apply Intelligent-Tiering policy

🔍 Monitor the bucket:
aws s3api get-bucket-lifecycle-configuration --bucket spendoptimo-test-bucket-1729342496 --region us-east-1

⚠️ Remember to delete the bucket when done testing:
node test/delete-test-bucket.js spendoptimo-test-bucket-1729342496
```

**Policy Violation:**
- Missing lifecycle policy (all buckets must have lifecycle management)
- Estimated savings: $5-100/month depending on bucket size

**Cleanup:**
```bash
node test/delete-test-bucket.js spendoptimo-test-bucket-1729342496
```

---

### `delete-test-bucket.js`
Deletes a test S3 bucket (with all objects).

**What it does:**
- Empties the bucket (deletes all objects)
- Deletes the bucket itself

**Usage:**
```bash
node test/delete-test-bucket.js <bucket-name>
```

**Example:**
```bash
node test/delete-test-bucket.js spendoptimo-test-bucket-1729342496
```

**Expected Output:**
```
🗑️ Deleting S3 bucket: spendoptimo-test-bucket-1729342496 in us-east-1
====================================================
🧹 Emptying bucket: spendoptimo-test-bucket-1729342496...
✅ Bucket emptied.

🗑️ Deleting bucket: spendoptimo-test-bucket-1729342496...
✅ S3 bucket deleted: spendoptimo-test-bucket-1729342496
```

**Safety:**
⚠️ This permanently deletes the bucket and all objects. Make sure you specify the correct bucket name!

---

## Complete Testing Workflow

### End-to-End EC2 Optimization Test

1. **Create test instance:**
   ```bash
   node test/create-test-instance.js
   # Note the instance ID
   ```

2. **Query the agent:**
   - Open SpendOptimo UI
   - Ask: "Get rightsizing recommendations"
   - Verify agent detects R5.large violation
   - Check estimated savings (~$50/month)

3. **Execute optimization:**
   - Click "Execute Recommendations"
   - Verify execution plan shows:
     - Stop instance i-0abc123def456
     - Modify from r5.large to t3.medium
     - Restart and verify
   - Wait 3-5 minutes

4. **Verify results:**
   ```bash
   aws ec2 describe-instances --instance-ids i-0abc123def456 --query 'Reservations[0].Instances[0].InstanceType'
   # Should show: "t3.medium"
   ```

5. **Cleanup:**
   ```bash
   aws ec2 terminate-instances --instance-ids i-0abc123def456
   ```

---

### End-to-End S3 Optimization Test

1. **Create test bucket:**
   ```bash
   node test/create-test-bucket.js
   # Note the bucket name
   ```

2. **Query the agent:**
   - Ask: "Analyze my S3 buckets for cost optimization"
   - Verify agent detects missing lifecycle policy
   - Check estimated savings ($5-$100/month based on size)

3. **Execute optimization:**
   - Click "Execute Recommendations"
   - Verify execution plan shows:
     - Apply Intelligent-Tiering lifecycle policy to bucket spendoptimo-test-bucket-xxx
   - Wait 10-30 seconds

4. **Verify results:**
   ```bash
   aws s3api get-bucket-lifecycle-configuration --bucket spendoptimo-test-bucket-xxx
   # Should show Intelligent-Tiering rule
   ```

5. **Cleanup:**
   ```bash
   node test/delete-test-bucket.js spendoptimo-test-bucket-xxx
   ```

---

## Prerequisites

All scripts require:
- Node.js 18+
- AWS CLI configured with credentials
- Appropriate IAM permissions:
  - EC2: `ec2:RunInstances`, `ec2:CreateTags`, `ec2:TerminateInstances`
  - S3: `s3:CreateBucket`, `s3:PutBucketTagging`, `s3:DeleteBucket`, `s3:ListBucket`, `s3:DeleteObject`

## Environment Variables

Set these to customize behavior:

```bash
# AWS region for resource creation
export AWS_REGION=us-east-1

# AWS profile (if not using default)
export AWS_PROFILE=my-profile
```

## Cost of Test Resources

While active, test resources incur costs:

| Resource | Type | Hourly Cost | Daily Cost |
|----------|------|-------------|------------|
| EC2 R5.large | On-Demand | ~$0.13 | ~$3.12 |
| S3 Bucket | Empty | ~$0 | ~$0 |

**⚠️ Remember to clean up test resources to avoid unnecessary charges!**

