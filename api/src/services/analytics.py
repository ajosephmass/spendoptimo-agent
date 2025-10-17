from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from botocore.exceptions import BotoCoreError, ClientError

from . import aws

_DEFAULT_GROUP = ["SERVICE"]
_SUPPORTED_GRANULARITY = {"DAILY", "MONTHLY"}


def analyze_cost(
    days: int = 7,
    *,
    granularity: str = "DAILY",
    group_by: Optional[Iterable[str]] = None,
    filter_dimension: Optional[str] = None,
    filter_value: Optional[str] = None,
    include_forecast: bool = True,
    include_anomalies: bool = True,
    include_savings: bool = True,
) -> Dict[str, Any]:
    """Return cost drivers, anomalies, coverage, and forecast for the requested window."""

    if days <= 0:
        raise ValueError("days must be a positive integer")

    granularity_key = granularity.upper()
    if granularity_key not in _SUPPORTED_GRANULARITY:
        raise ValueError(f"Unsupported granularity '{granularity}'. Use one of {_SUPPORTED_GRANULARITY}.")

    ce = aws.client("ce")
    today = dt.date.today()
    period_end = today  # Cost Explorer end date is exclusive; today gives latest full day.
    current_start = period_end - dt.timedelta(days=days)
    lookback_start = current_start - dt.timedelta(days=days)

    # Cost Explorer allows up to two group-by dimensions; normalise inputs.
    group_keys = _normalise_group_keys(group_by)
    filter_expression = _build_filter(filter_dimension, filter_value)

    # Pull two windows so we can compute period-over-period deltas.
    usage_results = _fetch_cost_and_usage(
        ce,
        start=lookback_start,
        end=period_end,
        granularity=granularity_key,
        group_keys=group_keys,
        metrics=["UnblendedCost"],
        filter_expression=filter_expression,
    )

    period_count = _determine_period_count(days, granularity_key, len(usage_results))
    current_period = usage_results[-period_count:] if usage_results else []
    previous_period = usage_results[-(period_count * 2):-period_count] if len(usage_results) >= period_count * 2 else usage_results[: len(usage_results) - period_count]

    currency = _detect_currency(current_period, previous_period)
    current_total = _sum_results(current_period)
    previous_total = _sum_results(previous_period)
    percentage_change = _percentage_delta(previous_total, current_total)
    average_daily = current_total / max(1, period_count)

    group_aggregates_current = _aggregate_groups(current_period)
    group_aggregates_previous = _aggregate_groups(previous_period)

    top_contributors = _format_group_totals(group_aggregates_current, currency)
    biggest_risers = _format_group_deltas(group_aggregates_current, group_aggregates_previous, currency, descending=True)
    biggest_declines = _format_group_deltas(group_aggregates_current, group_aggregates_previous, currency, descending=False)

    trend = _format_trend(current_period, currency)

    warnings: List[str] = []
    forecast = coverage = anomalies = None

    if include_forecast:
        forecast = _safe_forecast(ce, period_end, granularity_key, days, filter_expression, warnings)

    if include_savings:
        coverage = _collect_coverage(ce, current_start, period_end, warnings)

    if include_anomalies:
        anomalies = _collect_anomalies(ce, current_start, period_end, warnings)

    response: Dict[str, Any] = {
        "period": {
            "start": current_start.isoformat(),
            "end": period_end.isoformat(),
            "lookbackStart": lookback_start.isoformat(),
            "granularity": granularity_key,
            "dataPoints": period_count,
        },
        "groupBy": group_keys or [],
        "filter": _format_filter_metadata(filter_dimension, filter_value),
        "summary": {
            "currency": currency,
            "totalSpend": round(current_total, 2),
            "previousTotalSpend": round(previous_total, 2) if previous_period else None,
            "periodOverPeriodChangePct": percentage_change,
            "averagePerDataPoint": round(average_daily, 2),
        },
        "topContributors": top_contributors[:10],
        "biggestMovers": {
            "risers": biggest_risers[:5],
            "decliners": biggest_declines[:5],
        },
        "trend": trend,
    }

    if forecast:
        response["forecast"] = forecast
    if coverage:
        response["coverage"] = coverage
    if anomalies:
        response["anomalies"] = anomalies
    if warnings:
        response["warnings"] = warnings

    return response


