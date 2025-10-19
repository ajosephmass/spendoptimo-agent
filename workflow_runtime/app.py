"""
SpendOptimoWorkflow Agent - Execution Agent for AWS Optimizations

This agent executes optimization recommendations using Amazon Nova Lite.
It receives recommendations from the SpendOptimo analysis agent and applies them
using service-specific tools.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from strands import Agent, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = BedrockAgentCoreApp()


# ================================
# EC2 Tools
# ================================

@tool
def ec2_stop_instance(instance_id: str) -> str:
    """Stop an EC2 instance. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    import os
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        ec2 = boto3.client('ec2', region_name=region)
        logger.info(f"Stopping EC2 instance {instance_id}")
        
        ec2.stop_instances(InstanceIds=[instance_id])
        
        # Wait for instance to stop
        waiter = ec2.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 10, 'MaxAttempts': 30})
        
        return f"✅ Successfully stopped instance {instance_id}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to stop instance {instance_id}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error stopping instance {instance_id}: {str(e)}"


@tool
def ec2_modify_instance_type(instance_id: str, new_type: str) -> str:
    """Modify an EC2 instance type. Instance must be stopped first. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        ec2 = boto3.client('ec2', region_name=region)
        logger.info(f"Modifying instance {instance_id} to type {new_type}")
        
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={'Value': new_type}
        )
        
        return f"✅ Successfully modified instance {instance_id} to type {new_type}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to modify instance {instance_id}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error modifying instance {instance_id}: {str(e)}"


@tool
def ec2_start_instance(instance_id: str) -> str:
    """Start an EC2 instance. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        ec2 = boto3.client('ec2', region_name=region)
        logger.info(f"Starting EC2 instance {instance_id}")
        
        ec2.start_instances(InstanceIds=[instance_id])
        
        # Wait for instance to be running
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 10, 'MaxAttempts': 30})
        
        return f"✅ Successfully started instance {instance_id}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to start instance {instance_id}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error starting instance {instance_id}: {str(e)}"


@tool
def ec2_verify_instance_type(instance_id: str, expected_type: str) -> str:
    """Verify an EC2 instance has the expected type. Returns verification result."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        ec2 = boto3.client('ec2', region_name=region)
        logger.info(f"Verifying instance {instance_id} is type {expected_type}")
        
        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        
        actual_type = instance['InstanceType']
        state = instance['State']['Name']
        
        if actual_type == expected_type and state == 'running':
            return f"✅ Verified: Instance {instance_id} is {expected_type} and running"
        elif actual_type == expected_type:
            return f"⚠️ Instance {instance_id} is {expected_type} but in state: {state}"
        else:
            return f"❌ Verification failed: Instance {instance_id} is {actual_type}, expected {expected_type}"
    except ClientError as e:
        return f"❌ Failed to verify instance {instance_id}: {e.response['Error']['Message']}"
    except Exception as e:
        return f"❌ Error verifying instance {instance_id}: {str(e)}"


# ================================
# S3 Tools
# ================================

@tool
def s3_put_lifecycle_policy(bucket_name: str, transition_days: int = 0, storage_class: str = "INTELLIGENT_TIERING") -> str:
    """Apply a lifecycle policy to an S3 bucket to transition objects to a different storage class.
    For Intelligent-Tiering, use transition_days=0 to apply immediately.
    Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        s3 = boto3.client('s3', region_name=region)
        logger.info(f"Applying lifecycle policy to bucket {bucket_name}: transition to {storage_class} after {transition_days} days")
        
        lifecycle_config = {
            'Rules': [{
                'ID': 'SpendOptimo-IntelligentTiering',
                'Status': 'Enabled',
                'Filter': {},  # Apply to all objects
                'Transitions': [{
                    'Days': transition_days,
                    'StorageClass': storage_class
                }]
            }]
        }
        
        s3.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_config
        )
        
        logger.info(f"Successfully applied lifecycle policy to {bucket_name}")
        return f"Successfully applied lifecycle policy to bucket {bucket_name}: transition to {storage_class} after {transition_days} days"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        logger.error(f"Failed to apply lifecycle policy to {bucket_name}: {error_code} - {error_msg}")
        return f"Failed to apply lifecycle policy to {bucket_name}: {error_code} - {error_msg}"
    except Exception as e:
        logger.error(f"Error applying lifecycle policy to {bucket_name}: {str(e)}")
        return f"Error applying lifecycle policy: {str(e)}"


# ================================
# Lambda Tools
# ================================

