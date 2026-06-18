"""Storage helpers for Garmin exports.

Raw Garmin data is intentionally kept under ignored folders. Downstream notes
or agents should consume only reviewed summaries.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
EXPORTS_DIR = PROJECT_ROOT / "exports"
DEFAULT_EXPORT_DIR = EXPORTS_DIR
RAW_DIR = EXPORTS_DIR / "raw"
MANIFESTS_DIR = EXPORTS_DIR / "manifests"
DERIVED_DIR = PROJECT_ROOT / "derived"
SUMMARY_DERIVED_DIR = DERIVED_DIR / "training"
RIDEFASTER_DERIVED_DIR = DERIVED_DIR / "ridefaster"
WORKOUT_SYNC_STATE_PATH = RIDEFASTER_DERIVED_DIR / "workout_sync_state.json"
EXPORT_STATE_PATH = MANIFESTS_DIR / "export_state.json"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def month_output_dir(day: date) -> Path:
    return RAW_DIR / f"{day.year:04d}" / month_key(day)


def month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def month_end(day: date) -> date:
    if day.month == 12:
        next_month = date(day.year + 1, 1, 1)
    else:
        next_month = date(day.year, day.month + 1, 1)
    return next_month - timedelta(days=1)


def month_chunks(start: date, end: date) -> list[tuple[date, date]]:
    if end < start:
        raise ValueError("end date must be on or after start date")

    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(month_end(cursor), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def load_export_state() -> dict[str, Any]:
    return read_json(EXPORT_STATE_PATH, default={"exports": []})


def save_export_state(state: dict[str, Any]) -> None:
    write_json(EXPORT_STATE_PATH, state)


def record_export(
    *,
    start_date: date,
    end_date: date,
    activity_type: str | None,
    output_dir: Path,
    download_activities: bool,
    status: str,
    source: str,
) -> None:
    state = load_export_state()
    exports = state.setdefault("exports", [])
    record = {
        "activity_type": activity_type,
        "download_activities": download_activities,
        "end_date": end_date.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "month": month_key(start_date),
        "output_dir": str(output_dir),
        "source": source,
        "start_date": start_date.isoformat(),
        "status": status,
    }
    exports.append(record)
    state["last_successful_export_date"] = end_date.isoformat()
    state["last_successful_export_dir"] = str(output_dir)
    state["last_successful_export_source"] = source
    save_export_state(state)
