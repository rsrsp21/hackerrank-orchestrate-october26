# code/explore — exploration scripts (not part of the pipeline)

Re-runnable scripts used to understand the data before and while building the pipeline. Nothing here is imported by `code/main.py`. Findings are written up in `plan/data_notes.md` and `plan/sample_walkthrough.md`.

| Script | Purpose (phase) |
|---|---|
| `profile_csv.py` | profile the CSV inputs: timestamps, activity patterns, identity history, request texts (P1.2) |
| `load_sql.py` | load every SQL snapshot into in-memory SQLite; families, replica drift, value representations (P1.3) |
| `parse_records.py` | flatten JSON/TXT record families; record-level times; the post-capture trap rows (P1.4) |
| `parse_logs.py` | parse the 7 log formats and join traces (P1.4) |
| `extract_docs.py` | extract PDF text/tables (P1.5) |
| `sample_walkthrough.py` | per-subject evidence timelines for the 32 samples (P1.6) |
| `identity_report.py` | resolve every request; cross-check the samples (P3) |
| `workflow_report.py` | measure workflow-timing linking (P4.6) |
| `investigation_report.py` | investigation quality on samples + eval health report (P4.9) |
| `check_gemini.py` | pre-flight: confirm the configured Gemini model exists (P7) |
| `spot_check.py` | output profile and manual spot checks against raw evidence (P8) |

Run any of them with `uv run python code/explore/<script>.py`. Some write scratch output to `code/cache/` (gitignored, never shipped).
