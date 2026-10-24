# Evaluation Report — Ghost Data Still Exists

Final system as submitted (`output.csv` sha256 `0d80a7d4bad67187…`). Reproduce every number here with:
```bash
uv run python code/evaluation/main.py          # samples + custom cases (add --markdown out.md for the tables)
uv run python -m pytest code/tests -q          # 152 tests
uv run python code/explore/spot_check.py --profile
```

## 1. Method
- **Public samples:** the 32 requests in `dataset/sample_deletion_requests.csv` are run through the full pipeline (together with the 518 evaluation requests, because concurrent deletion workflows are assigned jointly) and scored against `dataset/sample_output.csv`. The answers are used only for scoring — the pipeline never reads them.
- **Metrics** (`code/evaluation/score.py`):
  - *case-level status accuracy* — share of cases whose `deletion_status` matches;
  - *step-level precision / recall / F1* — multiset match of whole steps on (phase, system_id, resource_id, operation, state, evidence_id);
  - *field-level accuracy* — per field over aligned step positions (a missing or extra step counts as wrong);
  - *sequence accuracy* — share of cases whose entire `steps_json` array is identical (JSON key order ignored, as the grader does).
- **Custom cases:** 12 hand-built variants of real requests (`code/evaluation/custom_cases.py`), each with an expectation written from the rules and the evidence *before* running the pipeline.
- **Eval-side checks:** contract validator over all 518 rows, determinism and keyless reproducibility, a confidence census, and 21 manual spot checks against raw evidence.

## 2. Results on the public samples (32 cases, 193 expected steps)

| Metric | Value |
|---|---|
| **Case-level status accuracy** | **1.0000** (32/32) |
| Step precision / recall / F1 | 0.9948 / 0.9845 / **0.9896** (191 predicted, 193 expected, 190 matched) |
| **Sequence accuracy** (exact steps array) | **0.9062** (29/32) |
| Field accuracy — step_no | 0.9896 |
| Field accuracy — phase | 0.9896 |
| Field accuracy — system_id | 0.9689 |
| Field accuracy — resource_id | 0.9637 |
| Field accuracy — operation | 0.9689 |
| Field accuracy — state | 0.9689 |
| Field accuracy — evidence_id | 0.9896 |
| Cited evidence agreement (steps that cite evidence) | 75/75 |

### Remaining differences and their root causes
| Case | Difference | Root cause | Reachable? |
|---|---|---|---|
| case_18 | missing `VERIFY_RECORD_PRESENT security_service/audit_record_6645` | the id appears in **no** participant file (evidence, activity, identities) | no |
| case_20 | missing `VERIFY_RECORD_PRESENT security_service/audit_record_5569` | same — appears nowhere in participant data | no |
| case_23 | `VERIFY_RECORD_ABSENT account_7015` instead of `account_410` | three requests share `reported_at` 2026-09-05T12:00Z and three FAILED account deletions exist only as activity rows with no identifier; nothing separates them, so the last-resort tie-break decides (1-in-3) | no evidence-based way |

**Reachability ceiling.** Of the 193 expected sample steps, 177 reference a resource present in evidence content, 13 reference accounts visible only in activity rows (reachable only through workflow timing), and 3 reference resources present nowhere (`account_004` — recovered by the naming fallback — `audit_record_6645`, `audit_record_5569`). With one genuine tie, 29/32 exact sequences is the ceiling, and the system reaches it.

## 3. Custom evaluation cases (12/12 passing)

Each case replaces its source request in an isolated run and changes only the listed field(s); full reasoning in [`custom_cases.md`](custom_cases.md).

| Case | Source → change | Expectation (written before running) | Behaviour tested | Result |
|---|---|---|---|---|
| cc_01 | case_533 → text "No quiero eliminar mi cuenta, solo cambiar el correo." | NOT_APPLICABLE `[]` | negated deletion verb in Spanish | pass |
| cc_02 | case_533 → "Please remove me from your mailing list." | NOT_APPLICABLE `[]` | marketing opt-out phrased with "remove" | pass |
| cc_03 | case_533 → "My account was deleted by mistake. Could you restore it?" | NOT_APPLICABLE `[]` | restore request mentioning deletion | pass |
| cc_04 | sample case_17 → retention-clause deletion text | exactly case_17's answer | "backups may be kept" must not cancel the deletion | pass |
| cc_05 | sample case_21 → "Please unsubscribe me and delete my account entirely." | exactly case_21's answer | opt-out + deletion together | pass |
| cc_06 | sample case_29 → the subject's **current** email | exactly case_29's 14 steps | identity invariance; evidence exists only under the old email | pass |
| cc_07 | sample case_30 → old email in Mixed Case | exactly case_30's answer | email normalization | pass |
| cc_08 | synthetic identity change after audit_at | old email resolves; new values excluded before the change | temporal identity (unit tests) | pass |
| cc_09 | eval case_135, unchanged | `VERIFY_RECORD_ABSENT account_1417`; no "remaining" finding | ledger row recorded after its file's capture is ignored | pass |
| cc_10 | sample case_27 → `audit_at` 2026-09-17T12:00Z | INCOMPLETE; `REPORT_REMAINING_RECORD account_3866` citing evidence_02 | data re-created after deletion is reported once its evidence is usable | pass |
| cc_11 | eval case_261, unchanged | `VERIFY_RECORD_PRESENT legal_service/legal_hold_8017`; never deleted/redacted | legal-hold retention | pass |
| cc_12 | sample case_09 → `audit_at` 2026-09-16T08:00Z | INCOMPLETE; `REPORT_RESTORE_RISK backup_4978` citing activity_3709; nothing cites evidence_93/06 | two-clock rule with an earlier audit | pass |