def _fetch_cost_and_usage(
    client,
    *,
    start: dt.date,
    end: dt.date,
    granularity: str,
    group_keys: List[Dict[str, str]],
    metrics: List[str],
    filter_expression: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    kwargs: Dict[str, Any] = {
        "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
        "Granularity": granularity,
        "Metrics": metrics,
    }
    if group_keys:
        kwargs["GroupBy"] = group_keys
    if filter_expression:
        kwargs["Filter"] = filter_expression

    try:
        response = client.get_cost_and_usage(**kwargs)
    except (ClientError, BotoCoreError) as exc:
        raise RuntimeError(f"Failed to query Cost Explorer: {exc}") from exc
    return response.get("ResultsByTime", [])


def _determine_period_count(days: int, granularity: str, available_points: int) -> int:
    if available_points == 0:
        return 0
    if granularity == "DAILY":
        return min(days, available_points)
    # Monthly granularity: approximate number of months requested.
    months_requested = max(1, math.ceil(days / 30))
    return min(months_requested, available_points)


def _sum_results(results: Iterable[Dict[str, Any]]) -> float:
    total = 0.0
    for item in results:
        total += _to_float(item.get("Total", {}).get("UnblendedCost", {}).get("Amount"))
    return total


def _aggregate_groups(results: Iterable[Dict[str, Any]]) -> Dict[str, float]:
    aggregates: Dict[str, float] = defaultdict(float)
    for item in results:
        for group in item.get("Groups", []):
            keys = group.get("Keys") or ["Unknown"]
            label = " · ".join(keys)
            amount = _to_float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount"))
            aggregates[label] += amount
    return aggregates


def _format_group_totals(group_totals: Dict[str, float], currency: str) -> List[Dict[str, Any]]:
    ordered = sorted(group_totals.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"label": label, "amount": round(amount, 2), "currency": currency}
        for label, amount in ordered
        if amount > 0.0
    ]


def _format_group_deltas(
    current: Dict[str, float],
    previous: Dict[str, float],
    currency: str,
    *,
    descending: bool,
) -> List[Dict[str, Any]]:
    movers: List[Tuple[str, float, float]] = []
    keys = set(current) | set(previous)
    for key in keys:
        current_amount = current.get(key, 0.0)
        previous_amount = previous.get(key, 0.0)
        if current_amount == previous_amount:
            continue
        delta = current_amount - previous_amount
        pct = _percentage_delta(previous_amount, current_amount)
        movers.append((key, delta, pct or 0.0))

    movers.sort(key=lambda item: item[1], reverse=descending)
    result = []
    for label, amount_delta, pct in movers:
        if descending and amount_delta <= 0:
            continue
        if not descending and amount_delta >= 0:
            continue
        result.append(
            {
                "label": label,
                "amountDelta": round(amount_delta, 2),
                "currency": currency,
                "percentageChange": round(pct, 2) if pct is not None else None,
            }
        )
    return result


def _format_trend(results: Iterable[Dict[str, Any]], currency: str) -> List[Dict[str, Any]]:
    trend = []
    previous_amount = None
    for item in results:
        amount = _to_float(item.get("Total", {}).get("UnblendedCost", {}).get("Amount"))
        pct = None if previous_amount is None else _percentage_delta(previous_amount, amount)
        trend.append(
            {
                "timestamp": item.get("TimePeriod", {}).get("Start"),
                "amount": round(amount, 2),
                "currency": currency,
                "percentageChange": round(pct, 2) if pct is not None else None,
            }
        )
        previous_amount = amount
    return trend


def _safe_forecast(client, end: dt.date, granularity: str, days: int, filter_expression: Optional[Dict[str, Any]], warnings: List[str]):
    future_days = max(7, min(60, days))
    forecast_end = end + dt.timedelta(days=future_days)
    kwargs: Dict[str, Any] = {
        "TimePeriod": {"Start": end.isoformat(), "End": forecast_end.isoformat()},
        "Granularity": granularity,
        "Metric": "UNBLENDED_COST",
        "PredictionIntervalLevel": 80,
    }
    if filter_expression:
        kwargs["Filter"] = filter_expression
    try:
        response = client.get_cost_forecast(**kwargs)
    except (ClientError, BotoCoreError) as exc:
        warnings.append(f"Unable to retrieve forecast: {exc}")
        return None

    points = []
    total_amount = 0.0
    for entry in response.get("ForecastResultsByTime", []):
        mean = _to_float(entry.get("MeanValue"))
        points.append(
            {
                "timestamp": entry.get("Timestamp"),
                "amount": round(mean, 2),
                "currency": entry.get("Unit", "USD"),
            }
        )
        total_amount += mean

    if not points:
        return None

    return {
        "period": {"start": end.isoformat(), "end": forecast_end.isoformat()},
        "total": round(total_amount, 2),
        "currency": points[0]["currency"],
        "points": points,
    }


def _collect_coverage(client, start: dt.date, end: dt.date, warnings: List[str]):
    coverage: Dict[str, Any] = {}
    try:
        sp = client.get_savings_plans_coverage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
        )
        parsed_sp = _parse_savings_plans_coverage(sp.get("SavingsPlansCoverages", []))
        if any(value is not None for value in parsed_sp.values()):
            coverage["savingsPlans"] = parsed_sp
    except (ClientError, BotoCoreError) as exc:
        warnings.append(f"Savings Plans coverage unavailable: {exc}")

    try:
        ri = client.get_reservation_coverage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            Granularity="DAILY",
        )
        parsed_ri = _parse_reservation_coverage(ri.get("CoveragesByTime", []))
        if any(value is not None for value in parsed_ri.values()):
            coverage["reservedInstances"] = parsed_ri
    except (ClientError, BotoCoreError) as exc:
        warnings.append(f"Reserved Instance coverage unavailable: {exc}")

    return coverage or None


