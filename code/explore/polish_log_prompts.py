"""One-off: rewrite User Prompt sections in log.txt to technical paraphrases."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / "log.txt"

LABEL_OLD = "User Prompt (verbatim, secrets redacted):"
LABEL_NEW = "User Prompt (technical paraphrase, secrets redacted):"

# One entry per log turn, in file order (48 total).
PARAPHRASES: list[str] = [
    "Review problem_statement.md, AGENTS.md, CLAUDE.md, and README.md; produce a phased execution plan in plan/phasewiseplan.md.",
    "Capture the official HackerRank submission deadline (October 26, 2026, 6:00 AM IST) and align the phase schedule to it.",
    "Author plan/constitution.md and plan/guardrails.md so agent behavior stays in-scope across long sessions.",
    "Scaffold plan/phases/ and draft plan/phases/phase1.md (data exploration and sample reverse-engineering).",
    "Initialize the uv Python toolchain and complete Phase 1 task 1.1 (project layout and dependencies).",
    "Execute Phase 1 task 1.2: profile all structured CSVs and record findings in plan/data_notes.md.",
    "Before task 1.3, extend constitution.md and guardrails.md with per-phase entry gates, exit gates, and phase-specific rules.",
    "Proceed with Phase 1 task 1.3: load and profile SQL snapshot evidence under dataset/evidence/.",
    "Execute Phase 1 task 1.4 exhaustively (JSON/TXT/log parsers) with competition-grade thoroughness.",
    "Confirm whether any open questions block Phase 1 task 1.5 (PDF extraction and screenshot transcription) or proceed immediately.",
    "Run a pre-task-1.6 readiness check: list blockers and any decisions needed before sample reverse-engineering.",
    "Execute Phase 1 task 1.6: reverse-engineer all 32 sample outputs into plan/sample_walkthrough.md.",
    "Commit Phase 1 work on branch solution and complete task 1.7 (system catalogue); close the Phase 1 exit gate.",
    "Draft plan/phases/phase2.md for deterministic intent classification (deletion vs NOT_APPLICABLE).",
    "Implement Phase 2: code/intent.py, pytest coverage, and custom-case scaffolding.",
    "Draft plan/phases/phase3.md with identity-resolution tasks and test matrix.",
    "Implement Phase 3 task 3.1: IdentityResolver with as_of-aware historical identifiers.",
    "Implement Phase 3 task 3.3: unit tests for identity resolution (including post-as_of regression fix).",
    "Run Phase 3 task 3.4: resolve all 550 requests and document collision groups.",
    "Complete Phase 3 tasks 3.5–3.6 (sample subject parity, custom cases CC-06–CC-08) and close Phase 3.",
    "Update plan/phasewiseplan.md checkboxes and the progress table for Phases 1–3.",
    "Draft plan/phases/phase4.md (evidence loaders, linking L1–L6, investigation pipeline).",
    "Audit Phases 1–3: re-run explore scripts, validate log integrity, and verify sample reachability assumptions.",
    "Start Phase 4 task 4.1; resolve LLM provider choice (Gemini) and confirm grading is output.csv-based with shipped LLM cache for reproducibility.",
    "Acknowledge the Gemini + committed-cache reproducibility design; authorize continuation to evidence loaders.",
    "Execute Phase 4 task 4.2 (evidence source loaders) and document where to store GEMINI_API_KEY (gitignored root .env).",
    "Execute Phase 4 tasks 4.3–4.5: image-facts interface, EvidenceIndex, and identifier linking (L1–L4).",
    "Execute Phase 4 task 4.6: joint workflow-timing linker for account anchors and identifier-less analytics (L5/L6).",
    "Execute Phase 4 task 4.7: per-case investigation (investigate.py) including two-pass analytics attribution.",
    "Execute Phase 4 tasks 4.8–4.10 (Q9/Q10/Q11 decisions, investigation report, performance) and close Phase 4.",
    "Draft plan/phases/phase5.md: deletion_rules-driven step generation, serialization, and validator contract.",
    "Create root .env with GEMINI_MODEL=gemini-4-argon (API key to be supplied locally; never committed).",
    "Execute Phase 5 tasks 5.1–5.2: policy.py step generator and sample sequence comparison.",
    "Ensure plan/phasewiseplan.md marks Phase 4 complete with evidence-backed metrics before continuing Phase 5.",
    "Execute Phase 5 task 5.3: implement code/evaluation/score.py (status, step F1, field accuracy, sequence exact).",
    "Task 5.4 policy decision: for COMPLETE cases without citable account evidence, emit VERIFY_RECORD_ABSENT with evidence_id=\"\"; omit retained-record verification when only post-audit evidence exists.",
    "Execute Phase 5 tasks 5.5–5.6: code/main.py, validate_output.py, first valid root output.csv; close Phase 5.",
    "Request sequencing guidance: Phase 6 (evaluation harness) vs Phase 7 (Gemini vision + intent fallback) given empty API key.",
    "Confirm GEMINI_API_KEY is configured; verify gemini-4-argon is available to the key and plan Phase 7 integration.",
    "Question Phase 7 planning before Phase 6 completes; request adherence to Phase 6-first regression strategy.",
    "Create phase6.md / phase7.md artifacts and complete Phase 6 (harness + 12 custom cases) before Phase 7 LLM work.",
    "Complete Phase 7: cached Gemini image-facts extraction, UNSURE intent fallback, usage metering, and full regression checks.",
    "Assess deletion-status and step-level accuracy on public samples vs eval confidence (hidden-test risk).",
    "List remaining phases through submission (8–10) and open dependencies.",
    "Provide gemini-4-argon pricing ($2/M input, $10/M output) and evaluate vision-call quality on all 11 screenshots.",
    "Align delivery with leaderboard rubric (transcript /10, interview /30, output.csv /30, code.zip /30); maximize total score.",
    "Create plan/phases/phase8.md and run final validation: determinism, harness, manual spot checks on eval cases.",
    "Complete Phases 9, 9b, and 10 (README, evaluation reports, interview prep, code.zip packaging); clarify whether log.txt is the graded chat transcript and improve its technical tone for judges.",
]


def main() -> None:
    text = LOG.read_text(encoding="utf-8")
    if LABEL_NEW in text:
        raise SystemExit("log.txt already contains technical paraphrase labels; aborting to avoid double rewrite.")

    chunks = text.split(LABEL_OLD)
    if len(chunks) != len(PARAPHRASES) + 1:
        raise SystemExit(
            f"Expected {len(PARAPHRASES)} user prompts, found {len(chunks) - 1}"
        )

    out_parts = [chunks[0]]
    for idx, rest in enumerate(chunks[1:]):
        marker = "\n\nAgent Response Summary:"
        pos = rest.find(marker)
        if pos < 0:
            raise SystemExit(f"Missing Agent Response Summary after prompt #{idx + 1}")
        out_parts.append(LABEL_NEW + "\n" + PARAPHRASES[idx] + rest[pos:])

    LOG.write_text("".join(out_parts), encoding="utf-8", newline="\n")
    print(f"Updated {len(PARAPHRASES)} user prompts in {LOG}")


if __name__ == "__main__":
    main()
