#!/usr/bin/env python3
"""Export Garmin Connect data to local JSON files.

This wrapper intentionally keeps credentials and tokens outside the project.
It uses the published ``garminconnect`` Python package.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from getpass import getpass
from pathlib import Path
from typing import Any, Callable

from garmin_storage import (
    DEFAULT_EXPORT_DIR,
    month_chunks,
    month_output_dir,
    record_export,
    write_json,
)


DEFAULT_TOKENSTORE = Path(os.path.expanduser("~/.garminconnect"))

try:
    from garminconnect import (  # type: ignore[import-not-found]
        Garmin,
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
    )
except ImportError as exc:  # pragma: no cover - setup guard
    raise SystemExit(
        "Cannot import garminconnect. Install dependencies first:\n"
        "  poetry install"
    ) from exc


class ExportError(RuntimeError):
    """Raised when export cannot complete safely."""


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def daterange(start: date, end: date) -> list[date]:
    if end < start:
        raise ExportError("--end-date must be on or after --start-date")
    days = (end - start).days
    return [start + timedelta(days=offset) for offset in range(days + 1)]


def safe_call(name: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "data": fn()}
    except (
        GarminConnectAuthenticationError,
        GarminConnectConnectionError,
        GarminConnectTooManyRequestsError,
        ValueError,
    ) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def login_client(tokenstore: Path, allow_prompt: bool) -> Garmin:
    tokenstore = tokenstore.expanduser().resolve()

    try:
        client = Garmin()
        client.login(str(tokenstore))
        return client
    except GarminConnectTooManyRequestsError:
        raise
    except (GarminConnectAuthenticationError, GarminConnectConnectionError):
        if not allow_prompt:
            raise ExportError(
                f"No valid Garmin tokens found at {tokenstore}. "
                "Run `export_garmin_data.py login` first."
            )

    email = os.getenv("GARMIN_EMAIL") or input("Garmin email: ").strip()
    password = os.getenv("GARMIN_PASSWORD") or getpass("Garmin password: ")
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=lambda: input("Garmin MFA code: ").strip(),
    )
    client.login(str(tokenstore))
    return client


def command_login(args: argparse.Namespace) -> int:
    client = login_client(args.tokenstore, allow_prompt=True)
    profile = safe_call("profile", client.get_user_profile)
    write_json(args.output_dir / "login_check.json", profile)
    print(f"Login succeeded. Tokens stored at: {args.tokenstore.expanduser()}")
    print(f"Login check written to: {args.output_dir / 'login_check.json'}")
    return 0


def export_daily_health(client: Garmin, day: date, output_dir: Path) -> None:
    day_s = day.isoformat()
    checks: dict[str, Callable[[], Any]] = {
        "user_summary": lambda: client.get_user_summary(day_s),
        "stats": lambda: client.get_stats(day_s),
        "heart_rates": lambda: client.get_heart_rates(day_s),
        "sleep": lambda: client.get_sleep_data(day_s),
        "stress": lambda: client.get_all_day_stress(day_s),
        "body_battery": lambda: client.get_body_battery(day_s),
        "body_battery_events": lambda: client.get_body_battery_events(day_s),
        "hrv": lambda: client.get_hrv_data(day_s),
        "training_readiness": lambda: client.get_training_readiness(day_s),
        "training_status": lambda: client.get_training_status(day_s),
    }
    payload = {name: safe_call(name, fn) for name, fn in checks.items()}
    write_json(output_dir / "daily" / f"{day_s}.json", payload)


def export_activities(
    client: Garmin,
    start_date: date,
    end_date: date,
    output_dir: Path,
    activity_type: str | None,
    download_activities: bool,
) -> None:
    activities_result = safe_call(
        "activities_by_date",
        lambda: client.get_activities_by_date(
            start_date.isoformat(),
            end_date.isoformat(),
            activitytype=activity_type,
        ),
    )
    write_json(output_dir / "activities.json", activities_result)

    if not activities_result["ok"]:
        return

    activities = activities_result["data"] or []
    detail_dir = output_dir / "activity_details"
    download_dir = output_dir / "activity_downloads"

    for activity in activities:
        activity_id = activity.get("activityId")
        if not activity_id:
            continue

        details = {
            "summary": activity,
            "details": safe_call(
                "activity_details",
                lambda activity_id=activity_id: client.get_activity_details(activity_id),
            ),
            "hr_time_in_zones": safe_call(
                "activity_hr_in_timezones",
                lambda activity_id=activity_id: client.get_activity_hr_in_timezones(
                    activity_id
                ),
            ),
            "power_time_in_zones": safe_call(
                "activity_power_in_timezones",
                lambda activity_id=activity_id: client.get_activity_power_in_timezones(
                    activity_id
                ),
            ),
            "weather": safe_call(
                "activity_weather",
                lambda activity_id=activity_id: client.get_activity_weather(activity_id),
            ),
        }
        write_json(detail_dir / f"{activity_id}.json", details)

        if download_activities:
            downloaded = safe_call(
                "download_activity_original",
                lambda activity_id=activity_id: client.download_activity(activity_id),
            )
            if downloaded["ok"]:
                download_dir.mkdir(parents=True, exist_ok=True)
                (download_dir / f"{activity_id}.zip").write_bytes(downloaded["data"])
            else:
                write_json(download_dir / f"{activity_id}.error.json", downloaded)


def export_range(
    *,
    client: Garmin,
    start_date: date,
    end_date: date,
    output_dir: Path,
    activity_type: str | None,
    download_activities: bool,
    tokenstore: Path,
) -> None:
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "activity_type": activity_type,
        "download_activities": download_activities,
        "tokenstore": str(tokenstore.expanduser()),
    }
    write_json(output_dir / "metadata.json", meta)

    for day in daterange(start_date, end_date):
        export_daily_health(client, day, output_dir)

    export_activities(
        client,
        start_date,
        end_date,
        output_dir,
        activity_type,
        download_activities,
    )

    extra = {
        "cycling_ftp": safe_call("cycling_ftp", client.get_cycling_ftp),
        "weigh_ins": safe_call(
            "weigh_ins",
            lambda: client.get_weigh_ins(
                start_date.isoformat(), end_date.isoformat()
            ),
        ),
    }
    write_json(output_dir / "performance_and_weight.json", extra)


def command_export(args: argparse.Namespace) -> int:
    client = login_client(args.tokenstore, allow_prompt=False)

    if args.monthly_layout:
        for chunk_start, chunk_end in month_chunks(args.start_date, args.end_date):
            output_dir = month_output_dir(chunk_start)
            export_range(
                client=client,
                start_date=chunk_start,
                end_date=chunk_end,
                output_dir=output_dir,
                activity_type=args.activity_type,
                download_activities=args.download_activities,
                tokenstore=args.tokenstore,
            )
            record_export(
                start_date=chunk_start,
                end_date=chunk_end,
                activity_type=args.activity_type,
                output_dir=output_dir,
                download_activities=args.download_activities,
                status="success",
                source="manual_export_monthly_layout",
            )
            print(f"Export written to: {output_dir}")
        return 0

    label = f"{args.start_date.isoformat()}_{args.end_date.isoformat()}"
    output_dir = args.output_dir / label
    export_range(
        client=client,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=output_dir,
        activity_type=args.activity_type,
        download_activities=args.download_activities,
        tokenstore=args.tokenstore,
    )
    print(f"Export written to: {output_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Garmin Connect activity and health data to local JSON files."
    )
    parser.add_argument(
        "--tokenstore",
        type=Path,
        default=DEFAULT_TOKENSTORE,
        help="Garmin token directory outside the vault.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Output directory. Default is ignored by git.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("login", help="Authenticate and save Garmin tokens.")

    export = subparsers.add_parser("export", help="Export a date range.")
    export.add_argument("--start-date", type=parse_date, required=True)
    export.add_argument("--end-date", type=parse_date, required=True)
    export.add_argument(
        "--activity-type",
        default="cycling",
        help="Garmin activity type filter. Use empty string for all activities.",
    )
    export.add_argument(
        "--download-activities",
        action="store_true",
        help="Download original activity archives where available.",
    )
    export.add_argument(
        "--monthly-layout",
        action="store_true",
        help="Store exports as exports/raw/YYYY/YYYY-MM chunks and update manifest.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "activity_type", None) == "":
        args.activity_type = None

    try:
        if args.command == "login":
            return command_login(args)
        if args.command == "export":
            return command_export(args)
    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin rate limit exceeded: {exc}", file=sys.stderr)
        return 2
    except (GarminConnectAuthenticationError, ExportError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
