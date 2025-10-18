from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

# Version: 2.1.0 - Updated button text to "Execute Recommendations"

from bedrock_agentcore import BedrockAgentCoreApp, RequestContext
from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = BedrockAgentCoreApp()


@tool
def analyze_aws_costs(days: int = 7, service: str = None) -> str:
    """Analyze AWS costs and identify anomalies, trends, and optimization opportunities."""
    import boto3
    import json
    from datetime import datetime, timedelta
    
    try:
        # Initialize Cost Explorer client
        ce_client = boto3.client('ce')
        
        # Set date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Build request parameters
        request_params = {
            'TimePeriod': {
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            'Granularity': 'DAILY',
            'Metrics': ['BlendedCost', 'UnblendedCost', 'UsageQuantity'],
            'GroupBy': [
                {'Type': 'DIMENSION', 'Key': 'SERVICE'}
            ]
        }
        
        # Add service filter if specified
        if service:
            request_params['Filter'] = {
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': [service]
                }
            }
        
        # Get cost and usage data
        response = ce_client.get_cost_and_usage(**request_params)
        
        # Try to get Reserved Instance coverage (only for EC2)
        ri_coverage = None
        if not service or service == "Amazon Elastic Compute Cloud - Compute":
            try:
                ri_response = ce_client.get_reservation_coverage(
                    TimePeriod={
                        'Start': start_date.strftime('%Y-%m-%d'),
                        'End': end_date.strftime('%Y-%m-%d')
                    },
                    GroupBy=[
                        {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'}
                    ]
                )
                ri_coverage = ri_response.get('CoveragesByTime', [])
            except Exception as e:
                # Reserved Instance coverage is optional, don't fail the whole request
                ri_coverage = f"Reserved Instance coverage unavailable: {str(e)}"
        
        # Analyze the data
        total_cost = 0
        service_costs = {}
        daily_costs = []
        
        for result in response['ResultsByTime']:
            date = result['TimePeriod']['Start']
            daily_total = 0
            
            for group in result['Groups']:
                service_name = group['Keys'][0]
                cost = float(group['Metrics']['BlendedCost']['Amount'])
                daily_total += cost
                
                if service_name not in service_costs:
                    service_costs[service_name] = 0
                service_costs[service_name] += cost
            
            daily_costs.append({'date': date, 'cost': daily_total})
            total_cost += daily_total
        
        # Identify top services
        top_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Calculate trends
        if len(daily_costs) >= 2:
            recent_avg = sum(d['cost'] for d in daily_costs[-3:]) / min(3, len(daily_costs))
            older_avg = sum(d['cost'] for d in daily_costs[:-3]) / max(1, len(daily_costs) - 3) if len(daily_costs) > 3 else recent_avg
            trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            trend = 0
        
        # Generate analysis
        analysis = {
            "period": f"{start_date} to {end_date}",
            "total_cost": f"${total_cost:.2f}",
            "daily_average": f"${total_cost/days:.2f}",
            "trend": f"{trend:+.1f}%",
            "filter": f"Service: {service}" if service else "All services",
            "top_services": [{"service": s, "cost": f"${c:.2f}"} for s, c in top_services],
            "recommendations": []
        }
        
        # Add Reserved Instance coverage info if available
        if ri_coverage:
            if isinstance(ri_coverage, str):
                analysis["warnings"] = [ri_coverage]
            else:
                analysis["reserved_instance_coverage"] = ri_coverage
        
        # Add recommendations based on analysis
        if trend > 10:
            analysis["recommendations"].append("⚠️ Costs are increasing significantly. Consider reviewing recent changes.")
        elif trend < -10:
            analysis["recommendations"].append("✅ Costs are decreasing. Good optimization progress!")
        
        if top_services:
            top_service = top_services[0]
            if top_service[1] > total_cost * 0.5:
                analysis["recommendations"].append(f"🔍 {top_service[0]} accounts for {top_service[1]/total_cost*100:.1f}% of costs. Review for optimization opportunities.")
        
        return json.dumps(analysis, indent=2)
        
    except Exception as e:
        return f"Error analyzing AWS costs: {str(e)}"

@tool
def get_cost_anomalies(start_date: str = None, end_date: str = None, dimension: str = None) -> str:
    """Detect cost anomalies in AWS billing. Optional parameters: start_date (YYYY-MM-DD), end_date (YYYY-MM-DD), dimension (SERVICE, LINKED_ACCOUNT, etc.)"""
    import boto3
    import json
    from datetime import datetime, timedelta
    
    try:
        ce_client = boto3.client('ce')
        
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Build request parameters - get_anomalies requires specific format
        request_params = {
            'DateInterval': {
                'StartDate': start_date,
                'EndDate': end_date
            }
        }
        
        # Get anomaly detection results
        response = ce_client.get_anomalies(**request_params)
        
        anomalies = []
        for anomaly in response.get('Anomalies', []):
            anomalies.append({
                "anomaly_id": anomaly.get('AnomalyId', 'N/A'),
                "dimension": anomaly.get('Dimension', 'N/A'),
                "impact": {
                    "start_date": anomaly.get('Impact', {}).get('StartDate', 'N/A'),
                    "end_date": anomaly.get('Impact', {}).get('EndDate', 'N/A'),
                    "total_impact": f"${anomaly.get('Impact', {}).get('TotalImpact', {}).get('Amount', 0):.2f}"
                },
                "status": anomaly.get('Status', 'N/A')
            })
        
        if not anomalies:
            return json.dumps({
                "message": "No cost anomalies detected in the specified period",
                "period": f"{start_date} to {end_date}",
                "dimension": dimension or "All dimensions"
            }, indent=2)
        
        return json.dumps({
            "period": f"{start_date} to {end_date}",
            "dimension": dimension or "All dimensions",
            "anomalies": anomalies
        }, indent=2)
        
    except Exception as e:
        return f"Error detecting cost anomalies: {str(e)}"

@tool
def execute_deploy_and_optimize_workflow() -> str:
    """Execute a complete optimization workflow using AWS Strands automation.
    This workflow will:
    1. Discover existing EC2 instances
    2. Collect usage metrics from CloudWatch
    3. Analyze optimization opportunities
    4. Apply rightsizing if beneficial
    5. Verify the optimization results"""
    import boto3
    import json
    import requests
    from datetime import datetime
    
    try:
        # Get the API URL from environment or construct it
        api_url = os.getenv('API_URL', 'https://api.spendoptimo.com')
        if not api_url.startswith('http'):
            api_url = f'https://{api_url}'
        
        # Prepare the automation request for optimize_existing_instances workflow
        automation_request = {
            "action": "optimize_existing_instances",
            "context": {
                "service": "Amazon Elastic Compute Cloud - Compute",
                "requestedBy": "agentcore_runtime",
                "workflow_type": "optimize_existing_instances"
            }
        }
        
        # Call the automation endpoint
        response = requests.post(
            f"{api_url}/v1/automation",
            json=automation_request,
            headers={'Content-Type': 'application/json'},
            timeout=300  # Longer timeout for this workflow
        )
        
        if response.status_code == 200:
            result = response.json()
            execution = result.get('execution', {})
            
            # Format the response
            message = f"🚀 Optimization workflow executed successfully!\n\n"
            message += f"**Execution ID**: {execution.get('id', 'N/A')}\n"
            
            if execution.get('payload', {}).get('workflow'):
                workflow = execution['payload']['workflow']
                
                # Show workflow steps and results
                message += "\n**Workflow Steps Completed:**\n"
                
                if workflow.get('discover_instances'):
                    step = workflow['discover_instances']
                    message += f"✅ **Discover Instances**: {step.get('message', 'Completed')}\n"
                    if step.get('instances'):
                        instances = step['instances']
                        message += f"   - Found {len(instances)} running instances\n"
                        for instance in instances[:3]:  # Show first 3 instances
                            message += f"   - {instance['instance_id']} ({instance['instance_type']})\n"
                
                if workflow.get('collect_usage_metrics'):
                    step = workflow['collect_usage_metrics']
                    message += f"✅ **Collect Usage Metrics**: {step.get('message', 'Completed')}\n"
                    if step.get('instance_metrics'):
                        instance_metrics = step['instance_metrics']
                        message += f"   - Collected metrics for {len(instance_metrics)} instances\n"
                
                if workflow.get('analyze_optimization'):
                    step = workflow['analyze_optimization']
                    message += f"✅ **Analyze Optimization**: {step.get('message', 'Completed')}\n"
                    if step.get('summary'):
                        summary = step['summary']
                        message += f"   - Total Instances: {summary.get('total_instances', 0)}\n"
                        message += f"   - Instances to Optimize: {summary.get('instances_to_optimize', 0)}\n"
                        message += f"   - Estimated Savings: {summary.get('total_estimated_savings', 'N/A')}\n"
                
                if workflow.get('apply_rightsizing'):
                    step = workflow['apply_rightsizing']
                    if step.get('status') == 'success':
                        message += f"✅ **Apply Rightsizing**: {step.get('message', 'Completed')}\n"
                        if step.get('summary'):
                            summary = step['summary']
                            message += f"   - Instances Modified: {summary.get('instances_modified', 0)}\n"
                            message += f"   - Instances Skipped: {summary.get('instances_skipped', 0)}\n"
                    elif step.get('status') == 'skipped':
                        message += f"⏭️ **Apply Rightsizing**: {step.get('message', 'Skipped')}\n"
                    else:
                        message += f"❌ **Apply Rightsizing**: {step.get('message', 'Failed')}\n"
                
                if workflow.get('verify_optimization'):
                    step = workflow['verify_optimization']
                    message += f"✅ **Verify Optimization**: {step.get('message', 'Completed')}\n"
                    if step.get('summary'):
                        summary = step['summary']
                        message += f"   - Successful Verifications: {summary.get('successful_verifications', 0)}\n"
                
                # Add overall workflow status
                if workflow.get('status') == 'completed':
                    message += f"\n🎉 **Overall Status**: {workflow.get('message', 'Workflow completed successfully')}"
                else:
                    message += f"\n⚠️ **Overall Status**: {workflow.get('message', 'Workflow completed with warnings')}"
            else:
                message += "**Workflow executed** - check the execution details for results."
            
            return message
        else:
            return f"❌ Failed to execute optimization workflow. Status: {response.status_code}, Response: {response.text}"
            
    except Exception as e:
        return f"❌ Error executing optimization workflow: {str(e)}"

@tool
def execute_rightsizing_workflow() -> str:
    """Execute the rightsizing workflow using current agent recommendations."""
    import boto3
    import json
    import requests
    from datetime import datetime
    
    try:
        # Get the API URL from environment or construct it
        api_url = os.getenv('API_URL', 'https://api.spendoptimo.com')
        if not api_url.startswith('http'):
            api_url = f'https://{api_url}'
        
        # Get current recommendations by calling the agent's analysis
        try:
            # Call get_rightsizing_recommendations to get current recommendations
            recommendations_data = get_rightsizing_recommendations()
            rec_data = json.loads(recommendations_data)
            recommendations = rec_data.get('recommendations', [])
            
            if not recommendations:
                return "✅ No recommendations found to execute. All resources are already optimized according to company policies and usage patterns."
                
        except Exception as e:
            return f"❌ Error getting recommendations: {str(e)}"
        
        # Prepare the automation request with agent recommendations
        automation_request = {
            "action": "optimize_existing_instances",
            "context": {
                "service": "Amazon Elastic Compute Cloud - Compute",
                "requestedBy": "agentcore_runtime",
                "recommendations": recommendations,
                "workflow_type": "execute_agent_recommendations"
            }
        }
        
        # Call the automation endpoint
        response = requests.post(
            f"{api_url}/v1/automation",
            json=automation_request,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            execution = result.get('execution', {})
            
            # Format the response
            message = f"✅ Rightsizing workflow executed successfully!\n\n"
            message += f"**Execution ID**: {execution.get('id', 'N/A')}\n"
            
            if execution.get('payload', {}).get('workflow'):
                workflow = execution['payload']['workflow']
                
                # Check if there are any recommendations
                if workflow.get('action_plan', {}).get('actionPlan', {}).get('recommendations'):
                    recommendations = workflow['action_plan']['actionPlan']['recommendations']
                    message += f"**Found {len(recommendations)} optimization opportunity(ies):**\n"
                    
                    for i, rec in enumerate(recommendations, 1):
                        message += f"{i}. {rec.get('instanceId', 'N/A')}: {rec.get('currentType', 'N/A')} → {rec.get('recommendedType', 'N/A')} (saves {rec.get('estimatedSavings', 'N/A')})\n"
                    
                    message += f"\n**Total Potential Savings**: {workflow['action_plan']['actionPlan'].get('totalSavings', 'N/A')}\n"
                    message += f"**Risk Level**: {workflow['action_plan']['actionPlan'].get('riskLevel', 'N/A')}\n"
                else:
                    message += "**No rightsizing opportunities found** - your resources are already optimized!\n"
                    message += "Flow executed but no resources are scheduled for rightsizing during off-peak hours.\n"
                
                # Add workflow status
                if workflow.get('status') == 'completed':
                    message += f"\n✅ **Workflow Status**: {workflow.get('message', 'Completed successfully')}"
                else:
                    message += f"\n⚠️ **Workflow Status**: {workflow.get('message', 'Completed with warnings')}"
            else:
                message += "**Workflow executed** - check the execution details for results."
            
            return message
        else:
            return f"❌ Failed to execute rightsizing workflow. Status: {response.status_code}, Response: {response.text}"
            
    except Exception as e:
        return f"❌ Error executing rightsizing workflow: {str(e)}"

# ===================================
# Multi-Service Recommendation Checks
# ===================================

# FUTURE ENHANCEMENT - RDS Optimization
# Uncomment this function to enable RDS instance optimization
# def check_rds_instances():
#     """Check RDS instances against company policies and return recommendations."""
#     import boto3
#     import re
#     from company_policies import get_policy, get_policy_rationale
#     
#     recommendations = []
#     
#     try:
#         rds = boto3.client('rds')
#         response = rds.describe_db_instances()
#         
#         rds_policy = get_policy('rds')
#         if not rds_policy:
#             return []
#         
#         disallowed_classes = rds_policy.get('disallowed_instance_classes', [])
#         recommended_classes = rds_policy.get('recommended_classes', [])
#         
#         for db in response['DBInstances']:
#             db_identifier = db['DBInstanceIdentifier']
#             db_class = db['DBInstanceClass']
#             storage_type = db.get('StorageType', 'gp2')
#             allocated_storage = db.get('AllocatedStorage', 0)
#             
#             # Check instance class against policy
#             is_disallowed = False
#             for pattern in disallowed_classes:
#                 regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
#                 if re.match(f"^{regex_pattern}$", db_class):
#                     is_disallowed = True
#                     break
#             
#             if is_disallowed:
#                 recommended_class = recommended_classes[1] if len(recommended_classes) > 1 else 'db.t3.small'
#                 recommendations.append({
#                     "resource_type": "RDS",
#                     "db_identifier": db_identifier,
#                     "current_class": db_class,
#                     "recommended_class": recommended_class,
#                     "estimated_monthly_savings": "$30.00",
#                     "reason": rds_policy.get('rationale', 'Policy violation - expensive instance class'),
#                     "confidence": "Policy-Based",
#                     "recommendation_source": "Company Cost Policy"
#                 })
#             
#             # Check storage type
#             if storage_type in rds_policy.get('storage', {}).get('disallowed_storage_types', []):
#                 recommendations.append({
#                     "resource_type": "RDS",
#                     "db_identifier": db_identifier,
#                     "current_storage_type": storage_type,
#                     "recommended_storage_type": "gp3",
#                     "estimated_monthly_savings": "$15.00",
#                     "reason": "Policy violation - expensive provisioned IOPS storage",
#                     "confidence": "Policy-Based",
#                     "recommendation_source": "Company Cost Policy"
#                 })
#     
#     except Exception as e:
#         logger.error(f"Error checking RDS instances: {str(e)}")
#     
#     return recommendations


def check_lambda_functions():
    """Check Lambda functions against company policies and return recommendations."""
    import boto3
    from company_policies import get_policy
    
    recommendations = []
    
    try:
        lambda_client = boto3.client('lambda')
        response = lambda_client.list_functions(MaxItems=100)
        
        total_functions = len(response['Functions'])
        logger.info(f"Found {total_functions} Lambda functions to analyze")
        
        lambda_policy = get_policy('lambda')
        if not lambda_policy:
            logger.warning("No Lambda policy found")
            return []
        
        max_concurrency = lambda_policy.get('reserved_concurrency', {}).get('max', 100)
        functions_over_provisioned = 0
        
        for func in response['Functions']:
            function_name = func['FunctionName']
            memory_size = func['MemorySize']
            
            logger.info(f"Checking Lambda {function_name}: {memory_size} MB")
            
            # Check memory (over-provisioned if > 5GB)
            if memory_size > 5120:  # 5GB threshold
                logger.info(f"Lambda {function_name} is over-provisioned: {memory_size} MB > 5120 MB")
                functions_over_provisioned += 1
                recommendations.append({
                    "resource_type": "Lambda",
                    "function_name": function_name,
                    "current_memory_mb": memory_size,
                    "recommended_memory_mb": 1024,
                    "estimated_monthly_savings": "$10.00",
                    "reason": "Over-provisioned memory - most functions don't need > 5GB, recommend 1GB",
                    "confidence": "Policy-Based",
                    "recommendation_source": "Company Cost Policy"
                })
            
            # Check reserved concurrency
            try:
                concurrency_response = lambda_client.get_function_concurrency(FunctionName=function_name)
                reserved_concurrency = concurrency_response.get('ReservedConcurrentExecutions')
                
                if reserved_concurrency and reserved_concurrency > max_concurrency:
                    logger.info(f"Lambda {function_name} concurrency exceeds limit: {reserved_concurrency} > {max_concurrency}")
                    recommendations.append({
                        "resource_type": "Lambda",
                        "function_name": function_name,
                        "current_concurrency": reserved_concurrency,
                        "recommended_concurrency": max_concurrency,
                        "estimated_monthly_savings": "$10.00",
                        "reason": f"Reserved concurrency exceeds policy maximum of {max_concurrency}",
                        "confidence": "Policy-Based",
                        "recommendation_source": "Company Cost Policy"
                    })
            except:
                pass  # Function might not have reserved concurrency set
        
        logger.info(f"Lambda Check Complete: {total_functions} functions analyzed, {functions_over_provisioned} over-provisioned, {len(recommendations)} total recommendations")
    
    except Exception as e:
        logger.error(f"Error checking Lambda functions: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    return recommendations


def check_s3_buckets():
    """Check S3 buckets for lifecycle policies and return recommendations."""
    import boto3
    from botocore.exceptions import ClientError
    from company_policies import get_policy
    
    recommendations = []
    
    try:
        s3 = boto3.client('s3')
        response = s3.list_buckets()
        
        logger.info(f"Found {len(response['Buckets'])} S3 buckets to analyze")
        
        s3_policy = get_policy('s3')
        if not s3_policy or not s3_policy.get('lifecycle_policy_required'):
            logger.info("S3 lifecycle policy not required by company policy")
            return []
        
        buckets_checked = 0
        buckets_skipped = 0
        
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            
            # Check if lifecycle policy exists
            has_lifecycle = False
            try:
                lifecycle_config = s3.get_bucket_lifecycle_configuration(Bucket=bucket_name)
                has_lifecycle = True
                logger.info(f"Bucket {bucket_name} has lifecycle policy")
            except ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchLifecycleConfiguration':
                    has_lifecycle = False
                    logger.info(f"Bucket {bucket_name} has NO lifecycle policy - adding to recommendations")
                else:
                    # Skip buckets we can't access (permissions, etc.)
                    logger.warning(f"Skipping bucket {bucket_name}: {e.response['Error']['Code']}")
                    buckets_skipped += 1
                    continue
            except Exception as e:
                logger.warning(f"Skipping bucket {bucket_name}: {str(e)}")
                buckets_skipped += 1
                continue  # Skip buckets with other errors
            
            buckets_checked += 1
            
            if not has_lifecycle:
                recommendations.append({
                    "resource_type": "S3",
                    "bucket_name": bucket_name,
                    "issue": "No lifecycle policy configured",
                    "recommended_action": "Add Intelligent-Tiering or transition to Glacier",
                    "estimated_monthly_savings": "$20.00",
                    "reason": "Policy requires lifecycle management for all buckets",
                    "confidence": "Policy-Based",
                    "recommendation_source": "Company Cost Policy"
                })
        
        logger.info(f"S3 Check Complete: {buckets_checked} checked, {buckets_skipped} skipped, {len(recommendations)} recommendations")
    
    except Exception as e:
        logger.error(f"Error checking S3 buckets: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    return recommendations


# FUTURE ENHANCEMENT - EBS Optimization
# Uncomment this function to enable EBS volume optimization
# def check_ebs_volumes():
#     """Check EBS volumes against company policies and return recommendations."""
#     import boto3
#     import re
#     from company_policies import get_policy
#     
#     recommendations = []
#     
#     try:
#         ec2 = boto3.client('ec2')
#         response = ec2.describe_volumes()
#         
#         ebs_policy = get_policy('ebs')
#         if not ebs_policy:
#             return []
#         
#         disallowed_types = ebs_policy.get('disallowed_volume_types', [])
#         recommended_type = ebs_policy.get('recommended_types', ['gp3'])[0]
#         
#         for volume in response['Volumes']:
#             volume_id = volume['VolumeId']
#             volume_type = volume['VolumeType']
#             volume_size = volume['Size']
#             state = volume['State']
#             
#             # Check for disallowed types (io1, io2 - expensive provisioned IOPS)
#             if volume_type in disallowed_types:
#                 recommendations.append({
#                     "resource_type": "EBS",
#                     "volume_id": volume_id,
#                     "current_type": volume_type,
#                     "recommended_type": recommended_type,
#                     "size_gb": volume_size,
#                     "estimated_monthly_savings": "$15.00",
#                     "reason": f"Policy violation - {volume_type} is expensive, use {recommended_type} instead",
#                     "confidence": "Policy-Based",
#                     "recommendation_source": "Company Cost Policy"
#                 })
#             
#             # Check for unattached volumes (waste of money)
#             if state == 'available':
#                 recommendations.append({
#                     "resource_type": "EBS",
#                     "volume_id": volume_id,
#                     "volume_type": volume_type,
#                     "size_gb": volume_size,
#                     "issue": "Unattached volume",
#                     "recommended_action": "Snapshot and delete",
#                     "estimated_monthly_savings": "$10.00",
#                     "reason": "Unattached volumes waste money - clean up after 7 days per policy",
#                     "confidence": "Policy-Based",
#                     "recommendation_source": "Company Cost Policy"
#                 })
#     
#     except Exception as e:
#         logger.error(f"Error checking EBS volumes: {str(e)}")
#     
#     return recommendations


@tool
def get_rightsizing_recommendations(resource_types: str = "EC2,Lambda,S3", account_ids: str = None, limit: int = 50) -> str:
    """Get cost optimization recommendations for AWS services based on company policies and AWS optimizer data.
    
    Supports: EC2 (instances), Lambda (functions), S3 (buckets)
    
    Company policies are checked first for immediate recommendations, then AWS optimization services if available.
    Optional parameters: resource_types (comma-separated: EC2,Lambda,S3), account_ids, limit (max recommendations)"""
    import boto3
    import json
    from company_policies import is_instance_type_allowed, get_recommended_type, get_policy_rationale, get_policy, COMPANY_COST_POLICIES
    
    try:
        recommendations = []
        policy_violations = []
        metrics_recommendations = []
        total_savings = 0
        enrollment_status = 'N/A'
        
        # Get EC2 recommendations - POLICY-BASED FIRST
        if 'EC2' in resource_types:
            ec2_client = boto3.client('ec2')
            compute_optimizer = boto3.client('compute-optimizer')
            
            # Check enrollment status
            try:
                enrollment_response = compute_optimizer.get_enrollment_status()
                enrollment_status = enrollment_response.get('status', 'Unknown')
            except:
                enrollment_status = 'Unknown'
            
            # Get company policy
            ec2_policy = get_policy("ec2")
            policy_rationale = get_policy_rationale("ec2")
            # Step 1: Get all running EC2 instances
            try:
                ec2_response = ec2_client.describe_instances(
                    Filters=[
                        {'Name': 'instance-state-name', 'Values': ['running']}
                    ]
                )
                
                running_instances = []
                for reservation in ec2_response['Reservations']:
                    for instance in reservation['Instances']:
                        running_instances.append({
                            'instance_id': instance['InstanceId'],
                            'instance_type': instance['InstanceType'],
                            'launch_time': instance['LaunchTime'].isoformat(),
                            'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                        })
                
                # Step 2: Check each instance against policy
                for instance in running_instances:
                    instance_id = instance['instance_id']
                    instance_type = instance['instance_type']
                    
                    # Check if instance type is allowed by policy
                    if not is_instance_type_allowed(instance_type, "ec2"):
                        # Policy violation - recommend change
                        recommended_type = get_recommended_type(instance_type, "ec2")
                        
                        # Estimate savings (rough calculation based on instance family)
                        estimated_savings = 0
                        if instance_type.startswith('r5') or instance_type.startswith('m5'):
                            estimated_savings = 50.0  # R5/M5 to T3 saves ~$50/month
                        elif instance_type.startswith('c5'):
                            estimated_savings = 40.0  # C5 to T3 saves ~$40/month
                        elif 't3.large' in instance_type:
                            estimated_savings = 20.0
                        elif 't3.xlarge' in instance_type:
                            estimated_savings = 40.0
                        
                        total_savings += estimated_savings
                        
                        policy_violations.append({
                            "resource_type": "EC2",
                            "instance_id": instance_id,
                            "current_instance_type": instance_type,
                            "recommended_instance_type": recommended_type,
                            "violation_type": "disallowed_instance_type",
                            "reason": policy_rationale,
                            "estimated_monthly_savings": f"${estimated_savings:.2f}",
                            "confidence": "Policy-Based",
                            "recommendation_source": "Company Cost Policy",
                            "tags": instance.get('tags', {})
                        })
                
                # Step 3: Try to get Compute Optimizer recommendations (if available)
                try:
                    optimizer_response = compute_optimizer.get_ec2_instance_recommendations()
                    
                    for rec in optimizer_response.get('instanceRecommendations', []):
                        instance_arn = rec.get('instanceArn', '')
                        instance_id = instance_arn.split('/')[-1] if instance_arn else 'N/A'
                        
                        # Skip if already flagged as policy violation
                        if any(pv['instance_id'] == instance_id for pv in policy_violations):
                            continue
                        
                    if rec.get('recommendationOptions'):
                            best_option = rec['recommendationOptions'][0]
                            savings = best_option.get('savingsOpportunity', {}).get('estimatedMonthlySavings', {})
                            savings_value = float(savings.get('value', 0))
                            
                            # Check if recommended type is policy-compliant
                            recommended_type = best_option.get('instanceType', 'N/A')
                            if not is_instance_type_allowed(recommended_type, "ec2"):
                                # Override with policy-compliant type
                                recommended_type = get_recommended_type(recommended_type, "ec2")
                            
                            total_savings += savings_value
                            
                            recommendations.append({
                            "resource_type": "EC2",
                                "instance_id": instance_id,
                            "current_instance_type": rec.get('currentInstanceType', 'N/A'),
                                "recommended_instance_type": recommended_type,
                            "estimated_monthly_savings": f"${savings_value:.2f}",
                            "confidence": best_option.get('rank', 'N/A'),
                                "recommendation_source": "Compute Optimizer",
                            "utilization_metrics": {
                                "cpu": f"{rec.get('utilizationMetrics', {}).get('cpuUtilization', {}).get('value', 0):.1f}%",
                                "memory": f"{rec.get('utilizationMetrics', {}).get('memoryUtilization', {}).get('value', 0):.1f}%"
                            }
                            })
                except Exception as e:
                    # Compute Optimizer data not available - that's OK, we have policy-based recommendations
                    logger.info(f"Compute Optimizer not available: {str(e)}")
                    pass
                
            except Exception as e:
                return f"Error analyzing EC2 instances: {str(e)}"
        
        # Combine policy violations, metrics recommendations, and optimizer recommendations
        all_recommendations = policy_violations + metrics_recommendations + recommendations
        
        # Check other services based on resource_types parameter
        service_summary = {"EC2": len(all_recommendations)}
        
        # FUTURE ENHANCEMENT - Uncomment to enable RDS optimization
        # if 'RDS' in resource_types:
        #     rds_recs = check_rds_instances()
        #     all_recommendations.extend(rds_recs)
        #     service_summary["RDS"] = len(rds_recs)
        #     # Add savings from RDS
        #     for rec in rds_recs:
        #         savings_str = rec.get("estimated_monthly_savings", "$0")
        #         savings_val = float(savings_str.replace("$", "").replace(",", ""))
        #         total_savings += savings_val
        
        if 'Lambda' in resource_types:
            logger.info("Starting Lambda function check...")
            lambda_recs = check_lambda_functions()
            logger.info(f"Lambda check returned {len(lambda_recs)} recommendations")
            all_recommendations.extend(lambda_recs)
            service_summary["Lambda"] = len(lambda_recs)
            # Add savings from Lambda
            for rec in lambda_recs:
                savings_str = rec.get("estimated_monthly_savings", "$0")
                savings_val = float(savings_str.replace("$", "").replace(",", ""))
                total_savings += savings_val
        
        if 'S3' in resource_types:
            logger.info("Starting S3 bucket check...")
            s3_recs = check_s3_buckets()
            logger.info(f"S3 check returned {len(s3_recs)} recommendations")
            all_recommendations.extend(s3_recs)
            service_summary["S3"] = len(s3_recs)
            # Add savings from S3
            for rec in s3_recs:
                savings_str = rec.get("estimated_monthly_savings", "$0")
                savings_val = float(savings_str.replace("$", "").replace(",", ""))
                total_savings += savings_val
        
        # FUTURE ENHANCEMENT - Uncomment to enable EBS optimization
        # if 'EBS' in resource_types:
        #     ebs_recs = check_ebs_volumes()
        #     all_recommendations.extend(ebs_recs)
        #     service_summary["EBS"] = len(ebs_recs)
        #     # Add savings from EBS
        #     for rec in ebs_recs:
        #         savings_str = rec.get("estimated_monthly_savings", "$0")
        #         savings_val = float(savings_str.replace("$", "").replace(",", ""))
        #         total_savings += savings_val
        
        # Limit results
        if limit and len(all_recommendations) > limit:
            all_recommendations = all_recommendations[:limit]
        
        # Build comprehensive resource inventory
        resource_inventory = {
            "total_running_instances": len(running_instances) if 'EC2' in resource_types and 'running_instances' in locals() else 0,
            "total_lambda_functions": service_summary.get("Lambda", 0),
            "total_s3_buckets": service_summary.get("S3", 0),
            "instances_by_type": {},
            "policy_compliant_count": 0,
            "policy_violating_count": 0,
            "services_analyzed": list(service_summary.keys()),
            "recommendations_by_service": service_summary
        }
        
        if 'EC2' in resource_types and 'running_instances' in locals():
            # Count instances by type
            for instance in running_instances:
                itype = instance['instance_type']
                if itype not in resource_inventory["instances_by_type"]:
                    resource_inventory["instances_by_type"][itype] = 0
                resource_inventory["instances_by_type"][itype] += 1
                
                # Count compliance
                if is_instance_type_allowed(itype, "ec2"):
                    resource_inventory["policy_compliant_count"] += 1
                else:
                    resource_inventory["policy_violating_count"] += 1
        
        result = {
            "enrollment_status": enrollment_status,
            "resource_inventory": resource_inventory,
            "policy_violations": len(policy_violations),
            "optimizer_recommendations": len(recommendations),
            "total_recommendations": len(all_recommendations),
            "estimated_total_monthly_savings": f"${total_savings:.2f}",
            "recommendations": all_recommendations,
            "policy_info": {
                "policy_name": "Company Cost Policy",
                "enforcement_level": COMPANY_COST_POLICIES.get("metadata", {}).get("enforcement_level", "strict"),
                "services_checked": list(service_summary.keys())
            }
        }
        
        # Build summary based on what was analyzed
        services_analyzed_str = ', '.join(service_summary.keys())
        total_resources_analyzed = sum(service_summary.values())
        
        if not all_recommendations:
            result["message"] = f"Excellent! All your {services_analyzed_str} resources comply with company cost policies. No optimization recommendations at this time."
            result["compliance_status"] = "compliant"
            result["summary"] = f"Analyzed {services_analyzed_str} resources. All are policy-compliant."
        else:
            if policy_violations:
                result["message"] = f"Found {len(all_recommendations)} optimization opportunity(ies) across {services_analyzed_str}."
                result["compliance_status"] = "violations_detected"
                result["summary"] = f"Analyzed {services_analyzed_str} resources. Found {len(all_recommendations)} recommendation(s)."
            else:
                result["message"] = f"Found {len(all_recommendations)} optimization opportunities across {services_analyzed_str} based on usage metrics."
                result["compliance_status"] = "compliant_with_optimizations"
                result["summary"] = f"Analyzed {services_analyzed_str} resources. Found {len(all_recommendations)} metrics-based optimization(s)."
        
        return json.dumps(result, indent=2)
        
    except Exception as e:
        return f"Error getting rightsizing recommendations: {str(e)}"


def _configure_region() -> str | None:
    model_region = (
        os.getenv("BEDROCK_MODEL_REGION")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
    )
    if model_region:
        current_default = os.getenv("AWS_DEFAULT_REGION")
        if current_default != model_region:
            logger.info("Setting AWS_DEFAULT_REGION to %s for Bedrock runtime", model_region)
            os.environ["AWS_DEFAULT_REGION"] = model_region
        current_region = os.getenv("AWS_REGION")
        if current_region != model_region:
            os.environ["AWS_REGION"] = model_region
    return model_region


def _build_agent() -> Agent:
    model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
    model_region = _configure_region()
    logger.info("Initialising Strands agent with model %s in %s", model_id, model_region or "default region")

    model = BedrockModel(
        model_id=model_id,
    )

    system_prompt = (
        "You are SpendOptimo, an advanced FinOps assistant specialized in AWS cost optimization and financial operations. "
        "You have access to powerful tools for analyzing AWS costs, detecting anomalies, and executing automated optimization workflows. "
        "\n\nYour capabilities include:\n"
        "- analyze_aws_costs: Analyze AWS spending patterns, trends, and identify cost drivers\n"
        "- get_cost_anomalies: Detect unusual spending patterns and cost anomalies\n"
        "- get_rightsizing_recommendations: Get cost optimization recommendations for EC2 instances, Lambda functions, and S3 buckets based on company policies and AWS optimization services\n"
               "- execute_deploy_and_optimize_workflow: Execute a complete optimization workflow that discovers existing instances, analyzes them, and applies rightsizing\n"
        "- execute_rightsizing_workflow: Execute rightsizing workflow on existing resources\n"
        "- calculator: Perform mathematical calculations\n"
        "\n\nGuidelines for responding:\n"
        "- When users ask about cost analysis, trends, or anomalies, use the appropriate tools to provide data-driven insights. DO NOT show any buttons for these queries.\n"
        "- When users ask about rightsizing, optimization, instance recommendations, or cost savings opportunities:\n"
        "  1. ALWAYS use get_rightsizing_recommendations to check company policies and resource compliance\n"
        "  2. Write a CONVERSATIONAL, well-explained response (not just bullet points). Include:\n"
        "     - Opening statement about what you found\n"
        "     - Resource inventory in natural language (e.g., 'I found 5 running EC2 instances...')\n"
        "     - Policy violations explained clearly with context\n"
        "     - Compute Optimizer insights if available\n"
        "     - Total estimated savings\n"
        "     - Clear next steps\n"
        "  3. Use markdown formatting (headers, bold, lists) to make it readable\n"
        "  4. CRITICAL: You MUST end your response with these EXACT markers:\n\n"
        "     [RECOMMENDATIONS_JSON]\n"
        "     <paste the full recommendations JSON array from get_rightsizing_recommendations tool result here>\n"
        "     [/RECOMMENDATIONS_JSON]\n\n"
        "     [BUTTON:Execute Recommendations]\n\n"
        "     These markers must appear for EVERY rightsizing query. If no recommendations, use empty array [].\n"
        "- Company cost policies are the PRIMARY source of recommendations. Compute Optimizer metrics provide additional insights.\n"
        "- If resources violate company policy (e.g., R5 instances when only T3 allowed), explain WHY the policy exists and what the impact is.\n"
        "- Even when everything is compliant, write a positive, detailed response explaining what was checked and why it's good.\n"
        "- DO NOT show the 'Deploy and Optimize Demo' button unless specifically requested by the user.\n"
        "- Be conversational, helpful, and specific. Avoid overly technical jargon.\n"
        "- Always explain the business impact of recommendations."
    )
    return Agent(
        model=model,
        tools=[calculator, analyze_aws_costs, get_cost_anomalies, get_rightsizing_recommendations, execute_rightsizing_workflow, execute_deploy_and_optimize_workflow],
        system_prompt=system_prompt,
    )


_agent = _build_agent()


@app.entrypoint
def spendoptimo_agent(request: RequestContext) -> Dict[str, Any]:
    prompt = (request.get("prompt") or request.get("input") or "").strip()
    logger.info("Runtime received prompt: %s", prompt)
    if not prompt:
        return {
            "brand": "SpendOptimo",
            "message": "No prompt provided.",
        }
    response = _agent(prompt)
    text = response.message["content"][0]["text"]
    logger.info("Runtime response generated successfully")
    
    # Extract recommendations from the text between markers
    recommendations = []
    import re
    
    rec_match = re.search(r'\[RECOMMENDATIONS_JSON\](.*?)\[/RECOMMENDATIONS_JSON\]', text, re.DOTALL)
    if rec_match:
        try:
            rec_json = rec_match.group(1).strip()
            recommendations = json.loads(rec_json)
            if isinstance(recommendations, dict) and 'recommendations' in recommendations:
                recommendations = recommendations['recommendations']
            logger.info(f"Extracted {len(recommendations)} recommendations from response")
        except Exception as e:
            logger.warning(f"Failed to parse recommendations JSON: {e}")
            recommendations = []
    
    # Check if the response contains button markers
    rightsizing_button = "[BUTTON:Execute Recommendations]"
    deploy_button = "[BUTTON:Deploy and Optimize Demo]"
    
    if rightsizing_button in text:
        # Remove the button marker and recommendations JSON from the message
        clean_message = text.replace(rightsizing_button, "").strip()
        if rec_match:
            clean_message = clean_message.replace(rec_match.group(0), "").strip()
        
        # Only include button if there are actual recommendations
        if recommendations and len(recommendations) > 0:
            return {
                "brand": "SpendOptimo",
                "message": clean_message,
                "button": {
                    "text": "Execute Recommendations",
                    "action": "rightsizing_workflow",
                    "recommendations": recommendations
                }
            }
        else:
            # No recommendations - return message without button
            return {
                "brand": "SpendOptimo",
                "message": clean_message
            }
    elif deploy_button in text:
        # Remove the button marker from the message
        clean_message = text.replace(deploy_button, "").strip()
        
        return {
            "brand": "SpendOptimo",
            "message": clean_message,
            "button": {
                "text": "Deploy and Optimize Demo",
                "action": "deploy_and_optimize_workflow"
            }
        }
    
    return {
        "brand": "SpendOptimo",
        "message": text,
    }


if __name__ == "__main__":
    app.run()
