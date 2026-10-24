"""Ghost Data Still Exists — deletion-audit agent entry point.

    uv run python code/main.py [--data dataset] [--out output.csv]

Reads every participant file under dataset/, investigates each request in deletion_requests.csv, and writes
output.csv (case_id, deletion_status, steps_json) sorted numerically by case_id. Sample requests are
investigated alongside the evaluation requests because concurrent deletion workflows are assigned jointly;
their answers are never read. The previous output.csv is kept as code/cache/output_prev.csv.

LLM use (Gemini, configured in .env): screenshot facts are extracted only for images without a committed facts
file, and request texts the rules mark UNSURE get a cached fallback classification. Without a key the run uses
the committed cache only, so it reproduces the same output. Usage is written to code/llm_cache/usage_last_run.json.
"""

import argparse
import csv
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from image_extract import extract  # noqa: E402
from investigate import investigate_all, load_requests  # noqa: E402
from llm import CACHE_DIR, default_llm  # noqa: E402
from policy import serialize, steps_for  # noqa: E402


def case_number(case_id):
    digits = "".join(ch for ch in case_id if ch.isdigit())
    return (int(digits) if digits else 0, case_id)


def usage_summary(llm, requests_count):
    """Live calls of this run plus the recorded usage of every cached answer the run relies on."""
    cached = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(CACHE_DIR).glob("*.json"))]
    by_task = {}
    for c in cached:
        t = by_task.setdefault((c["provider"], c["model"], c["task"]), {"answers": 0, "input_tokens": 0, "output_tokens": 0})
        t["answers"] += 1
        t["input_tokens"] += c["usage"]["input_tokens"]
        t["output_tokens"] += c["usage"]["output_tokens"]
    return {"requests": requests_count, "this_run": llm.meter.summary(),
            "cached_answers": [{"provider": p, "model": m, "task": t, **v} for (p, m, t), v in sorted(by_task.items())]}


def run(data_dir, out_path, use_llm=True):
    started = time.perf_counter()
    eval_requests = load_requests(data_dir, ("deletion_requests.csv",))
    all_requests = load_requests(data_dir)  # eval + sample requests (inputs only)
    llm = default_llm() if use_llm else None
    if llm is not None and llm.client is not None:
        extract(data_dir, llm)  # only images without a committed facts file are sent
    cases = investigate_all(data_dir, all_requests, llm=llm)
    rows = []
    for r in sorted(eval_requests, key=lambda r: case_number(r["case_id"])):
        inv = cases[r["case_id"]]
        rows.append((r["case_id"], inv.status, serialize(steps_for(inv))))
    out_path = Path(out_path)
    if out_path.exists():
        backup = ROOT / "code" / "cache" / "output_prev.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(out_path, backup)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["case_id", "deletion_status", "steps_json"])
        writer.writerows(rows)
    if llm is not None:
        usage_path = CACHE_DIR.parent / "usage_last_run.json"
        summary = json.dumps(usage_summary(llm, len(rows)), indent=2, sort_keys=True)
        usage_path.write_text(summary + "\n", encoding="utf-8")
    status = Counter(s for _, s, _ in rows)
    print(f"wrote {len(rows)} rows to {out_path} in {time.perf_counter() - started:.1f}s; status {dict(sorted(status.items()))}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data", default=str(ROOT / "dataset"), help="dataset directory")
    parser.add_argument("--out", default=str(ROOT / "output.csv"), help="output CSV path")
    parser.add_argument("--no-llm", action="store_true", help="skip every LLM use (deterministic rules + committed facts only)")
    args = parser.parse_args()
    run(Path(args.data), Path(args.out), use_llm=not args.no_llm)


if __name__ == "__main__":
    main()
