"""Validate output.csv against the submission contract (guardrails §9.2).

    uv run python code/validate_output.py [--output output.csv] [--data dataset]

Exits non-zero and lists every problem if any check fails.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from identity import parse_ts  # noqa: E402
from main import case_number  # noqa: E402
from policy import ALLOWED, FINDING, OPERATION_ORDER, PHASES, VERIFICATION  # noqa: E402

HEADER = ["case_id", "deletion_status", "steps_json"]
STATUSES = {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}
KEYS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}


def evidence_dates(data_dir):
    """Every citable id → its date (file captured_at, activity event_time, audit event_time)."""
    dates = {}
    for name, id_col, time_col in (("evidence_files.csv", "file_id", "captured_at"),
                                   ("system_activity.csv", "activity_id", "event_time"),
                                   ("user_audit_log.csv", "audit_id", "event_time")):
        with open(data_dir / name, newline="", encoding="utf-8") as f:
            dates.update({r[id_col]: parse_ts(r[time_col]) for r in csv.DictReader(f)})
    return dates


def validate(output_path, data_dir):
    errors = []
    with open(data_dir / "deletion_requests.csv", newline="", encoding="utf-8") as f:
        requests = {r["case_id"]: r for r in csv.DictReader(f)}
    dates = evidence_dates(data_dir)
    with open(output_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        rows = list(reader)
    if header != HEADER:
        errors.append(f"header is {header}, expected {HEADER}")
    ids = [r[0] for r in rows if r]
    if len(rows) != len(requests):
        errors.append(f"{len(rows)} data rows, expected {len(requests)}")
    if len(set(ids)) != len(ids):
        errors.append("duplicate case_id rows")
    if set(ids) != set(requests):
        errors.append(f"case_id set differs: missing {sorted(set(requests) - set(ids))[:5]}, "
                      f"unknown {sorted(set(ids) - set(requests))[:5]}")
    if ids != sorted(ids, key=case_number):
        errors.append("rows are not sorted by case_id")
    for row in rows:
        if len(row) != 3:
            errors.append(f"row with {len(row)} columns: {row[:1]}")
            continue
        cid, status, text = row
        where = f"{cid}:"
        if status not in STATUSES:
            errors.append(f"{where} invalid status {status!r}")
        try:
            steps = json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"{where} steps_json is not valid JSON ({exc})")
            continue
        if not isinstance(steps, list):
            errors.append(f"{where} steps_json is not an array")
            continue
        if (status == "NOT_APPLICABLE") != (steps == []):
            errors.append(f"{where} NOT_APPLICABLE must have [] and only it may be empty")
        audit_at = parse_ts(requests[cid]["audit_at"]) if cid in requests else None
        prev = None
        for i, s in enumerate(steps, 1):
            if not isinstance(s, dict) or set(s) != KEYS:
                errors.append(f"{where} step {i} must have exactly the keys {sorted(KEYS)}")
                continue
            if s["step_no"] != i:
                errors.append(f"{where} step_no {s['step_no']} at position {i}")
            if ALLOWED.get((s["phase"], s["operation"])) != s["state"]:
                errors.append(f"{where} step {i} disallowed {s['phase']}/{s['operation']}/{s['state']}")
                continue
            key = (PHASES.index(s["phase"]), OPERATION_ORDER[s["phase"]].index(s["operation"]), s["system_id"], s["resource_id"])
            if prev is not None and key < prev:
                errors.append(f"{where} step {i} out of order")
            prev = key
            ev = s["evidence_id"]
            if status == "COMPLETE" and s["phase"] != VERIFICATION:
                errors.append(f"{where} COMPLETE case contains a {s['phase']} step")
            if status == "INCOMPLETE" and s["phase"] != FINDING and ev:
                errors.append(f"{where} step {i} future {s['phase']} step must have evidence_id \"\"")
            if status == "INCOMPLETE" and s["phase"] == FINDING and not ev:
                errors.append(f"{where} step {i} finding without evidence")
            if ev:
                if ev not in dates:
                    errors.append(f"{where} step {i} cites unknown evidence {ev}")
                elif audit_at and dates[ev] > audit_at:
                    errors.append(f"{where} step {i} cites {ev} dated after audit_at")
        if status == "INCOMPLETE" and not any(isinstance(s, dict) and s.get("phase") == FINDING for s in steps):
            errors.append(f"{where} INCOMPLETE without a finding")
    return errors, len(rows)


def main():
    parser = argparse.ArgumentParser(description="Validate output.csv")
    parser.add_argument("--output", default=str(ROOT / "output.csv"))
    parser.add_argument("--data", default=str(ROOT / "dataset"))
    args = parser.parse_args()
    errors, n = validate(Path(args.output), Path(args.data))
    if errors:
        print(f"INVALID: {len(errors)} problem(s) in {n} rows")
        for e in errors[:50]:
            print("  -", e)
        sys.exit(1)
    print(f"VALID: {n} rows pass every contract check")


if __name__ == "__main__":
    main()
