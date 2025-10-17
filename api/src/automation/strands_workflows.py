"""
Real Strands workflow implementations for SpendOptimo.

This module contains actual Strands workflow steps that can be executed
using the AWS Strands Agents SDK. The workflow now takes agent recommendations
as input and executes them, rather than doing its own analysis.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Initialize AWS clients
ec2_client = boto3.client('ec2')


class ValidateRecommendationsStep:
    """Validate agent recommendations and prepare them for execution."""
    
    def __init__(self):
        self.name = "validate_recommendations"
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate agent recommendations and check if instances still exist."""
        try:
            logger.info("Validating agent recommendations for execution")
            
            # Get recommendations from context (passed from agent)
            recommendations = context.get('recommendations', [])
            
            if not recommendations:
                return {
                    "status": "success",
                    "validated_recommendations": [],
                    "message": "No recommendations to execute",
                    "next_step": "apply_rightsizing"
                }
            
            validated_recommendations = []
            
            for rec in recommendations:
                instance_id = rec.get('instance_id') or rec.get('instanceId')
                current_type = rec.get('current_instance_type') or rec.get('currentType')
                recommended_type = rec.get('recommended_instance_type') or rec.get('recommendedType')
                
                if not all([instance_id, current_type, recommended_type]):
                    logger.warning(f"Skipping invalid recommendation: {rec}")
                    continue
                
                # Check if instance still exists and is running
                try:
                    response = ec2_client.describe_instances(
                        InstanceIds=[instance_id]
                    )
                    
                    if not response['Reservations']:
                        logger.warning(f"Instance {instance_id} not found")
                        continue
                    
                    instance = response['Reservations'][0]['Instances'][0]
                    current_state = instance['State']['Name']
                    actual_type = instance['InstanceType']
                    
                    if current_state != 'running':
                        logger.warning(f"Instance {instance_id} is not running (state: {current_state})")
                        continue
                    
                    if actual_type != current_type:
                        logger.warning(f"Instance {instance_id} type changed from {current_type} to {actual_type}")
                        # Update the recommendation with actual current type
                        rec['current_instance_type'] = actual_type
                        rec['currentType'] = actual_type
                    
                    # Validate the recommendation is still valid
                    validated_rec = {
                        'instance_id': instance_id,
                        'current_instance_type': actual_type,
                        'recommended_instance_type': recommended_type,
                        'estimated_savings': rec.get('estimated_monthly_savings') or rec.get('estimatedSavings', 'N/A'),
                        'reason': rec.get('reason') or rec.get('recommendation_source', 'Agent Analysis'),
                        'original_recommendation': rec
                    }
                    
                    validated_recommendations.append(validated_rec)
                    logger.info(f"Validated recommendation for {instance_id}: {actual_type} -> {recommended_type}")
                    
                except ClientError as e:
                    if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
                        logger.warning(f"Instance {instance_id} not found")
                    else:
                        logger.error(f"Error checking instance {instance_id}: {str(e)}")
                    continue
            
            logger.info(f"Validated {len(validated_recommendations)} out of {len(recommendations)} recommendations")
            
            return {
                "status": "success",
                "validated_recommendations": validated_recommendations,
                "total_recommendations": len(recommendations),
                "valid_recommendations": len(validated_recommendations),
                "skipped_recommendations": len(recommendations) - len(validated_recommendations),
                "message": f"Validated {len(validated_recommendations)} recommendations for execution",
                "next_step": "apply_rightsizing"
            }
            
        except Exception as e:
            logger.error(f"Failed to validate recommendations: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "message": "Failed to validate recommendations"
            }