@tool
def lambda_update_memory(function_name: str, memory_size_mb: int) -> str:
    """Update Lambda function memory size. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        lambda_client = boto3.client('lambda', region_name=region)
        logger.info(f"Updating Lambda function {function_name} memory to {memory_size_mb}MB")
        
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            MemorySize=memory_size_mb
        )
        
        return f"Successfully updated Lambda function {function_name} memory to {memory_size_mb}MB"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        logger.error(f"Failed to update Lambda {function_name} memory: {error_code} - {error_msg}")
        return f"Failed to update Lambda {function_name}: {error_code} - {error_msg}"
    except Exception as e:
        logger.error(f"Error updating Lambda memory: {str(e)}")
        return f"Error updating Lambda memory: {str(e)}"


@tool
def lambda_update_concurrency(function_name: str, reserved_concurrent_executions: int) -> str:
    """Update Lambda function reserved concurrency. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        lambda_client = boto3.client('lambda', region_name=region)
        logger.info(f"Updating Lambda function {function_name} concurrency to {reserved_concurrent_executions}")
        
        lambda_client.put_function_concurrency(
            FunctionName=function_name,
            ReservedConcurrentExecutions=reserved_concurrent_executions
        )
        
        return f"✅ Successfully updated Lambda function {function_name} concurrency to {reserved_concurrent_executions}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to update Lambda {function_name}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error updating Lambda concurrency: {str(e)}"


# ================================
# RDS Tools
# ================================

@tool
def rds_modify_instance(db_instance_id: str, new_instance_class: str) -> str:
    """Modify an RDS instance class. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        rds = boto3.client('rds', region_name=region)
        logger.info(f"Modifying RDS instance {db_instance_id} to class {new_instance_class}")
        
        rds.modify_db_instance(
            DBInstanceIdentifier=db_instance_id,
            DBInstanceClass=new_instance_class,
            ApplyImmediately=True
        )
        
        return f"✅ Successfully initiated RDS instance modification for {db_instance_id} to {new_instance_class}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to modify RDS instance {db_instance_id}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error modifying RDS instance: {str(e)}"


# ================================
# EBS Tools
# ================================

@tool
def ebs_modify_volume(volume_id: str, new_volume_type: str, new_size_gb: int = None) -> str:
    """Modify an EBS volume type and optionally size. Returns success message or error."""
    import boto3
    from botocore.exceptions import ClientError
    
    try:
        region = os.getenv('AWS_REGION', 'us-east-1')
        ec2 = boto3.client('ec2', region_name=region)
        logger.info(f"Modifying EBS volume {volume_id} to type {new_volume_type}")
        
        params = {
            'VolumeId': volume_id,
            'VolumeType': new_volume_type
        }
        
        if new_size_gb:
            params['Size'] = new_size_gb
        
        ec2.modify_volume(**params)
        
        size_msg = f" and size {new_size_gb}GB" if new_size_gb else ""
        return f"✅ Successfully initiated EBS volume modification for {volume_id} to {new_volume_type}{size_msg}"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        return f"❌ Failed to modify EBS volume {volume_id}: {error_code} - {error_msg}"
    except Exception as e:
        return f"❌ Error modifying EBS volume: {str(e)}"


# ================================
# Workflow Agent
# ================================

def _build_workflow_agent() -> Agent:
    """Build the workflow execution agent with Nova Lite."""
    model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
    logger.info(f"Initializing Workflow Agent with model {model_id}")
    
    model = BedrockModel(model_id=model_id)
    
    system_prompt = (
        "You are SpendOptimoWorkflow, an AWS optimization execution agent. "
        "Your job is to execute cost optimization recommendations provided by the SpendOptimo analysis agent.\n\n"
        
        "You have tools to modify various AWS resources:\n"
        "- EC2: Stop, modify instance type, start, verify\n"
        "- S3: Apply lifecycle policies for storage class transitions\n"
        "- Lambda: Update concurrency settings\n"
        "- RDS: Modify database instance classes\n"
        "- EBS: Modify volume types and sizes\n\n"
        
        "When you receive recommendations, execute them immediately:\n"
        "1. Process each recommendation based on its resource_type\n"
        "2. For EC2 rightsizing: stop → modify → start → verify\n"
        "3. For S3: Use s3_put_lifecycle_policy(bucket_name, transition_days=0, storage_class='INTELLIGENT_TIERING')\n"
        "4. For Lambda memory: Use lambda_update_memory(function_name, memory_size_mb)\n"
        "5. For Lambda concurrency: Use lambda_update_concurrency(function_name, reserved_concurrent_executions)\n"
        "5. For RDS: modify instance class\n"
        "6. For EBS: modify volume type/size\n"
        "7. Provide clear status for EACH recommendation\n"
        "8. If a step fails, explain why and suggest next steps\n\n"
        
        "Format your final response with:\n"
        "- Summary of what was executed\n"
        "- Status for each recommendation (success/failed)\n"
        "- Total savings achieved\n"
        "- Any issues or warnings"
    )
    
    return Agent(
        model=model,
        tools=[
            # EC2 tools
            ec2_stop_instance,
            ec2_modify_instance_type,
            ec2_start_instance,
            ec2_verify_instance_type,
            # S3 tools
            s3_put_lifecycle_policy,
            # Lambda tools
            lambda_update_memory,
            lambda_update_concurrency,
            # RDS tools
            rds_modify_instance,
            # EBS tools
            ebs_modify_volume,
        ],
        system_prompt=system_prompt,
    )


# Global agent instance
_agent = None

def _get_agent() -> Agent:
    """Get or create the workflow agent instance."""
    global _agent
    if _agent is None:
        _agent = _build_workflow_agent()
    return _agent


@app.entrypoint
def execute_workflow(request: RequestContext) -> Dict[str, Any]:
    """Execute optimization recommendations."""
    # AgentCore passes the user's message/goal, which contains the recommendations JSON
    user_input = request.get("goal") or request.get("prompt") or request.get("input") or ""
    
    # Try to parse as JSON array of recommendations
    recommendations = []
    try:
        if isinstance(user_input, str):
            parsed = json.loads(user_input)
            if isinstance(parsed, list):
                recommendations = parsed
            elif isinstance(parsed, dict) and "recommendations" in parsed:
                recommendations = parsed["recommendations"]
        elif isinstance(user_input, list):
            recommendations = user_input
    except json.JSONDecodeError:
        logger.warning(f"Could not parse input as JSON, treating as text: {user_input[:100]}")
    
    logger.info(f"Workflow agent received {len(recommendations)} recommendations")
    
    # If no recommendations provided, fetch them
    if not recommendations:
        logger.info("No recommendations provided, fetching current recommendations...")
        try:
            import boto3
            region = os.getenv('AWS_REGION', 'us-east-1')
            ec2_client = boto3.client('ec2', region_name=region)
            compute_optimizer = boto3.client('compute-optimizer', region_name=region)
            
            # Get running instances
            response = ec2_client.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            
            # Simple policy check: flag r5, m5, c5, t2 instances
            disallowed_families = ['r5', 'm5', 'c5', 't2']
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    family = instance_type.split('.')[0]
                    
                    if family in disallowed_families:
                        recommendations.append({
                            "resource_type": "EC2",
                            "instance_id": instance_id,
                            "current_instance_type": instance_type,
                            "recommended_instance_type": "t3.medium",
                            "estimated_monthly_savings": "$50.00",
                            "reason": "Policy violation - disallowed instance family"
                        })
            
            logger.info(f"Fetched {len(recommendations)} recommendations")
        except Exception as e:
            logger.error(f"Failed to fetch recommendations: {e}")
            return {
                "status": "failed",
                "message": f"No recommendations provided and failed to fetch: {str(e)}",
                "results": []
            }
    
    if not recommendations:
        return {
            "status": "success",
            "message": "No optimization recommendations found. All resources are compliant.",
            "results": []
        }
    
    # Build a prompt for the workflow agent
    prompt = f"""Execute these {len(recommendations)} AWS optimization recommendations:

