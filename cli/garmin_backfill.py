#!/usr/bin/env python3
"""Backfill Garmin raw exports in monthly chunks."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

from export_garmin_data import ExportError, export_range, login_client, parse_date
from garmin_storage import month_chunks, month_output_dir, record_export
from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError


DEFAULT_START_DATE = date(2022, 1, 1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill Garmin exports in monthly raw folders."
    )
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", type=parse_date, default=date.today())
    parser.add_argument("--activity-type", default="cycling")
    parser.add_argument("--download-activities", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=2.0)
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

    try:
        client = login_client(args.tokenstore, allow_prompt=False)
        for start, end in month_chunks(args.start_date, args.end_date):
            output_dir = month_output_dir(start)
            if output_dir.exists() and not args.overwrite:
                print(f"Skipping existing month: {output_dir}")
                continue

            print(
                "Exporting "
                f"{start.isoformat()} to {end.isoformat()} -> {output_dir}"
            )
            export_range(
                client=client,
                start_date=start,
                end_date=end,
                output_dir=output_dir,
                activity_type=args.activity_type,
                download_activities=args.download_activities,
                tokenstore=args.tokenstore,
            )
            record_export(
                start_date=start,
                end_date=end,
                activity_type=args.activity_type,
                output_dir=output_dir,
                download_activities=args.download_activities,
                status="success",
                source="backfill",
            )
            time.sleep(args.pause_seconds)
    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin rate limit exceeded: {exc}", file=sys.stderr)
        return 2
    except (GarminConnectAuthenticationError, ExportError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Backfill completed at {datetime.now().isoformat(timespec='seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