class ApplyRightsizingStep:
    """Apply rightsizing changes to validated recommendations."""
    
    def __init__(self):
        self.name = "apply_rightsizing"
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply rightsizing changes to validated recommendations."""
        try:
            logger.info("Applying rightsizing changes")
            
            # Get validated recommendations from previous step
            validated_recommendations = context.get('validated_recommendations', [])
            
            if not validated_recommendations:
                return {
                    "status": "success",
                    "applied_changes": [],
                    "summary": {
                        "instances_modified": 0,
                        "instances_skipped": 0,
                        "total_savings": "$0/month"
                    },
                    "message": "No recommendations to apply",
                    "next_step": "verify_optimization"
                }
            
            applied_changes = []
            total_savings = 0
            
            for rec in validated_recommendations:
                instance_id = rec['instance_id']
                current_type = rec['current_instance_type']
                recommended_type = rec['recommended_instance_type']
                estimated_savings = rec['estimated_savings']
                reason = rec['reason']
                
                try:
                    logger.info(f"Applying rightsizing to {instance_id}: {current_type} -> {recommended_type}")
                    
                    # Stop the instance first
                    logger.info(f"Stopping instance {instance_id}")
                    ec2_client.stop_instances(InstanceIds=[instance_id])
                    
                    # Wait for instance to stop
                    waiter = ec2_client.get_waiter('instance_stopped')
                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 10, 'MaxAttempts': 30})
                    
                    # Modify instance type
                    logger.info(f"Modifying instance type for {instance_id} to {recommended_type}")
                    ec2_client.modify_instance_attribute(
                        InstanceId=instance_id,
                        InstanceType={'Value': recommended_type}
                    )
                    
                    # Start the instance
                    logger.info(f"Starting instance {instance_id}")
                    ec2_client.start_instances(InstanceIds=[instance_id])
                    
                    # Wait for instance to start
                    waiter = ec2_client.get_waiter('instance_running')
                    waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 10, 'MaxAttempts': 30})
                    
                    # Extract savings value for calculation
                    savings_value = 0
                    if isinstance(estimated_savings, str) and '$' in estimated_savings:
                        try:
                            savings_value = float(estimated_savings.replace('$', '').replace('/month', ''))
                        except ValueError:
                            pass
                    
                    total_savings += savings_value
                    
                    applied_changes.append({
                        'instance_id': instance_id,
                        'action': 'rightsizing',
                        'from': current_type,
                        'to': recommended_type,
                        'estimated_savings': estimated_savings,
                        'status': 'success',
                        'reason': reason,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    logger.info(f"Successfully rightsized {instance_id}: {current_type} -> {recommended_type}")
                    
                except Exception as e:
                    logger.error(f"Failed to rightsize {instance_id}: {str(e)}")
                    applied_changes.append({
                        'instance_id': instance_id,
                        'action': 'rightsizing',
                        'from': current_type,
                        'to': recommended_type,
                        'estimated_savings': estimated_savings,
                        'status': 'failed',
                        'error': str(e),
                        'reason': reason,
                        'timestamp': datetime.now().isoformat()
                    })
            
            successful_changes = [c for c in applied_changes if c['status'] == 'success']
            failed_changes = [c for c in applied_changes if c['status'] == 'failed']
            
            logger.info(f"Applied {len(successful_changes)} successful changes, {len(failed_changes)} failed")
            
            return {
                "status": "success" if successful_changes else "failed",
                "applied_changes": applied_changes,
                "summary": {
                    "instances_modified": len(successful_changes),
                    "instances_failed": len(failed_changes),
                    "total_savings": f"${total_savings:.2f}/month"
                },
                "message": f"Successfully applied {len(successful_changes)} rightsizing changes",
                "next_step": "verify_optimization"
            }
            
        except Exception as e:
            logger.error(f"Failed to apply rightsizing changes: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "message": "Failed to apply rightsizing changes"
            }


class VerifyOptimizationStep:
    """Verify that optimization changes were applied successfully."""
    
    def __init__(self):
        self.name = "verify_optimization"
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that optimization changes were applied successfully."""
        try:
            logger.info("Verifying optimization changes")
            
            # Get applied changes from previous step
            applied_changes = context.get('applied_changes', [])
            
            if not applied_changes:
                return {
                    "status": "success",
                    "verification_results": [],
                    "summary": {
                        "successful_verifications": 0,
                        "failed_verifications": 0
                    },
                    "message": "No changes to verify",
                    "workflow_complete": True
                }
            
            verification_results = []
            
            for change in applied_changes:
                instance_id = change['instance_id']
                
                if change['status'] == 'failed':
                    verification_results.append({
                        'instance_id': instance_id,
                        'verification_status': 'skipped',
                        'reason': 'Change failed during application',
                        'error': change.get('error', 'Unknown error')
                    })
                    continue
                
                try:
                    # Check current instance state
                    response = ec2_client.describe_instances(InstanceIds=[instance_id])
                    instance = response['Reservations'][0]['Instances'][0]
                    
                    current_state = instance['State']['Name']
                    current_type = instance['InstanceType']
                    expected_type = change['to']
                    
                    if current_state == 'running' and current_type == expected_type:
                        verification_results.append({
                            'instance_id': instance_id,
                            'verification_status': 'success',
                            'current_type': current_type,
                            'expected_type': expected_type,
                            'instance_state': current_state,
                            'verified_at': datetime.now().isoformat()
                        })
                        logger.info(f"Verified successful rightsizing for {instance_id}: {current_type}")
                    else:
                        verification_results.append({
                            'instance_id': instance_id,
                            'verification_status': 'failed',
                            'current_type': current_type,
                            'expected_type': expected_type,
                            'instance_state': current_state,
                            'reason': f"Instance type mismatch or not running (state: {current_state})"
                        })
                        logger.warning(f"Verification failed for {instance_id}: expected {expected_type}, got {current_type} (state: {current_state})")
                
                except Exception as e:
                    verification_results.append({
                        'instance_id': instance_id,
                        'verification_status': 'error',
                        'error': str(e),
                        'reason': 'Failed to verify instance state'
                    })
                    logger.error(f"Failed to verify {instance_id}: {str(e)}")
            
            successful_verifications = [v for v in verification_results if v['verification_status'] == 'success']
            failed_verifications = [v for v in verification_results if v['verification_status'] in ['failed', 'error']]
            
            logger.info(f"Verification complete: {len(successful_verifications)} successful, {len(failed_verifications)} failed")
            
            return {
                "status": "success" if successful_verifications else "failed",
                "verification_results": verification_results,
                "summary": {
                    "successful_verifications": len(successful_verifications),
                    "failed_verifications": len(failed_verifications)
                },
                "message": f"Verified {len(successful_verifications)} successful optimizations",
                "workflow_complete": True
            }
            
        except Exception as e:
            logger.error(f"Failed to verify optimization changes: {str(e)}")
            return {
                "status": "failed",
                "error": str(e),
                "message": "Failed to verify optimization changes"
            }


# Workflow step registry
WORKFLOW_STEPS = {
    "validate_recommendations": ValidateRecommendationsStep(),
    "apply_rightsizing": ApplyRightsizingStep(),
    "verify_optimization": VerifyOptimizationStep(),
}


def execute_workflow_step(step_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a specific workflow step."""
    if step_name not in WORKFLOW_STEPS:
        return {
            "status": "failed",
            "error": f"Unknown workflow step: {step_name}",
            "message": f"Workflow step '{step_name}' not found"
        }
    
    step = WORKFLOW_STEPS[step_name]
    return step.execute(context)