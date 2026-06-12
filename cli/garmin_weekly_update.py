#!/usr/bin/env python3
"""Refresh Garmin raw exports for the current month."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from export_garmin_data import ExportError, export_range, login_client, parse_date
from garmin_storage import month_output_dir, month_start, record_export
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Weekly Garmin update. Refreshes the current month-to-date."
    )
    parser.add_argument("--today", type=parse_date, default=date.today())
    parser.add_argument("--activity-type", default="cycling")
    parser.add_argument("--download-activities", action="store_true")
    parser.add_argument(
        "--tokenstore",
        type=Path,
        default=Path("~/.garminconnect"),
        help="Garmin token directory outside the vault.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.activity_type == "":
        args.activity_type = None

    start = month_start(args.today)
    output_dir = month_output_dir(args.today)

    try:
        client = login_client(args.tokenstore, allow_prompt=False)
        export_range(
            client=client,
            start_date=start,
            end_date=args.today,
            output_dir=output_dir,
            activity_type=args.activity_type,
            download_activities=args.download_activities,
            tokenstore=args.tokenstore,
        )
        record_export(
            start_date=start,
            end_date=args.today,
            activity_type=args.activity_type,
            output_dir=output_dir,
            download_activities=args.download_activities,
            status="success",
            source="weekly_update",
        )
    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin rate limit exceeded: {exc}", file=sys.stderr)
        return 2
    except (GarminConnectAuthenticationError, ExportError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Weekly update written to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

