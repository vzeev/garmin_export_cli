# Garmin local export tools

Small Python tools for exporting Garmin Connect data into local JSON files and generating compact summaries for an AI agent or personal training workflow.

The design is intentionally simple: keep the raw data local, store it in predictable folders, and generate smaller derived files that are easier for an agent to read than screenshots or manual copy-paste.

## Repository Layout

```text
garmin-local-export-tools/
  README.md
  pyproject.toml
  poetry.toml
  .gitignore
  cli/
    __init__.py
    entrypoints.py
    export_garmin_data.py
    garmin_backfill.py
    garmin_storage.py
    garmin_summarize.py
    garmin_trainings.py
    garmin_weekly_update.py
  examples/llm_agents/       # command examples for agent-driven workflows
  exports/                     # personal raw data, ignored
  derived/                     # generated summaries, ignored
```

## What This Does

- Logs in to Garmin Connect using the published [`garminconnect`](https://pypi.org/project/garminconnect/) Python package.
- Stores Garmin tokens outside the project by default.
- Exports daily health data, activities, activity details, FTP, and weight data where available.
- Stores raw data by month under `exports/raw/YYYY/YYYY-MM/`.
- Keeps an export manifest under `exports/manifests/export_state.json`.
- Supports month-by-month historical backfill.
- Supports current-month weekly refresh.
- Generates compact training summaries under `derived/training/`.
- Provides dry-run-first commands for creating and scheduling Garmin cycling training workouts.

## What This Is Not

- It is not an official Garmin product.
- It is not medical or coaching advice.
- It is not a polished app.
- It does not include my Garmin data, tokens, or personal exports.

## Requirements

- Python `>=3.12`
- Poetry
- A Garmin Connect account

## Install

Clone this repository:

```powershell
git clone https://github.com/vzeev/garmin_export_cli garmin-local-export-tools
cd garmin-local-export-tools
```

Install dependencies:

```powershell
poetry install
```

This project depends on the published `garminconnect` package:

```toml
garminconnect = "^0.3.5"
```

The upstream source repository is [`cyberjunky/python-garminconnect`](https://github.com/cyberjunky/python-garminconnect).

## First Login

Run:

```powershell
poetry run garmin-export login
```

The script will prompt for Garmin email, password, and MFA code if required.

By default, tokens are stored outside the project:

```text
~/.garminconnect
```

Do not commit tokens.

## Export A Date Range

Example:

```powershell
poetry run garmin-export export --start-date 2026-06-01 --end-date 2026-06-07
```

By default this filters for cycling activities. To export all activity types, pass an empty activity type:

```powershell
poetry run garmin-export export --start-date 2026-06-01 --end-date 2026-06-07 --activity-type=
```

To use the long-term monthly layout:

```powershell
poetry run garmin-export export --start-date 2026-06-01 --end-date 2026-06-07 --monthly-layout
```

## Historical Backfill

Backfill data month by month:

```powershell
poetry run backfill --start-date 2022-01-01 --end-date 2026-06-07 --activity-type=
```

Use `--overwrite` only when you intentionally want to refresh existing month folders:

```powershell
poetry run backfill --start-date 2022-01-01 --end-date 2026-06-07 --activity-type= --overwrite
```

The script pauses between months by default to reduce pressure on Garmin Connect.

## Weekly Update

Refresh current month-to-date:

```powershell
poetry run weekly
```

This writes to:

```text
exports/raw/YYYY/YYYY-MM/
```

and updates:

```text
exports/manifests/export_state.json
```

## Generate Summaries

Run:

```powershell
poetry run summarize
```

This creates:

```text
derived/training/current_baseline.json
derived/training/weekly_summary.json
derived/training/monthly_summary.json
derived/training/latest_training_context.md
```

Treat the summarizer as an example and adapt it to the questions you want your agent to answer.

## Create Garmin Training Workouts

Build the harmless test workout JSON:

```powershell
poetry run garmin-rf build-test-workout
```

Dry-run upload and scheduling for one manually chosen date:

```powershell
poetry run garmin-rf push-workout --date 2026-06-18 --dry-run
```

Apply only after reviewing the dry-run payload:

```powershell
poetry run garmin-rf push-workout --date 2026-06-18 --apply
```

To push an agent-generated Garmin workout JSON file:

```powershell
poetry run garmin-rf push-workout --date 2026-06-18 --workout-json derived/ridefaster/rf_easy_10m.json --dry-run
```

Applied workout sync results are recorded in the ignored local state file:

```text
derived/ridefaster/workout_sync_state.json
```

More examples are in:

```text
examples/llm_agents/garmin_training_commands.md
```

## Privacy Notes

Garmin exports may include health, sleep, stress, activity, location, body, and performance data. Keep `exports/`, `derived/`, tokens, and logs out of public repositories unless you intentionally sanitize them.

The included `.gitignore` excludes those folders by default.

## Useful Commands

```powershell
poetry run garmin-export --help
poetry run garmin-export export --help
poetry run backfill --help
poetry run weekly --help
poetry run summarize
poetry run garmin-rf --help
poetry run garmin-rf examples
```

## Boundary

Use raw Garmin data as the audit trail. Use generated summaries as agent context. Keep planning assumptions explicit.