{json.dumps(recommendations, indent=2)}

CRITICAL INSTRUCTIONS:
- For S3 recommendations: Extract bucket_name and call s3_put_lifecycle_policy(bucket_name, 0, 'INTELLIGENT_TIERING')
- For Lambda memory recommendations: Extract function_name and recommended_memory_mb, call lambda_update_memory(function_name, memory_size_mb)
- For Lambda concurrency recommendations: Extract function_name and recommended_concurrency, call lambda_update_concurrency(function_name, reserved_concurrent_executions)
- For EC2 recommendations: stop → modify → start → verify sequence

Process ALL recommendations and report results for each one."""
    
    try:
        logger.info(f"Starting workflow agent execution for {len(recommendations)} recommendations")
        agent = _get_agent()
        response = agent(prompt)
        result_text = response.message["content"][0]["text"]
        
        logger.info(f"Workflow agent completed execution. Response length: {len(result_text)}")
        logger.info(f"Workflow agent response preview: {result_text[:200]}...")
        
        return {
            "status": "success",
            "message": result_text,
            "recommendations_processed": len(recommendations),
            "execution_details": result_text
        }
        
    except Exception as e:
        logger.exception(f"Workflow agent execution failed: {e}")
        return {
            "status": "failed",
            "message": f"Workflow execution failed: {str(e)}",
            "error": str(e)
        }


if __name__ == "__main__":
    app.run()

