"""Poetry console script entry points."""

from __future__ import annotations

import sys
from pathlib import Path


CLI_DIR = Path(__file__).resolve().parent
if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))


def garmin_export() -> int:
    from export_garmin_data import main

    return main()


def backfill() -> int:
    from garmin_backfill import main

    return main()


def weekly() -> int:
    from garmin_weekly_update import main

    return main()


def summarize() -> int:
    from garmin_summarize import main

    return main()


def garmin_rf() -> int:
    from garmin_trainings import main

    return main()
