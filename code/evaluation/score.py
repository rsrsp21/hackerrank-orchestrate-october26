"""Scoring: compare predicted answers with expected answers (task 5.3; the core of the P6 harness).

Metrics
  status accuracy      share of cases whose deletion_status matches
  step P / R / F1      multiset match of whole steps (phase, system_id, resource_id, operation, state, evidence_id)
  field accuracy       per field, over aligned step positions (position i of both arrays; a missing step counts wrong)
  sequence exact       share of cases whose full steps array is identical (key order ignored)
Run on the public samples: uv run python code/evaluation/score.py
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id")
STEP_KEY = ("phase", "system_id", "resource_id", "operation", "state", "evidence_id")


def _key(step):
    return tuple(step.get(f) for f in STEP_KEY)


def score(expected, predicted):
    """expected/predicted: case_id → (status, steps). Returns a metrics dict with per-case details."""
    status_ok = seq_ok = tp = n_pred = n_exp = 0
    field_ok, field_n = Counter(), 0
    cases = {}
    for cid, (exp_status, exp_steps) in expected.items():
        got_status, got_steps = predicted.get(cid, ("<missing>", []))
        status_ok += got_status == exp_status
        seq_ok += got_steps == exp_steps
        e, g = Counter(map(_key, exp_steps)), Counter(map(_key, got_steps))
        match = sum((e & g).values())
        tp, n_pred, n_exp = tp + match, n_pred + len(got_steps), n_exp + len(exp_steps)
        width = max(len(exp_steps), len(got_steps))
        field_n += width
        for i in range(width):
            a = exp_steps[i] if i < len(exp_steps) else {}
            b = got_steps[i] if i < len(got_steps) else {}
            for f in FIELDS:
                field_ok[f] += bool(a) and bool(b) and a.get(f) == b.get(f)
        cases[cid] = {"status": (exp_status, got_status), "missing": sorted(e - g), "extra": sorted(g - e)}
    precision = tp / n_pred if n_pred else 1.0
    recall = tp / n_exp if n_exp else 1.0
    n = len(expected)
    return {
        "cases": n,
        "status_accuracy": status_ok / n,
        "step_precision": precision,
        "step_recall": recall,
        "step_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "field_accuracy": {f: field_ok[f] / field_n for f in FIELDS} if field_n else {},
        "sequence_exact": seq_ok / n,
        "steps_expected": n_exp,
        "steps_predicted": n_pred,
        "details": cases,
    }


def load_answers(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["case_id"]: (r["deletion_status"], json.loads(r["steps_json"])) for r in csv.DictReader(f)}


def format_report(m, title="score"):
    lines = [f"=== {title}: {m['cases']} cases",
             f"status accuracy   {m['status_accuracy']:.4f}",
             f"step precision    {m['step_precision']:.4f}  recall {m['step_recall']:.4f}  F1 {m['step_f1']:.4f}"
             f"  ({m['steps_predicted']} predicted / {m['steps_expected']} expected)",
             f"sequence exact    {m['sequence_exact']:.4f}",
             "field accuracy    " + "  ".join(f"{f}={v:.4f}" for f, v in m["field_accuracy"].items())]
    for cid, d in sorted(m["details"].items(), key=lambda kv: (len(kv[0]), kv[0])):
        if d["missing"] or d["extra"] or d["status"][0] != d["status"][1]:
            lines.append(f"  {cid}: status {d['status'][1]} (expected {d['status'][0]})")
            lines += [f"      - missing {s}" for s in d["missing"]] + [f"      + extra   {s}" for s in d["extra"]]
    return "\n".join(lines)


def main():
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "code"))
    from investigate import investigate_all
    from policy import steps_for

    cases = investigate_all(root / "dataset")
    expected = load_answers(root / "dataset" / "sample_output.csv")
    predicted = {cid: (cases[cid].status, steps_for(cases[cid])) for cid in expected}
    print(format_report(score(expected, predicted), "public samples"))


if __name__ == "__main__":
    main()
