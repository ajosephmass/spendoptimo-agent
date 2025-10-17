"""
Multi-Service Optimization Workflows for AWS

This module defines common workflow patterns that can be applied across different AWS services.
Each service has a similar structure: Discover → Analyze → Optimize → Verify
"""

# Common Workflow Pattern for All Services
COMMON_WORKFLOW_PATTERN = {
    "steps": [
        "discover_resources",      # Find all resources of this type
        "collect_metrics",         # Get usage/performance data
        "check_policy_compliance", # Check against company policies
        "analyze_optimization",    # Determine what to optimize
        "apply_optimization",      # Make actual changes
        "verify_optimization"      # Confirm changes worked
    ]
}

# Service-Specific Workflows
MULTI_SERVICE_WORKFLOWS = {
    
    # EC2 Instance Optimization (Already Implemented)
    "ec2_optimization": {
        "service": "EC2",
        "description": "Optimize EC2 instances based on policy and metrics",
        "steps": [
            {
                "name": "discover_instances",
                "handler": "ec2.discover_instances",
                "collects": ["instance_id", "instance_type", "state", "tags"]
            },
            {
                "name": "collect_usage_metrics",
                "handler": "ec2.collect_metrics",
                "metrics": ["cpu_utilization", "network_io", "disk_io"],
                "lookback_hours": 24
            },
            {
                "name": "analyze_optimization",
                "handler": "ec2.analyze",
                "checks": ["policy_compliance", "utilization_metrics"],
                "policies": ["disallowed_instance_types", "max_instance_size"]
            },
            {
                "name": "apply_rightsizing",
                "handler": "ec2.rightsize",
                "actions": ["stop", "modify_instance_type", "start"],
                "validation": "check_state_after_each_action"
            },
            {
                "name": "verify_optimization",
                "handler": "ec2.verify",
                "verifies": ["instance_running", "type_changed", "reachable"]
            }
        ]
    },
    
    # RDS Database Optimization
    "rds_optimization": {
        "service": "RDS",
        "description": "Optimize RDS databases for cost and performance",
        "steps": [
            {
                "name": "discover_databases",
                "handler": "rds.discover",
                "collects": ["db_instance_id", "db_instance_class", "engine", "multi_az", "storage_type", "allocated_storage"]
            },
            {
                "name": "collect_performance_insights",
                "handler": "rds.collect_metrics",
                "metrics": ["cpu_utilization", "connections", "iops", "read_latency", "write_latency"],
                "lookback_hours": 168  # 7 days
            },
            {
                "name": "analyze_optimization",
                "handler": "rds.analyze",
                "checks": [
                    "policy_compliance",  # Check against allowed instance classes
                    "multi_az_necessity",  # Is Multi-AZ actually needed?
                    "storage_type_efficiency",  # gp3 vs io1/io2
                    "over_provisioned_storage",  # Allocated vs used storage
                    "backup_retention_policy"  # Too many backups?
                ],
                "policies": ["disallowed_instance_classes", "multi_az_policy", "storage_policy", "backup_retention"]
            },
            {
                "name": "apply_optimization",
                "handler": "rds.optimize",
                "actions": [
                    "modify_instance_class",  # Downsize if oversized
                    "disable_multi_az",  # If policy allows and not critical
                    "change_storage_type",  # io1 → gp3
                    "reduce_allocated_storage",  # Shrink if over-provisioned
                    "adjust_backup_retention"  # Reduce retention days
                ],
                "requires_maintenance_window": True,
                "apply_immediately": False  # RDS changes often need maintenance window
            },
            {
                "name": "verify_optimization",
                "handler": "rds.verify",
                "verifies": ["database_available", "class_changed", "connections_working"]
            }
        ]
    },
    
    # Lambda Function Optimization
    "lambda_optimization": {
        "service": "Lambda",
        "description": "Optimize Lambda functions for cost and performance",
        "steps": [
            {
                "name": "discover_functions",
                "handler": "lambda.discover",
                "collects": ["function_name", "function_arn", "runtime", "memory_size", "timeout", "reserved_concurrency"]
            },
            {
                "name": "collect_metrics",
                "handler": "lambda.collect_metrics",
                "metrics": ["invocations", "duration", "errors", "throttles", "concurrent_executions"],
                "lookback_days": 30
            },
            {
                "name": "analyze_optimization",
                "handler": "lambda.analyze",
                "checks": [
                    "timeout_policy",  # Max 300s per policy
                    "reserved_concurrency_policy",  # Max 100 per policy
                    "over_provisioned_memory",  # Memory too high for actual usage
                    "unused_functions"  # No invocations in 30 days
                ],
                "policies": ["max_timeout", "max_reserved_concurrency"]
            },
            {
                "name": "apply_optimization",
                "handler": "lambda.optimize",
                "actions": [
                    "reduce_timeout",  # If completion time is consistently low
                    "reduce_reserved_concurrency",  # If not hitting limits
                    "tag_for_deletion"  # If unused for 30+ days
                ],
                "no_downtime": True  # Lambda changes are instant
            },
            {
                "name": "verify_optimization",
                "handler": "lambda.verify",
                "verifies": ["function_available", "settings_updated", "test_invocation"]
            }
        ]
    },
    
    # EBS Volume Optimization
    "ebs_optimization": {
        "service": "EBS",
        "description": "Optimize EBS volumes for cost",
        "steps": [
            {
                "name": "discover_volumes",
                "handler": "ebs.discover",
                "collects": ["volume_id", "volume_type", "size", "state", "attachments", "iops"],
                "focus": ["unattached_volumes", "over_provisioned_iops"]
            },
            {
                "name": "collect_metrics",
                "handler": "ebs.collect_metrics",
                "metrics": ["read_ops", "write_ops", "read_bytes", "write_bytes"],
                "lookback_days": 7
            },
            {
                "name": "analyze_optimization",
                "handler": "ebs.analyze",
                "checks": [
                    "unattached_volumes",  # Volumes not attached to instances
                    "volume_type_policy",  # io1/io2 → gp3
                    "over_provisioned_iops",  # Provisioned IOPS not being used
                    "unused_snapshots"  # Old snapshots to delete
                ],
                "policies": ["disallowed_volume_types", "unattached_volume_age", "snapshot_retention"]
            },
            {
                "name": "apply_optimization",
                "handler": "ebs.optimize",
                "actions": [
                    "snapshot_and_delete_unattached",  # Unattached > 7 days
                    "modify_volume_type",  # io1 → gp3
                    "reduce_provisioned_iops",  # Lower IOPS if not used
                    "delete_old_snapshots"  # Older than retention policy
                ],
                "safety": "create_snapshot_before_delete"
            },
            {
                "name": "verify_optimization",
                "handler": "ebs.verify",
                "verifies": ["volumes_modified", "snapshots_created", "deletions_confirmed"]
            }
        ]
    },
    
    # S3 Bucket Optimization
    "s3_optimization": {
        "service": "S3",
        "description": "Optimize S3 buckets for cost efficiency",
        "steps": [
            {
                "name": "discover_buckets",
                "handler": "s3.discover",
                "collects": ["bucket_name", "region", "storage_class", "versioning", "lifecycle_policy"]
            },
            {
                "name": "analyze_storage",
                "handler": "s3.analyze_storage",
                "analyzes": ["total_size", "storage_class_distribution", "object_age_distribution"]
            },
            {
                "name": "analyze_optimization",
                "handler": "s3.analyze",
                "checks": [
                    "lifecycle_policy_exists",  # Should have lifecycle rules
                    "storage_class_compliance",  # STANDARD → Intelligent-Tiering
                    "versioning_limits",  # Too many versions?
                    "old_objects",  # Objects > 90 days in STANDARD
                    "incomplete_multipart_uploads"  # Cleanup incomplete uploads
                ],
                "policies": ["storage_class_policy", "lifecycle_required", "version_limits"]
            },
            {
                "name": "apply_optimization",
                "handler": "s3.optimize",
                "actions": [
                    "create_lifecycle_policy",  # Transition to IA/Glacier
                    "enable_intelligent_tiering",  # Auto-optimize
                    "delete_old_versions",  # Reduce version count
                    "cleanup_incomplete_uploads"  # Remove incomplete multipart
                ],
                "non_destructive": True  # Don't delete data, just transition
            },
            {
                "name": "verify_optimization",
                "handler": "s3.verify",
                "verifies": ["lifecycle_policy_active", "storage_class_changes_pending"]
            }
        ]
    },
    
    # ElastiCache Optimization
    "elasticache_optimization": {
        "service": "ElastiCache",
        "description": "Optimize ElastiCache clusters for cost",
        "steps": [
            {
                "name": "discover_clusters",
                "handler": "elasticache.discover",
                "collects": ["cluster_id", "node_type", "num_nodes", "engine", "engine_version"]
            },
            {
                "name": "collect_metrics",
                "handler": "elasticache.collect_metrics",
                "metrics": ["cpu_utilization", "evictions", "cache_hits", "cache_misses", "connections"],
                "lookback_days": 7
            },
            {
                "name": "analyze_optimization",
                "handler": "elasticache.analyze",
                "checks": [
                    "node_type_policy",  # r5/m5 → t3
                    "over_provisioned_nodes",  # Too many nodes for load
                    "low_cache_hit_rate",  # Not being used effectively
                    "unused_clusters"  # Very low connection count
                ],
                "policies": ["disallowed_node_types", "max_nodes_per_cluster"]
            },
            {
                "name": "apply_optimization",
                "handler": "elasticache.optimize",
                "actions": [
                    "modify_node_type",  # Downsize expensive nodes
                    "reduce_node_count",  # Fewer nodes if over-provisioned
                    "tag_unused_for_deletion"  # Flag barely-used clusters
                ],
                "requires_maintenance": True
            },
            {
                "name": "verify_optimization",
                "handler": "elasticache.verify",
                "verifies": ["cluster_available", "node_type_changed", "connections_working"]
            }
        ]
    },
    
    # Unified Multi-Service Workflow
    "comprehensive_optimization": {
        "service": "ALL",
        "description": "Comprehensive optimization across all AWS services",
        "steps": [
            {
                "name": "discover_all_resources",
                "handler": "multi.discover",
                "discovers": ["ec2", "rds", "lambda", "ebs", "s3", "elasticache"],
                "parallel": True  # Discover all services in parallel
            },
            {
                "name": "analyze_all_policies",
                "handler": "multi.analyze",
                "checks": "all_policies",
                "parallel_per_service": True
            },
            {
                "name": "prioritize_optimizations",
                "handler": "multi.prioritize",
                "prioritizes_by": ["policy_violations", "estimated_savings", "risk_level"],
                "output": "ranked_recommendations"
            },
            {
                "name": "apply_optimizations",
                "handler": "multi.apply",
                "applies": "all_services",
                "sequential": True,  # One service at a time for safety
                "order": ["ebs", "s3", "lambda", "elasticache", "ec2", "rds"]  # Least risky first
            },
            {
                "name": "verify_all",
                "handler": "multi.verify",
                "verifies": "all_modified_resources",
                "parallel": True
            }
        ]
    }
}


# Workflow Registry - Maps action names to workflow definitions
WORKFLOW_REGISTRY = {
    "optimize_ec2": "ec2_optimization",
    "optimize_rds": "rds_optimization",
    "optimize_lambda": "lambda_optimization",
    "optimize_ebs": "ebs_optimization",
    "optimize_s3": "s3_optimization",
    "optimize_elasticache": "elasticache_optimization",
    "optimize_all": "comprehensive_optimization",
    "optimize_existing_instances": "ec2_optimization"  # Alias for backward compatibility
}


def get_workflow_for_service(service: str) -> dict:
    """Get the workflow definition for a specific service."""
    workflow_key = WORKFLOW_REGISTRY.get(f"optimize_{service.lower()}")
    if workflow_key:
        return MULTI_SERVICE_WORKFLOWS.get(workflow_key, {})
    return {}


def get_all_optimizable_services() -> list:
    """Get list of all services that have optimization workflows."""
    return ["ec2", "rds", "lambda", "ebs", "s3", "elasticache"]