The cases discriminate: cc_10 and cc_12 expect a different status/citation than their unchanged sources, and the harness tests prove wrong expectations are reported as failures.

## 4. Failures found and improvements made

From `plan/eval_history.md` and the phase logs, in order:

| # | Failure found | How it was found | Improvement | Effect |
|---|---|---|---|---|
| 1 | Intent rules missed 5 free-form sample texts ("remove that search result", "profile is gone") | first rule version: eval 518/518 but samples 27/32 | broadened deletion paraphrases + guards (restore requests, mailing-list removal, multilingual negations) | samples 32/32, eval unchanged (508/10) |
| 2 | Identity: an email live at audit time but changed later did not resolve | synthetic unit test | match against the as-of value set; "current" = value live at audit_at | robustness for hidden tests |
| 3 | Deleted accounts / anonymized analytics have no identifiers | sample walkthrough (e.g. account_6440 appears only in a 404 and one activity row) | workflow-timing linker with joint assignment over all requests | accounts 31/32 |
| 4 | Stale evidence from a subject's earlier request linked wrongly (object_19, account_6523) | linking measurement on samples | request window: state evidence must be in [requested_at, audit_at] | precision 0.963 → 1.000 on linked resources |
| 5 | Retained audit records expected but only visible in post-audit files | sample comparison | user-approved rule: membership may use any evidence; state/citations never | non-account recall 0.823 → 0.886 |
| 6 | INCOMPLETE cases consumed ambiguous anonymized-analytics records needed by COMPLETE cases | case_25/26 diffs | two-pass attribution (only provisionally COMPLETE cases compete) | analytics 10/13 → 13/13 |
| 7 | Subject-order tie-break wrong for case_03 vs eval case_44 | case_03 diff | case-number order (consistent with 3/3 sample collision groups); documented as last resort | resource sets 29/32 |
| 8 | Tried "prefer evidenced account in ties" | eval health report | **reverted** — no sample gain, one eval case lost evidence | — |
| 9 | Screenshot prompt v1 marked a compliant tombstone IDENTIFIABLE (it counted the permitted user_id as identifying) | fixture test vs manual transcription | prompt v2 definitions (user id identifying only for analytics) | 11/11 images match |
| 10 | Tried "audit records need a supplied retention period" | case_45 review | **rejected** — 12 of 24 sample-expected audit records have no retention evidence | — |
| 11 | Harness variants renamed to `cc_*` changed the case-order tie-break | cc_05/cc_06 failed on first run | variants keep the source case id; tie-break sensitivity recorded as a limitation | 12/12 |

## 5. Evaluation set (518 requests) — no answer key, so checked differently
- **Contract validity:** `code/validate_output.py` passes all 518 rows (header, ids, order, JSON, step numbering, phase/operation order, allowed pairs, evidence rules, every cited id exists and is dated ≤ audit_at).
- **Determinism / reproducibility:** two runs, a keyless run, and a `--no-llm` run produce byte-identical files.
- **Output profile:** COMPLETE 154 / INCOMPLETE 354 / NOT_APPLICABLE 10; findings and remediations paired (367 `REPORT_REMAINING_RECORD` ↔ 367 `DELETE_RECORD`); 64 distinct evidence files cited; 62 non-English requests handled.
- **Confidence census** (508 deletion cases): 371 (73%) rely only on high-confidence links (identifiers, references, catalog, unique timing). The rest use a last-resort tie-break: 90 for the account only, 23 for an anonymized-analytics record only, 18 for both, plus 4 naming fallbacks; in 73 of the 108 account tie-breaks the case is INCOMPLETE, where only one verification step's `resource_id` is at stake.
- **Manual spot checks:** 21 eval cases verified against raw evidence (NOT_APPLICABLE texts, Portuguese/Korean requests, historical emails incl. a three-email chain, screenshot scenarios, the post-capture trap row, tombstones, a legal hold, replica drift, restore risk, active flows, a large COMPLETE case, a tie-break case, the shared-subject pair) — **21/21 correct** (log in `plan/phases/phase8.md`).

## 6. Limitations
- **Concurrent-workflow ties:** when several requests share `reported_at` and the candidate records carry no identifiers, the assignment falls back to case order (a generator-order artifact, not evidence). Expected effect: occasional wrong `resource_id` on a verification step; statuses are rarely affected.
- **Unreachable sample resources:** two expected audit records exist nowhere in participant data and are never fabricated.
- **Audit-record multiplicity:** case_45 verifies all six user_03 audit records shown in a screenshot; samples only ever show one per subject, but no evidence-based rule separates them.
- **COMPLETE without citable account evidence:** 3 eval cases (45, 126, 127) keep the account verification with an empty `evidence_id` (user-approved policy) because nothing in the case window observes the account.
- **Screenshot facts depend on the vision model;** they are validated against a schema and against manual transcriptions (11/11), then frozen in the committed cache.
