"""Evaluation harness: public samples + custom cases (plan/phases/phase6.md).

    uv run python code/evaluation/main.py [--markdown results.md]   (entry point; logic lives here)

1. Public samples — status accuracy, step P/R/F1, field accuracy, sequence exact, per-case diffs.
2. Custom cases — each runs in an isolated pipeline run where it replaces its source request. The variant keeps
   the source's case_id: only the fields named in `changes` differ (the workflow tie-break uses case order, so a
   renamed row would change an unrelated input — found by cc_05/cc_06, recorded in plan/eval_history.md).
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from custom_cases import CUSTOM_CASES, matches  # noqa: E402
from investigate import investigate_all, load_requests  # noqa: E402
from policy import steps_for  # noqa: E402
from score import format_report, load_answers, score  # noqa: E402

DATA = ROOT / "dataset"


def evaluate_samples(index=None):
    cases = investigate_all(DATA, index=index)
    expected = load_answers(DATA / "sample_output.csv")
    predicted = {cid: (cases[cid].status, steps_for(cases[cid])) for cid in expected}
    return score(expected, predicted)


def run_custom(case, requests, samples, index):
    """(passed, status, steps, problems) for one custom case."""
    if "unit_tests" in case:
        return True, "-", [], [f"covered by unit tests: {', '.join(case['unit_tests'])}"]
    base = next(r for r in requests if r["case_id"] == case["source"])
    row = dict(base, **case["changes"])
    run_requests = [r for r in requests if r["case_id"] != case["source"]] + [row]
    inv = investigate_all(DATA, run_requests, index=index)[case["source"]]
    status, steps = inv.status, steps_for(inv)
    problems = []
    if "exact_from" in case:
        exp_status, exp_steps = samples[case["exact_from"]]
        if status != exp_status:
            problems.append(f"status {status}, expected {exp_status}")
        if steps != exp_steps:
            problems.append(f"steps differ from {case['exact_from']}'s expected answer")
    if "exact" in case and steps != case["exact"]:
        problems.append(f"steps {steps}, expected {case['exact']}")
    if case.get("status") and status != case["status"]:
        problems.append(f"status {status}, expected {case['status']}")
    for partial in case.get("must_contain", []):
        if not any(matches(s, partial) for s in steps):
            problems.append(f"missing step matching {partial}")
    for partial in case.get("must_not", []):
        bad = [s for s in steps if matches(s, partial)]
        if bad:
            problems.append(f"forbidden step present: {bad[0]}")
    return not problems, status, steps, problems


def evaluate_custom(index=None):
    from evidence.index import build

    index = index or build(DATA)
    requests = load_requests(DATA)
    samples = load_answers(DATA / "sample_output.csv")
    return [(c, *run_custom(c, requests, samples, index)) for c in CUSTOM_CASES]


def markdown(sample_metrics, custom_results):
    m = sample_metrics
    lines = ["## Public samples (32 cases)", "",
             "| Metric | Value |", "|---|---|",
             f"| Case-level status accuracy | {m['status_accuracy']:.4f} |",
             f"| Step precision / recall / F1 | {m['step_precision']:.4f} / {m['step_recall']:.4f} / {m['step_f1']:.4f} |",
             f"| Sequence exact (full steps array) | {m['sequence_exact']:.4f} |"]
    lines += [f"| Field accuracy: {f} | {v:.4f} |" for f, v in m["field_accuracy"].items()]
    passed = sum(r[1] for r in custom_results)
    lines += ["", f"## Custom cases ({passed}/{len(custom_results)} passing)", "",
              "| Case | Behaviour tested | Result | Status |", "|---|---|---|---|"]
    for case, ok, status, _, problems in custom_results:
        lines.append(f"| {case['id']} | {case['title']} | {'pass' if ok else 'FAIL: ' + '; '.join(problems)} | {status} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Evaluation harness")
    parser.add_argument("--markdown", help="write a Markdown summary to this path")
    args = parser.parse_args()
    from evidence.index import build

    index = build(DATA)
    m = evaluate_samples(index)
    print(format_report(m, "public samples"))
    results = evaluate_custom(index)
    print(f"\n=== custom cases: {sum(r[1] for r in results)}/{len(results)} passing")
    for case, ok, status, steps, problems in results:
        print(f"  {'PASS' if ok else 'FAIL'} {case['id']} [{status}] {case['title']}")
        for p in problems:
            print(f"       {p}")
    if args.markdown:
        Path(args.markdown).write_text(markdown(m, results), encoding="utf-8")
        print(f"\nwrote {args.markdown}")


if __name__ == "__main__":
    main()
