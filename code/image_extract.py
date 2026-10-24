"""Screenshot → image facts via a vision LLM (plan/phases/phase7.md §2.2).

    uv run python code/image_extract.py [--only evidence_04] [--force]

For each image in the evidence manifest without a facts file, ask the model for facts (prompt:
code/prompts/image_facts.md), keep only records that pass the schema rules of evidence/images.py, and write
code/llm_cache/image_facts/<file_id>.json. Answers are cached (llm.py), so re-runs cost nothing.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence import activity, images  # noqa: E402
from evidence.common import files_under, load_manifest  # noqa: E402
from llm import default_llm  # noqa: E402

PROMPT_PATH = ROOT / "code" / "prompts" / "image_facts.md"
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def prompt_and_version():
    text = PROMPT_PATH.read_text(encoding="utf-8")
    version = re.search(r"prompt_version: (\S+)", text).group(1)
    return text, version


def valid_answer(answer):
    return isinstance(answer, dict) and isinstance(answer.get("records"), list)


def extract(data_dir, llm, only=None, force=False, facts_dir=images.FACTS_DIR):
    """Write facts for every image that needs them. Returns {file_id: kept/total or reason}."""
    manifest = load_manifest(data_dir)
    links = activity.catalog_links(activity.load_activities(data_dir))
    prompt, version = prompt_and_version()
    facts_dir = Path(facts_dir)
    facts_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for ef in files_under(manifest, "images", set(MIME)):
        if only and ef.file_id not in only:
            continue
        out = images.facts_path(ef.file_id, facts_dir)
        if out.exists() and not force:
            results[ef.file_id] = "exists"
            continue
        answer = llm.generate_json("image_facts", prompt, version, [(ef.path.read_bytes(), MIME[ef.path.suffix])],
                                   validate=valid_answer)
        if answer is None:
            results[ef.file_id] = "no answer (no key and no cache entry, or the call failed)"
            continue
        kept = [r for r in answer["records"] if isinstance(r, dict) and images._record_observation(ef, r, links)]
        out.write_text(json.dumps({"file_id": ef.file_id, "model": llm.model, "prompt_version": version,
                                   "records": answer["records"]}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        results[ef.file_id] = f"{len(kept)}/{len(answer['records'])} records usable"
    return results


def main():
    parser = argparse.ArgumentParser(description="Extract screenshot facts with the configured vision model")
    parser.add_argument("--data", default=str(ROOT / "dataset"))
    parser.add_argument("--only", nargs="*", help="file ids to process")
    parser.add_argument("--force", action="store_true", help="re-extract even if a facts file exists")
    args = parser.parse_args()
    llm = default_llm()
    for file_id, result in extract(Path(args.data), llm, set(args.only) if args.only else None, args.force).items():
        print(f"{file_id}: {result}")
    for row in llm.meter.summary():
        print(row)


if __name__ == "__main__":
    main()
