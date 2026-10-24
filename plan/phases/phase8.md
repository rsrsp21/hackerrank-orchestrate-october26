# Phase 8 — Final Run & Output Validation

**Time box:** ~1–1.5h
**Goal:** produce the submission `output.csv` from a clean run, prove it is contract-valid, deterministic, and reproducible without a key, and **manually verify 20 eval cases against the raw evidence** (the graded set has no answer key, so this is the only direct check of eval-side correctness).
**Governing docs:** constitution Part II Phase 8; guardrails P8 + §9.2; plan/scoring_plan.md (Output CSV /30).

---

## 1. Entry gate
- [x] P6 exit gate met (harness: samples at ceiling, custom 12/12).
- [x] P7 closed (image facts committed; keyless runs byte-identical).

## 2. Tasks
- [x] 8.1 Clean run, validator VALID (518 rows); run 1 = run 2 = keyless (`GEMINI_API_KEY=`) = `--no-llm` = previous committed output — **sha256 0d80a7d4bad67187…**.
- [x] 8.2 Tests 152 passed; harness: samples status 1.0000, step F1 0.9896, sequence 0.9062 (ceiling); custom 12/12.
- [x] 8.3 Profile (`code/explore/spot_check.py --profile`): COMPLETE 154 / INCOMPLETE 354 / NOT_APPLICABLE 10; steps per case 0–14; only allowed operations; REPORT_REMAINING_RECORD 367 = DELETE_RECORD 367 (findings ↔ remediations paired); 64 distinct evidence ids cited (all exist and are ≤ audit_at — validator); 62 non-ASCII request texts. No diff vs the last committed output.
- [x] 8.4 **21 manual spot checks — 21/21 correct, no defect** (log below).
- [x] 8.5 Frozen: `output.csv` committed; copy `code/cache/output_final.csv`; hash above.

## 3. Exit gate ✅ (2026-10-24)
- [x] Validator passes; two runs + keyless + `--no-llm` byte-identical.
- [x] Tests + harness green; no regression.
- [x] 21/21 spot checks reviewed; no defect found.
- [x] Committed with the recorded hash.

## 4. Spot-check log (each verified against the raw evidence via `spot_check.py`)
| # | Case | Covers | Result | Verdict / reason |
|---|---|---|---|---|
| 1 | case_533 | NOT_APPLICABLE (phone update, "leave the account active") | NOT_APPLICABLE `[]` | ✔ override cue |
| 2 | case_539 | NOT_APPLICABLE (access request, "not a request to erase") | NOT_APPLICABLE `[]` | ✔ override cue |
| 3 | case_54 | Portuguese deletion | INCOMPLETE, 14 steps, all findings from evidence_05 (read replica 09-21 = audit) | ✔ search present, analytics/support identifiable, flow enabled; account absent by omission; retained audit verified |
| 4 | case_66 | Korean deletion + historical email (audit_286) | INCOMPLETE: support_4249 exposed (evidence_93 requester fields) | ✔ evidence_06 (captured after audit) not cited; retained audit listed without evidence |
| 5 | case_37 | 3-email chain subject (user_35) | INCOMPLETE: search_1934 + data_flow_2528 from the 10-01 handover | ✔ handover captured exactly at audit_at |
| 6 | case_40 | historical email (audit_303) | INCOMPLETE: search_3200, support_4887 (handover) | ✔ matches sample case_11/13 pattern |
| 7 | case_34 | image: live account | INCOMPLETE: account_5762 PRESENT (evidence_04 screenshot 09-26) | ✔ in window [09-24, 09-27] |
| 8 | case_46 | image: tombstone + early-episode subject | COMPLETE: account_6523 404 (evidence_67), tombstone_17 REDACTED (evidence_42) | ✔ the post-audit-only audit record omitted (5.4 decision) |
| 9 | case_61 | image: attachment via file-name label | INCOMPLETE: object_19 (evidence_46, catalog "belongs only to") | ✔ account via L6 naming fallback (no anchor) |
| 10 | case_135 | trap row after file capture | COMPLETE: account_1417 ABSENT @08-12 (evidence_13) | ✔ the 08-14 FOUND row ignored |
| 11 | case_544 | tombstone with PII | INCOMPLETE: REDACT tombstone_8648 (evidence_52) | ✔ like sample case_32 |
| 12 | case_543 | compliant tombstone | COMPLETE: tombstone_205 REDACTED + audit present (evidence_52); account omission evidence_51 | ✔ evidence_52 holds no account table, so 51 is the latest omission proof |
| 13 | case_261 | legal hold + replica drift (Korean) | INCOMPLETE: account_3150 only in read replica (evidence_24), legal_hold_8017 RETAIN | ✔ C12 + rule_13 |
| 14 | case_105 | replica drift | INCOMPLETE: account_6345 in read replica (evidence_10) | ✔ C12 |
| 15 | case_55 | image: restore risk | INCOMPLETE: backup_9287 RESTORE_ALLOWED (evidence_32) | ✔ the 08-22 restore activity is after audit, ignored |
| 16 | case_104 | flow + full finding set | INCOMPLETE: 4 findings from evidence_10 | ✔ matches sample case_18 pattern |
| 17 | case_41 | large COMPLETE (historical email) | COMPLETE: 6 verifications all citing evidence_03 | ✔ anonymized analytics via unique workflow link |
| 18 | case_58 | tie-break COMPLETE | COMPLETE: account_9862 absent by omission (evidence_05), analytics_8858 anonymized | ✔ structurally correct; the tie-break choice itself is the known uncertainty |
| 19 | case_126 | COMPLETE without citable account evidence | account step with `""` | ✔ user decision 5.4 (only post-audit evidence_12 shows the account) |
| 20 | case_33 | shared subject (later episode) | INCOMPLETE: export_1842 via statement PDF evidence_18 | ✔ catalog label NST-2026-0718-1842 |
| 21 | case_52 | shared subject (earlier episode) | INCOMPLETE: export_1260 via screenshot evidence_23 | ✔ independent episode, own window |
