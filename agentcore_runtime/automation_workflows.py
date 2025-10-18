"""
SpendOptimo Automation Workflows

This module provides automated FinOps workflows that can be triggered
via the AgentCore Gateway to perform cost optimization actions.
"""

import boto3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class SpendOptimoAutomation:
    """Main automation class for FinOps workflows."""
    
    def __init__(self):
        self.ec2_client = boto3.client('ec2')
        self.ce_client = boto3.client('ce')
        self.compute_optimizer = boto3.client('compute-optimizer')
        self.sfn_client = boto3.client('stepfunctions')
    
    def execute_rightsizing_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute automated rightsizing workflow."""
        try:
            logger.info("Starting rightsizing workflow")
            
            # Get rightsizing recommendations
            recommendations = self._get_rightsizing_recommendations()
            
            if not recommendations:
                return {
                    "status": "completed",
                    "message": "No rightsizing recommendations found",
                    "actions_taken": []
                }
            
            actions_taken = []
            
            # Process high-confidence recommendations
            for rec in recommendations:
                if rec.get('confidence', 0) >= 4:  # High confidence
                    action = self._apply_rightsizing_recommendation(rec, context)
                    if action:
                        actions_taken.append(action)
            
            return {
                "status": "completed",
                "message": f"Processed {len(recommendations)} recommendations",
                "actions_taken": actions_taken,
                "potential_savings": sum(float(a.get('savings', 0)) for a in actions_taken)
            }
            
        except Exception as e:
            logger.error(f"Rightsizing workflow failed: {str(e)}")
            return {
                "status": "failed",
                "message": f"Workflow failed: {str(e)}",
                "actions_taken": []
            }
    
    def execute_cost_optimization_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute comprehensive cost optimization workflow."""
        try:
            logger.info("Starting cost optimization workflow")
            
            actions_taken = []
            
            # 1. Analyze current costs
            cost_analysis = self._analyze_current_costs()
            
            # 2. Identify optimization opportunities
            opportunities = self._identify_optimization_opportunities(cost_analysis)
            
            # 3. Execute optimizations based on context
            for opportunity in opportunities:
                if self._should_apply_optimization(opportunity, context):
                    action = self._apply_optimization(opportunity, context)
                    if action:
                        actions_taken.append(action)
            
            return {
                "status": "completed",
                "message": f"Identified {len(opportunities)} optimization opportunities",
                "actions_taken": actions_taken,
                "total_potential_savings": sum(float(a.get('savings', 0)) for a in actions_taken)
            }
            
        except Exception as e:
            logger.error(f"Cost optimization workflow failed: {str(e)}")
            return {
                "status": "failed",
                "message": f"Workflow failed: {str(e)}",
                "actions_taken": []
            }
    
    def execute_anomaly_response_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute automated response to cost anomalies."""
        try:
            logger.info("Starting anomaly response workflow")
            
            # Get recent anomalies
            anomalies = self._get_recent_anomalies()
            
            if not anomalies:
                return {
                    "status": "completed",
                    "message": "No recent anomalies found",
                    "actions_taken": []
                }
            
            actions_taken = []
            
            # Respond to high-impact anomalies
            for anomaly in anomalies:
                if float(anomaly.get('impact', {}).get('total_impact', 0)) > 100:  # $100+ impact
                    action = self._respond_to_anomaly(anomaly, context)
                    if action:
                        actions_taken.append(action)
            
            return {
                "status": "completed",
                "message": f"Responded to {len(anomalies)} anomalies",
                "actions_taken": actions_taken
            }
            
        except Exception as e:
            logger.error(f"Anomaly response workflow failed: {str(e)}")
            return {
                "status": "failed",
                "message": f"Workflow failed: {str(e)}",
                "actions_taken": []
            }
    
    def _get_rightsizing_recommendations(self) -> List[Dict[str, Any]]:
        """Get rightsizing recommendations from Compute Optimizer."""
        try:
            response = self.compute_optimizer.get_ec2_instance_recommendations()
            return response.get('instanceRecommendations', [])
        except Exception as e:
            logger.error(f"Failed to get rightsizing recommendations: {str(e)}")
            return []
    
    def _apply_rightsizing_recommendation(self, recommendation: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply a rightsizing recommendation if approved."""
        try:
            # Check if auto-apply is enabled in context
            if not context.get('auto_apply', False):
                return {
                    "type": "recommendation",
                    "instance": recommendation.get('instanceArn', ''),
                    "current_type": recommendation.get('currentInstanceType', ''),
                    "recommended_type": recommendation.get('recommendationOptions', [{}])[0].get('instanceType', ''),
                    "savings": recommendation.get('recommendationOptions', [{}])[0].get('savingsOpportunity', {}).get('estimatedMonthlySavings', {}).get('value', 0),
                    "status": "pending_approval"
                }
            
            # Auto-apply if enabled
            instance_id = recommendation.get('instanceArn', '').split('/')[-1]
            new_instance_type = recommendation.get('recommendationOptions', [{}])[0].get('instanceType', '')
            
            # Stop instance, modify type, start instance
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            
            # Wait for instance to stop
            waiter = self.ec2_client.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[instance_id])
            
            # Modify instance type
            self.ec2_client.modify_instance_attribute(
                InstanceId=instance_id,
                InstanceType={'Value': new_instance_type}
            )
            
            # Start instance
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            
            return {
                "type": "rightsizing",
                "instance": instance_id,
                "old_type": recommendation.get('currentInstanceType', ''),
                "new_type": new_instance_type,
                "savings": recommendation.get('recommendationOptions', [{}])[0].get('savingsOpportunity', {}).get('estimatedMonthlySavings', {}).get('value', 0),
                "status": "applied"
            }
            
        except Exception as e:
            logger.error(f"Failed to apply rightsizing recommendation: {str(e)}")
            return None
    
    def _analyze_current_costs(self) -> Dict[str, Any]:
        """Analyze current AWS costs."""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'}
                ]
            )
            
            return response
        except Exception as e:
            logger.error(f"Failed to analyze costs: {str(e)}")
            return {}
    
    def _identify_optimization_opportunities(self, cost_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify cost optimization opportunities."""
        opportunities = []
        
        # This would contain logic to identify specific optimization opportunities
        # based on cost analysis, usage patterns, etc.
        
        return opportunities
    
    def _should_apply_optimization(self, opportunity: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Determine if an optimization should be applied based on context."""
        # Check safety thresholds, approval requirements, etc.
        return context.get('auto_apply', False) and opportunity.get('risk_level', 'high') == 'low'
    
    def _apply_optimization(self, opportunity: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Apply a specific optimization."""
        # Implementation would depend on the type of optimization
        return None
    
    def _get_recent_anomalies(self) -> List[Dict[str, Any]]:
        """Get recent cost anomalies."""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            response = self.ce_client.get_anomalies(
                DateInterval={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                }
            )
            
            return response.get('Anomalies', [])
        except Exception as e:
            logger.error(f"Failed to get anomalies: {str(e)}")
            return []
    
    def _respond_to_anomaly(self, anomaly: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Respond to a cost anomaly."""
        # Implementation would depend on the type of anomaly and response strategy
        return {
            "type": "anomaly_response",
            "anomaly_id": anomaly.get('AnomalyId', ''),
            "action": "investigation_initiated",
            "status": "completed"
        }

# Global automation instance
automation = SpendOptimoAutomation()

def execute_workflow(workflow_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a specific workflow type."""
    if workflow_type == "rightsizing":
        return automation.execute_rightsizing_workflow(context)
    elif workflow_type == "cost_optimization":
        return automation.execute_cost_optimization_workflow(context)
    elif workflow_type == "anomaly_response":
        return automation.execute_anomaly_response_workflow(context)
    else:
        return {
            "status": "failed",
            "message": f"Unknown workflow type: {workflow_type}",
            "actions_taken": []
        }


