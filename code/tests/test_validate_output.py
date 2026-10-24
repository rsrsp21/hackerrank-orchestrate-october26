"""Tests for code/validate_output.py: the real output passes; deliberately broken files are caught."""

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from main import run  # noqa: E402
from validate_output import validate  # noqa: E402

DATA = ROOT / "dataset"


@pytest.fixture(scope="module")
def good(tmp_path_factory):
    path = tmp_path_factory.mktemp("out") / "output.csv"
    run(DATA, path)
    return path


def _rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    return path


def test_generated_output_is_valid(good):
    errors, n = validate(good, DATA)
    assert errors == [] and n == 518


def _mutate(good, tmp_path, fn):
    rows = _rows(good)
    fn(rows)
    errors, _ = validate(_write(tmp_path / "bad.csv", rows), DATA)
    return " | ".join(errors)


def _first(rows, status):
    return next(r for r in rows[1:] if r[1] == status)


def test_catches_contract_violations(good, tmp_path):
    assert "header" in _mutate(good, tmp_path, lambda r: r.__setitem__(0, ["case", "status", "steps"]))
    assert "data rows" in _mutate(good, tmp_path, lambda r: r.pop())
    assert "not sorted" in _mutate(good, tmp_path, lambda r: r.__setitem__(slice(1, 3), [r[2], r[1]]))
    assert "invalid status" in _mutate(good, tmp_path, lambda r: _first(r, "COMPLETE").__setitem__(1, "DONE"))
    assert "not valid JSON" in _mutate(good, tmp_path, lambda r: _first(r, "COMPLETE").__setitem__(2, "[{"))

    def bad_state(rows):
        row = _first(rows, "INCOMPLETE")
        steps = json.loads(row[2])
        steps[0]["state"] = "ABSENT"  # a finding can never be ABSENT
        row[2] = json.dumps(steps)
    assert "disallowed" in _mutate(good, tmp_path, bad_state)

    def remediation_with_evidence(rows):
        row = _first(rows, "INCOMPLETE")
        steps = json.loads(row[2])
        next(s for s in steps if s["phase"] == "REMEDIATION")["evidence_id"] = "evidence_01"
        row[2] = json.dumps(steps)
    assert 'must have evidence_id ""' in _mutate(good, tmp_path, remediation_with_evidence)

    with open(DATA / "deletion_requests.csv", newline="", encoding="utf-8") as f:
        early = {r["case_id"] for r in csv.DictReader(f) if r["audit_at"] < "2026-10-01T12:00:00Z"}

    def future_evidence(rows):
        row = next(r for r in rows[1:] if r[1] == "INCOMPLETE" and r[0] in early)
        steps = json.loads(row[2])
        steps[0]["evidence_id"] = "evidence_03"  # captured 2026-10-01T12:00Z, after this case's audit_at
        row[2] = json.dumps(steps)
    assert "after audit_at" in _mutate(good, tmp_path, future_evidence)

    def unknown_evidence(rows):
        row = _first(rows, "INCOMPLETE")
        steps = json.loads(row[2])
        steps[0]["evidence_id"] = "evidence_999"
        row[2] = json.dumps(steps)
    assert "unknown evidence" in _mutate(good, tmp_path, unknown_evidence)

    assert "NOT_APPLICABLE" in _mutate(good, tmp_path, lambda r: _first(r, "NOT_APPLICABLE").__setitem__(2, json.dumps(
        [{"step_no": 1, "phase": "VERIFICATION", "system_id": "account_service", "resource_id": "account_1",
          "operation": "VERIFY_RECORD_ABSENT", "state": "ABSENT", "evidence_id": "evidence_54"}])))
