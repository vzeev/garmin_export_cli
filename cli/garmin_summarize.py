#!/usr/bin/env python3
"""Build ignored training summaries from raw Garmin exports."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from garmin_storage import RAW_DIR, SUMMARY_DERIVED_DIR, read_json, write_json


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def number(payload: dict[str, Any], *keys: str) -> float:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, int | float):
            return float(value)
    return 0.0


def add_metric(bucket: dict[str, Any], key: str, value: float) -> None:
    bucket[key] = float(bucket.get(key, 0.0)) + value


def iter_month_dirs() -> list[Path]:
    if not RAW_DIR.exists():
        return []
    return sorted(path for path in RAW_DIR.glob("*/*") if path.is_dir())


def collect_weight(month_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(month_dir / "performance_and_weight.json", default={})
    data = payload.get("weigh_ins", {}).get("data", {})
    summaries = data.get("dailyWeightSummaries") or []
    rows: list[dict[str, Any]] = []
    for item in summaries:
        latest = item.get("latestWeight") or {}
        weight = latest.get("weight")
        day = latest.get("calendarDate") or item.get("summaryDate")
        if isinstance(weight, int | float) and day:
            rows.append({"date": day, "weight_kg": round(weight / 1000, 2)})
    return rows


def collect_activities(month_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(month_dir / "activities.json", default={})
    if not payload.get("ok"):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        day = parse_day(item.get("startTimeLocal") or item.get("startTimeGMT"))
        if not day:
            continue
        rows.append(
            {
                "date": day.isoformat(),
                "name": item.get("activityName"),
                "type": (item.get("activityType") or {}).get("typeKey"),
                "distance_km": round(number(item, "distance") / 1000, 2),
                "duration_h": round(
                    number(item, "duration", "movingDuration", "elapsedDuration")
                    / 3600,
                    2,
                ),
                "elevation_m": round(number(item, "elevationGain", "elevationGainInMeters"), 1),
                "avg_hr": item.get("averageHR") or item.get("avgHR"),
                "avg_power": item.get("avgPower") or item.get("averagePower"),
                "weighted_power": item.get("weightedAvgPower"),
            }
        )
    return rows


def collect_latest_ftp(month_dir: Path) -> dict[str, Any] | None:
    payload = read_json(month_dir / "performance_and_weight.json", default={})
    data = payload.get("cycling_ftp", {}).get("data")
    if not isinstance(data, dict):
        return None
    ftp = data.get("functionalThresholdPower")
    if not isinstance(ftp, int | float):
        return None
    return {
        "calendar_date": data.get("calendarDate"),
        "ftp_w": ftp,
        "is_stale": data.get("isStale"),
    }


def summarize() -> dict[str, Any]:
    activities: list[dict[str, Any]] = []
    weights: list[dict[str, Any]] = []
    ftp_rows: list[dict[str, Any]] = []

    for month_dir in iter_month_dirs():
        activities.extend(collect_activities(month_dir))
        weights.extend(collect_weight(month_dir))
        ftp = collect_latest_ftp(month_dir)
        if ftp:
            ftp_rows.append(ftp)

    weekly: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"activity_count": 0, "distance_km": 0.0, "duration_h": 0.0, "elevation_m": 0.0}
    )
    monthly: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"activity_count": 0, "distance_km": 0.0, "duration_h": 0.0, "elevation_m": 0.0}
    )

    for activity in activities:
        day = datetime.strptime(activity["date"], "%Y-%m-%d").date()
        week_key = f"{day.isocalendar().year}-W{day.isocalendar().week:02d}"
        month_key = activity["date"][:7]
        for bucket in (weekly[week_key], monthly[month_key]):
            bucket["activity_count"] += 1
            add_metric(bucket, "distance_km", activity["distance_km"])
            add_metric(bucket, "duration_h", activity["duration_h"])
            add_metric(bucket, "elevation_m", activity["elevation_m"])

    latest_weight = sorted(weights, key=lambda row: row["date"])[-1] if weights else None
    latest_ftp = sorted(ftp_rows, key=lambda row: str(row.get("calendar_date")))[-1] if ftp_rows else None
    latest_activity = sorted(activities, key=lambda row: row["date"])[-1] if activities else None

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "activity_count": len(activities),
        "weight_entry_count": len(weights),
        "latest_activity": latest_activity,
        "latest_weight": latest_weight,
        "latest_ftp": latest_ftp,
        "weekly_summary": dict(sorted(weekly.items())),
        "monthly_summary": dict(sorted(monthly.items())),
    }


def write_markdown(summary: dict[str, Any]) -> None:
    latest_activity = summary.get("latest_activity") or {}
    latest_weight = summary.get("latest_weight") or {}
    latest_ftp = summary.get("latest_ftp") or {}
    lines = [
        "# Garmin Training Context",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Current Baseline",
        "",
        f"- Activities in raw export set: {summary['activity_count']}",
        f"- Weight entries in raw export set: {summary['weight_entry_count']}",
        f"- Latest activity date: {latest_activity.get('date', 'n/a')}",
        f"- Latest weight: {latest_weight.get('weight_kg', 'n/a')} kg",
        f"- Latest cycling FTP: {latest_ftp.get('ftp_w', 'n/a')} W",
        "",
        "## Boundary",
        "",
        "This is an ignored derived summary. Promote only reviewed conclusions into project notes.",
        "",
    ]
    (SUMMARY_DERIVED_DIR / "latest_training_context.md").parent.mkdir(
        parents=True, exist_ok=True
    )
    (SUMMARY_DERIVED_DIR / "latest_training_context.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> int:
    summary = summarize()
    write_json(SUMMARY_DERIVED_DIR / "current_baseline.json", summary)
    write_json(SUMMARY_DERIVED_DIR / "weekly_summary.json", summary["weekly_summary"])
    write_json(SUMMARY_DERIVED_DIR / "monthly_summary.json", summary["monthly_summary"])
    write_markdown(summary)
    print(f"Garmin summaries written to: {SUMMARY_DERIVED_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
