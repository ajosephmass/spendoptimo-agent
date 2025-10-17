"""
Company Cost Optimization Policies

This file defines the company's cost optimization and compliance policies
for various AWS services. These policies are used by the SpendOptimo agent
to make recommendations even when CloudWatch metrics are insufficient.
"""

COMPANY_COST_POLICIES = {
    "metadata": {
        "company_name": "SpendOptimo Demo Corp",
        "policy_version": "2025-Q1",
        "enforcement_level": "strict",  # strict, advisory, audit
        "effective_date": "2025-01-01",
        "description": "Cost optimization policies to ensure efficient AWS resource usage"
    },
    
    "ec2": {
        "disallowed_instance_types": [
            "r5.*",      # All R5 family (memory-optimized - expensive)
            "r5a.*",
            "r5b.*",
            "r5n.*",
            "r6i.*",
            "r6a.*",
            "m5.*",      # All M5 family (general purpose - expensive)
            "m5a.*",
            "m5n.*",
            "m6i.*",
            "c5.*",      # All C5 family (compute-optimized - expensive)
            "c5a.*",
            "c5n.*",
            "c6i.*",
            "t2.*",      # T2 family (older generation - prefer T3)
            "t3.large",
            "t3.xlarge",
            "t3.2xlarge"
        ],
        "recommended_types": ["t3.micro", "t3.small", "t3.medium"],
        "rationale": "Cost optimization - only T3 instance family up to medium size allowed. R5, M5, C5, and T2 families are not approved.",
        "exceptions": {
            "tags": {
                "Environment": ["production", "prod"],
                "CriticalWorkload": ["true"]
            }
        }
    },
    
    "rds": {
        "disallowed_instance_classes": [
            "db.r5.*",
            "db.r5b.*",
            "db.r6i.*",
            "db.m5.*",
            "db.m6i.*"
        ],
        "recommended_classes": ["db.t3.micro", "db.t3.small", "db.t3.medium"],
        "storage": {
            "max_provisioned_iops": 3000,
            "disallowed_storage_types": ["io1", "io2"],  # Provisioned IOPS - expensive
            "recommended_storage_type": "gp3",
            "max_allocated_storage_gb": 100
        },
        "rationale": "Database cost optimization - T3 instances are sufficient for most workloads. Use gp3 storage instead of provisioned IOPS.",
        "features": {
            "multi_az": {
                "allowed": False,
                "except_for_tags": ["production", "critical"],
                "rationale": "Multi-AZ doubles costs - only for critical workloads"
            },
            "backup_retention_days": {
                "max": 7,
                "recommended": 3,
                "rationale": "Limit backup storage costs"
            }
        }
    },
    
    "lambda": {
        "timeout": {
            "max_seconds": 300,
            "recommended_seconds": 60,
            "rationale": "Most functions should complete within 60s to avoid runaway costs"
        },
        "reserved_concurrency": {
            "max": 100,
            "rationale": "Prevent runaway costs from unlimited scaling"
        }
    },
    
    "ebs": {
        "disallowed_volume_types": ["io1", "io2"],  # Provisioned IOPS - expensive
        "recommended_types": ["gp3"],
        "max_volume_size_gb": 1000,
        "rationale": "gp3 provides good performance at lower cost than provisioned IOPS",
        "unattached_volume_policy": {
            "max_age_days": 7,
            "action": "snapshot_and_delete",
            "rationale": "Unattached volumes waste money - clean up after 7 days"
        }
    },
    
    "s3": {
        "storage_class": {
            "disallowed": ["STANDARD"],  # Force lifecycle transitions
            "recommended": ["INTELLIGENT_TIERING", "GLACIER_IR"],
            "rationale": "Use Intelligent-Tiering for automatic cost optimization"
        },
        "lifecycle_policy_required": True,
        "versioning": {
            "max_versions": 3,
            "rationale": "Limit storage costs from versioning - keep only 3 versions"
        }
    },
    
    "elasticache": {
        "disallowed_node_types": [
            "cache.r5.*",
            "cache.r6g.*",
            "cache.m5.*",
            "cache.m6g.*"
        ],
        "recommended_types": ["cache.t3.micro", "cache.t3.small", "cache.t3.medium"],
        "rationale": "T3 cache nodes are sufficient for most caching workloads"
    },
    
    "general": {
        "unused_resources": {
            "check_interval_days": 30,
            "action": "flag_for_deletion",
            "applies_to": ["ebs_volumes", "elastic_ips", "snapshots", "old_amis"],
            "rationale": "Regular cleanup of unused resources prevents cost accumulation"
        },
        "tagging_required": {
            "required_tags": ["Environment", "Owner", "CostCenter"],
            "rationale": "Proper tagging enables cost allocation and accountability"
        },
        "region_restrictions": {
            "allowed_regions": ["us-east-1", "us-west-2"],
            "rationale": "Standardize regions for better pricing and management"
        }
    }
}


def get_policy(service: str) -> dict:
    """Get policy for a specific service."""
    return COMPANY_COST_POLICIES.get(service, {})


def get_all_policies() -> dict:
    """Get all company policies."""
    return COMPANY_COST_POLICIES


def is_instance_type_allowed(instance_type: str, service: str = "ec2") -> bool:
    """Check if an instance type is allowed by policy."""
    import re
    
    policy = get_policy(service)
    if not policy:
        return True
    
    disallowed = policy.get("disallowed_instance_types", [])
    
    for pattern in disallowed:
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
        if re.match(f"^{regex_pattern}$", instance_type):
            return False
    
    return True


def get_recommended_type(current_type: str, service: str = "ec2") -> str:
    """Get recommended instance type based on policy."""
    policy = get_policy(service)
    if not policy:
        return current_type
    
    recommended = policy.get("recommended_types", [])
    if recommended:
        # Return the medium size as a reasonable default
        if "t3.medium" in recommended:
            return "t3.medium"
        return recommended[0] if recommended else current_type
    
    return current_type


def get_policy_rationale(service: str) -> str:
    """Get the rationale for a service's policy."""
    policy = get_policy(service)
    return policy.get("rationale", "Company cost optimization policy")