def _collect_anomalies(client, start: dt.date, end: dt.date, warnings: List[str]):
    try:
        response = client.get_anomalies(
            DateInterval={"StartDate": start.isoformat(), "EndDate": end.isoformat()},
            MaxResults=10,
        )
    except (ClientError, BotoCoreError) as exc:
        warnings.append(f"Anomaly detection unavailable: {exc}")
        return None

    anomalies = []
    for anomaly in response.get("Anomalies", []):
        impact_total = anomaly.get("Impact", {}).get("TotalImpact", {})
        amount = _to_float(impact_total.get("Amount"))
        currency = impact_total.get("Unit", "USD")
        root_causes = []
        for root in anomaly.get("RootCauses", []):
            segments = [root.get("Service"), root.get("LinkedAccount"), root.get("UsageType")]
            root_causes.append(" / ".join(filter(None, segments)))

        anomalies.append(
            {
                "anomalyId": anomaly.get("AnomalyId"),
                "startDate": anomaly.get("StartDate"),
                "endDate": anomaly.get("EndDate"),
                "impactAmount": round(amount, 2),
                "currency": currency,
                "anomalyScore": anomaly.get("AnomalyScore", {}),
                "rootCauses": root_causes,
            }
        )

    return anomalies or None


def _normalise_group_keys(group_by: Optional[Iterable[str]]) -> List[Dict[str, str]]:
    if group_by is None:
        keys = list(_DEFAULT_GROUP)
    elif isinstance(group_by, str):
        keys = [item.strip() for item in group_by.split(",") if item.strip()]
    else:
        keys = [item.strip() for item in group_by if item and item.strip()]
        if not keys:
            keys = list(_DEFAULT_GROUP)
    parsed: List[Dict[str, str]] = []
    for raw in keys:
        if not raw:
            continue
        label = raw.strip()
        if not label:
            continue
        if label.lower().startswith("tag:"):
            parsed.append({"Type": "TAG", "Key": label.split(":", 1)[1]})
        else:
            parsed.append({"Type": "DIMENSION", "Key": label.upper()})
        if len(parsed) == 2:
            break
    return parsed


def _build_filter(dimension: Optional[str], value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not dimension or not value:
        return None
    dim = dimension.strip()
    val = value.strip()
    if not dim or not val:
        return None
    if dim.lower().startswith("tag:"):
        return {"Tags": {"Key": dim.split(":", 1)[1], "Values": [val]}}
    return {"Dimensions": {"Key": dim.upper(), "Values": [val]}}


def _detect_currency(*results_groups: Iterable[Dict[str, Any]]) -> str:
    for group in results_groups:
        for item in group:
            unit = item.get("Total", {}).get("UnblendedCost", {}).get("Unit")
            if unit:
                return unit
    return "USD"


def _percentage_delta(previous: float, current: float) -> Optional[float]:
    if previous == 0:
        return None if current == 0 else 100.0
    return ((current - previous) / previous) * 100.0


def _format_filter_metadata(dimension: Optional[str], value: Optional[str]) -> Optional[Dict[str, str]]:
    if not dimension or not value:
        return None
    return {"dimension": dimension, "value": value}


def _parse_savings_plans_coverage(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_hours = 0.0
    percentages = []
    for row in rows:
        coverage = row.get("Coverage") or {}
        coverage_hours = coverage.get("CoverageHours") or {}
        total_hours += _to_float(coverage_hours.get("TotalHours"))
        pct = _to_float(coverage.get("SavingsPlansCoveragePercentage"))
        if pct:
            percentages.append(pct)
    avg_pct = sum(percentages) / len(percentages) if percentages else None
    return {
        "totalHours": round(total_hours, 2) if total_hours else None,
        "averageCoveragePct": round(avg_pct, 2) if avg_pct is not None else None,
    }


def _parse_reservation_coverage(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_hours = 0.0
    percentages = []
    for row in rows:
        total = row.get("Total") or {}
        coverage_hours = total.get("CoverageHours") or {}
        total_hours += _to_float(coverage_hours.get("TotalHours") or coverage_hours.get("CoveredHours"))
        pct = (
            _to_float(total.get("CoverageHoursPercentage"))
            or _to_float(total.get("CoveragePercentage"))
        )
        if pct:
            percentages.append(pct)
    avg_pct = sum(percentages) / len(percentages) if percentages else None
    return {
        "totalHours": round(total_hours, 2) if total_hours else None,
        "averageCoveragePct": round(avg_pct, 2) if avg_pct is not None else None,
    }


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
