from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Tuple

from botocore.exceptions import BotoCoreError, ClientError

from . import aws

ResourceType = str

DEFAULT_RESOURCE_TYPES: Tuple[ResourceType, ...] = (
    "ec2",
    "auto-scaling",
    "ebs",
    "rds",
    "lambda",
)


def rightsizing_summary(
    resource_types: Optional[Iterable[str]] = None,
    *,
    account_ids: Optional[Iterable[str]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Aggregate Compute Optimizer recommendations across resource classes."""

    resolved_types = _normalise_resource_types(resource_types) or list(DEFAULT_RESOURCE_TYPES)
    client = aws.client("compute-optimizer")

    results: Dict[str, List[Dict[str, Any]]] = {}
    warnings: List[str] = []
    total_savings = 0.0
    savings_percentages: List[float] = []
    total_count = 0

    for resource_type in resolved_types:
        definition = _RESOURCE_DEFINITIONS.get(resource_type)
        if not definition:
            warnings.append(f"Unsupported resource type '{resource_type}'")
            continue

        if not hasattr(client, definition.api_name):
            warnings.append(
                f"{resource_type} recommendations are not available in this environment "
                f"(missing compute-optimizer.{definition.api_name})"
            )
            continue
        try:
            raw_recommendations = _paginate_recommendations(
                client,
                api_name=definition.api_name,
                response_key=definition.response_key,
                limit=limit,
                extra_args=_build_common_args(account_ids),
            )
        except (ClientError, BotoCoreError) as exc:
            warnings.append(f"{resource_type} recommendations unavailable: {exc}")
            continue

        formatted = [definition.formatter(item) for item in raw_recommendations if item]
        if not formatted:
            continue

        results[resource_type] = formatted
        total_count += len(formatted)
        for entry in formatted:
            savings = entry.get("estimatedMonthlySavings") or {}
            total_savings += savings.get("amount") or 0.0
            savings_opportunity = entry.get("savingsOpportunity") or {}
            pct = savings_opportunity.get("percentage")
            if pct is not None:
                savings_percentages.append(pct)

    summary: Dict[str, Any] = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "resourceTypes": resolved_types,
        "totalRecommendations": total_count,
        "totalEstimatedMonthlySavings": round(total_savings, 2),
    }

    if savings_percentages:
        summary["averageSavingsOpportunityPct"] = round(sum(savings_percentages) / len(savings_percentages), 2)

    response: Dict[str, Any] = {
        "summary": summary,
        "resources": results,
    }
    if warnings:
        response["warnings"] = warnings
    return response


def _build_common_args(account_ids: Optional[Iterable[str]]) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    accounts = [acc for acc in (account_ids or []) if acc]
    if accounts:
        args["accountIds"] = accounts
    return args


def _paginate_recommendations(
    client,
    *,
    api_name: str,
    response_key: str,
    limit: int,
    extra_args: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    method = getattr(client, api_name)
    collected: List[Dict[str, Any]] = []
    next_token: Optional[str] = None

    while True:
        request_args: Dict[str, Any] = {"maxResults": min(limit, 100)}
        if next_token:
            request_args["nextToken"] = next_token
        if extra_args:
            request_args.update(extra_args)
        response = method(**request_args)
        collected.extend(response.get(response_key, []))
        next_token = response.get("nextToken")
        if not next_token or len(collected) >= limit:
            break

    return collected[:limit]


def _normalise_resource_types(resource_types: Optional[Iterable[str]]) -> List[str]:
    if not resource_types:
        return []
    normalised = []
    for raw in resource_types:
        if not raw:
            continue
        key = raw.strip().lower()
        if key in {"autoscaling", "asg"}:
            key = "auto-scaling"
        normalised.append(key)
    return normalised


def _format_savings_opportunity(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not payload:
        return None
    if "estimatedMonthlySavings" in payload:
        amount, currency = _extract_amount(payload["estimatedMonthlySavings"])
    elif "savingsAmount" in payload:
        amount, currency = _extract_amount(payload["savingsAmount"])
    else:
        amount, currency = (None, None)
    percentage = payload.get("savingsOpportunityPercentage") or payload.get("estimatedSavingsPercentage")
    formatted = {
        "amount": amount,
        "currency": currency or "USD",
        "percentage": round(float(percentage), 2) if percentage is not None else None,
    }
    if formatted["amount"] is None and formatted["percentage"] is None:
        return None
    return formatted


def _format_utilization(metrics: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    formatted = []
    for metric in metrics or []:
        formatted.append(
            {
                "name": metric.get("name"),
                "statistic": metric.get("statistic"),
                "value": _to_float(metric.get("value")),
            }
        )
    return formatted


def _extract_amount(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    if payload is None:
        return None, None
    if isinstance(payload, dict):
        currency = payload.get("currency") or payload.get("Currency")
        value = payload.get("value") or payload.get("amount") or payload.get("Amount")
        amount = _to_float(value)
        return (round(amount, 2), currency)
    return None, None


def _ts(value: Any) -> Optional[str]:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.timezone.utc).isoformat()
    return str(value) if value else None


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class _ResourceDefinition:
    def __init__(self, api_name: str, response_key: str, formatter):
        self.api_name = api_name
        self.response_key = response_key
        self.formatter = formatter


def _format_ec2(rec: Dict[str, Any]) -> Dict[str, Any]:
    options = [_format_ec2_option(opt) for opt in rec.get("recommendationOptions", [])]
    primary = _select_primary_option(options)
    savings = primary.get("savings") if primary else None
    opportunity = _format_savings_opportunity(rec.get("savingsOpportunity"))

    return {
        "resourceArn": rec.get("instanceArn"),
        "resourceName": rec.get("instanceName"),
        "accountId": rec.get("accountId"),
        "finding": rec.get("finding"),
        "findingReasonCodes": rec.get("findingReasonCodes", []),
        "currentConfiguration": {
            "instanceType": rec.get("currentInstanceType"),
            "platform": rec.get("platformDetails"),
        },
        "utilization": _format_utilization(rec.get("utilizationMetrics")),
        "recommendations": options,
        "estimatedMonthlySavings": savings,
        "savingsOpportunity": opportunity,
        "performanceRisk": _to_float(rec.get("currentPerformanceRisk")),
        "lookbackPeriodInDays": rec.get("lookBackPeriodInDays"),
        "lastRefresh": _ts(rec.get("lastRefreshTimestamp")),
    }


def _format_ec2_option(option: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "instanceType": option.get("instanceType"),
        "rank": option.get("rank"),
        "performanceRisk": _to_float(option.get("performanceRisk")),
        "platformDifferences": option.get("platformDifferences", []),
        "projectedUtilization": _format_utilization(option.get("projectedUtilizationMetrics")),
        "savings": _format_savings_opportunity(option.get("savingsOpportunity")),
    }


def _format_auto_scaling(rec: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for option in rec.get("recommendationOptions", []):
        options.append(
            {
                "configuration": option.get("configuration"),
                "projectedUtilization": _format_utilization(option.get("projectedUtilizationMetrics")),
                "performanceRisk": _to_float(option.get("performanceRisk")),
                "rank": option.get("rank"),
                "savings": _format_savings_opportunity(option.get("savingsOpportunity")),
            }
        )
    primary = _select_primary_option(options)
    return {
        "resourceArn": rec.get("autoScalingGroupArn"),
        "resourceName": rec.get("autoScalingGroupName"),
        "accountId": rec.get("accountId"),
        "finding": rec.get("finding"),
        "utilization": _format_utilization(rec.get("utilizationMetrics")),
        "currentConfiguration": rec.get("currentConfiguration"),
        "recommendations": options,
        "estimatedMonthlySavings": primary.get("savings") if primary else None,
        "savingsOpportunity": _format_savings_opportunity(rec.get("savingsOpportunity")),
        "lookbackPeriodInDays": rec.get("lookBackPeriodInDays"),
        "lastRefresh": _ts(rec.get("lastRefreshTimestamp")),
    }


def _format_ebs(rec: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for option in rec.get("volumeRecommendationOptions", []):
        options.append(
            {
                "configuration": option.get("configuration"),
                "performanceRisk": _to_float(option.get("performanceRisk")),
                "rank": option.get("rank"),
                "savings": _format_savings_opportunity(option.get("savingsOpportunity")),
            }
        )
    primary = _select_primary_option(options)
    return {
        "resourceArn": rec.get("volumeArn"),
        "resourceName": rec.get("volumeName"),
        "accountId": rec.get("accountId"),
        "finding": rec.get("finding"),
        "findingReasonCodes": rec.get("findingReasonCodes", []),
        "utilization": _format_utilization(rec.get("utilizationMetrics")),
        "currentConfiguration": rec.get("currentConfiguration"),
        "recommendations": options,
        "estimatedMonthlySavings": primary.get("savings") if primary else None,
        "savingsOpportunity": _format_savings_opportunity(rec.get("savingsOpportunity")),
        "lastRefresh": _ts(rec.get("lastRefreshTimestamp")),
    }


def _format_rds(rec: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for option in rec.get("recommendationOptions", []):
        options.append(
            {
                "instanceType": option.get("instanceType"),
                "rank": option.get("rank"),
                "performanceRisk": _to_float(option.get("performanceRisk")),
                "projectedUtilization": _format_utilization(option.get("projectedUtilizationMetrics")),
                "savings": _format_savings_opportunity(option.get("savingsOpportunity")),
            }
        )
    primary = _select_primary_option(options)
    return {
        "resourceArn": rec.get("rdsInstanceArn"),
        "resourceName": rec.get("rdsInstanceName"),
        "accountId": rec.get("accountId"),
        "finding": rec.get("finding"),
        "utilization": _format_utilization(rec.get("utilizationMetrics")),
        "currentConfiguration": rec.get("currentConfiguration"),
        "recommendations": options,
        "estimatedMonthlySavings": primary.get("savings") if primary else None,
        "savingsOpportunity": _format_savings_opportunity(rec.get("savingsOpportunity")),
        "lookbackPeriodInDays": rec.get("lookBackPeriodInDays"),
        "lastRefresh": _ts(rec.get("lastRefreshTimestamp")),
    }


def _format_lambda(rec: Dict[str, Any]) -> Dict[str, Any]:
    options = []
    for option in rec.get("functionRecommendationOptions", []):
        options.append(
            {
                "memorySize": option.get("memorySize"),
                "rank": option.get("rank"),
                "performanceRisk": _to_float(option.get("performanceRisk")),
                "projectedUtilization": _format_utilization(option.get("projectedUtilizationMetrics")),
                "savings": _format_savings_opportunity(option.get("savingsOpportunity")),
            }
        )
    primary = _select_primary_option(options)
    return {
        "resourceArn": rec.get("lambdaFunctionArn"),
        "functionVersion": rec.get("functionVersion"),
        "accountId": rec.get("accountId"),
        "finding": rec.get("finding"),
        "findingReasonCodes": rec.get("findingReasonCodes", []),
        "currentConfiguration": rec.get("currentConfiguration"),
        "recommendations": options,
        "estimatedMonthlySavings": primary.get("savings") if primary else None,
        "savingsOpportunity": _format_savings_opportunity(rec.get("savingsOpportunity")),
        "lookbackPeriodInDays": rec.get("lookBackPeriodInDays"),
        "lastRefresh": _ts(rec.get("lastRefreshTimestamp")),
    }


def _select_primary_option(options: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not options:
        return None
    return sorted(options, key=lambda opt: opt.get("rank") or 9999)[0]


_RESOURCE_DEFINITIONS: Dict[str, _ResourceDefinition] = {
    "ec2": _ResourceDefinition("get_ec2_instance_recommendations", "instanceRecommendations", _format_ec2),
    "auto-scaling": _ResourceDefinition("get_auto_scaling_group_recommendations", "autoScalingGroupRecommendations", _format_auto_scaling),
    "ebs": _ResourceDefinition("get_ebs_volume_recommendations", "volumeRecommendations", _format_ebs),
    "rds": _ResourceDefinition("get_rds_instance_recommendations", "rdsInstanceRecommendations", _format_rds),
    "lambda": _ResourceDefinition("get_lambda_function_recommendations", "lambdaFunctionRecommendations", _format_lambda),
}
