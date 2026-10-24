# Phase 6 — Local Evaluation Harness

**Time box:** ~2–3h
**Goal:** one command that measures the system honestly — the 32 public samples plus hand-built custom cases that exercise behaviour the samples do not cover — and a results history, so every later change (Phase 7 Gemini facts first) is measured against a recorded baseline.
**Governing docs:** constitution Part II Phase 6; guardrails P6; AGENTS.md §6.8 (evaluation_report.md must contain case-level status accuracy, step- and field-level accuracy, sequence accuracy, ≥3 custom cases, failures found and improvements made).

---

## 1. Entry gate
- [x] The pipeline runs end-to-end on the samples (`code/main.py`, `investigate_all` + `policy.steps_for`).
- [x] Scoring core exists (`code/evaluation/score.py`, task 5.3).

## 2. Design

### 2.1 Custom cases are *variants* of real data
A custom case = a request row (new case id `cc_NN`) built from a real request, with one property changed (text, email, audit_at …). The expected result is derived **by hand from the rules and the evidence** and justified in writing. Two expectation kinds:
- **exact** — the full expected answer (used when the variant must reproduce a known answer, e.g. a sample answered via a different email);
- **assertions** — status + steps that must / must not appear (used when only part of the answer is hand-derivable).

Isolation: each custom case runs in its own pipeline run where it **replaces its source request** (otherwise the twin would compete with the original for the same workflow anchor).

Definitions live in `code/evaluation/custom_cases.py` (code, visible to reviewers); `code/evaluation/custom_cases.md` documents each case's purpose and reasoning.

### 2.2 Planned cases
| id | source | change | expectation | behaviour tested |
|---|---|---|---|---|
| CC-01 | case_533 row | text → Spanish refusal | exact: NOT_APPLICABLE `[]` | multilingual negation |
| CC-02 | case_533 row | text → "remove me from your mailing list" | exact: NOT_APPLICABLE | opt-out ≠ deletion |
| CC-03 | case_533 row | text → "deleted by mistake… restore it?" | exact: NOT_APPLICABLE | restore ≠ deletion |
| CC-04 | sample case_17 | text → retention-clause deletion | exact = case_17 answer | retention wording keeps intent |
| CC-05 | sample case_21 | text → "unsubscribe me and delete my account" | exact = case_21 answer | opt-out + deletion |
| CC-06 | sample case_29 | email → subject's **current** email | exact = case_29 answer | identity invariance (evidence only under the old email) |
| CC-07 | sample case_30 | email → old email in Mixed Case | exact = case_30 answer | normalization |
| CC-08 | synthetic | identity change after audit_at | unit tests (test_identity) | temporal identity |
| CC-09 | eval case_135 | none (original) | assertions: account_1417 ABSENT citing evidence_13; no step cites a post-audit row | trap row recorded after file capture |
| CC-10 | sample case_27 | audit_at → 2026-09-17T12:00Z | assertions: INCOMPLETE; finding REPORT_REMAINING_RECORD account_3866 citing evidence_02 | data recreated after deletion is reported once its evidence is usable |
| CC-11 | eval case with a legal hold | none | assertions: VERIFY_RECORD_PRESENT legal_service/legal_hold_*; never DELETE/REDACT a legal hold | retention policy |
| CC-12 | sample case_09 | audit_at → before evidence_93 capture | assertions: no step cites evidence_93 / evidence_06 | two-clock rule |

### 2.3 Harness `code/evaluation/main.py`
`uv run python code/evaluation/main.py [--markdown out.md]`
1. Samples: status accuracy, step P/R/F1, field accuracy, sequence exact, per-case diffs.
2. Custom cases: pass/fail per case with the reason for any failure.
3. Optional Markdown summary (feeds `evaluation_report.md` in P9).

### 2.4 History `plan/eval_history.md`
Dated entries: change made → sample metrics → custom pass count → notes. Baseline = state after Phase 5.

## 3. Tasks
- [x] 6.1 `code/evaluation/custom_cases.py`: CC-01 to CC-12 (CC-08 maps to identity unit tests); `custom_cases.md` documents purpose, input, expectation, reasoning.
- [x] 6.2 Harness `code/evaluation/harness.py` (+ thin entry `code/evaluation/main.py` per the starter layout; split because a second module named `main` shadowed `code/main.py` in tests): isolated custom runs, exact + assertion checks, Markdown summary (`--markdown`).
- [x] 6.3 First run 10/12: cc_05/cc_06 failed only because renaming the request changed its case-number tie-break position, so variants now keep the source case id (they replace it); recorded as a known limitation of the tie-break. Now **12/12**. Discrimination checked: cc_10/cc_12 expect a different status/citation than their sources; cc_01 to cc_03 fail if the classifier misreads.
- [x] 6.4 `plan/eval_history.md` with the post-P5 baseline and P6 entries.
- [x] 6.5 `code/tests/test_harness.py` (3 tests: definitions well-formed, wrong expectations reported, no-op variant reproduces its source). Suite **133 passed**. Pipeline logic unchanged, so output.csv is unchanged.
- [x] 6.6 Plans updated; committed.

## 4. Exit gate ✅ (2026-10-24)
- [x] Samples: status 32/32, sequence 29/32 (ceiling), no regression.
- [x] Custom cases: 12/12 pass.
- [x] History recorded; tests green; committed.

## 5. Guardrail reminders
- Custom expectations are derived from rules and evidence **before** running the pipeline on them; never edited to match output.
- A fix must be generic; "makes cc_10 pass" alone is not a justification.
- Sample answers are used only for scoring and as the exact expectation of their own variants.
