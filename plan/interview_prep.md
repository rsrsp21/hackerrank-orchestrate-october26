# AI Interview Preparation

The interviewer will ask about architecture, investigation approach, remediation planning, and evaluation, and will probe with **hidden test cases** ("what would your system do if…"). Below: a pitch, two worked cases, the decisions and their evidence, numbers to quote, scenario answers with the code that implements each, and honest limitations.

---

## 1. Two-minute pitch
"For each deletion request we first decide, from the text alone, whether the person really asked for deletion — rules in six languages where refusals like 'not a request to erase' or 'marketing lists only' override deletion words. Then we resolve exactly one user from the email, including old emails, and collect every email, hash, and phone that user had at audit time.

We parse all 94 evidence files — SQL replicas, JSON exports, ledgers, seven log formats, PDFs, and screenshots read by Gemini — into one kind of record: an observation of one resource's state at one time, with two timestamps: when the file was captured and when the record itself was observed. An observation counts only if both are at or before audit_at and it was observed after the request.

We link resources to the person by exact identifiers, references, and data-catalog links. Records that were already deleted or anonymized have no identifiers left, so we link them through the deletion workflow's timing in the activity log, assigned jointly across all 550 requests. For each resource we take the latest valid observation, apply deletion_rules.csv, and emit findings, then remediation in a safe order — disable flows and block restores first — then the verifications. Activity results like 'SUCCESS' are treated as claims, never as proof.

On the 32 public samples we get 100% status accuracy, step F1 0.99, and 29 of 32 exact answers, which is the ceiling — two expected records appear nowhere in the data and one is a genuine tie. It costs under nine cents of Gemini, and it reproduces byte-for-byte without an API key."

## 2. Worked cases (know these cold)

**case_21 (sample, COMPLETE)** — "I deleted my account… verify the profile is gone."
1. Intent: "deleted my account" → DELETION.
2. Identity: amara-okeke@proton.me → user_21 (current).
3. The account `account_6440` carries no identifier anywhere: it appears only in a 404 lookup (evidence_92) and one activity row `DELETE_RECORD SUCCESS` 59 min before `reported_at`. Workflow timing links it (COMPLETE ↔ SUCCESS).
4. `analytics_5335` is anonymized (all identifiers null) — linked by the workflow's "Policy action completed" step at `reported_at − 29 min`.
5. `audit_record_3737` has `subject_reference=user_21`.
6. States at audit 09-15: account 404 → ABSENT; analytics → ANONYMIZED; audit record → PRESENT (retained).
7. No findings → COMPLETE with 3 verifications, all citing evidence_92 (the latest capture before audit).

**case_29 (sample, INCOMPLETE)** — requested with the **old** email noah.f438085.
1. Identity resolves via `audit_284` (email change) → user_29 with both emails.
2. evidence_92 (09-15) shows: search_1993 hit for the old email → REMAINING; analytics_5208 with the email → EXPOSED_PII → ANONYMIZE; support ticket with requester_email → EXPOSED_PII → REDACT; connector enabled → ACTIVE_DATA_FLOW → DISABLE.
3. Steps: 4 findings (citing evidence_92), 4 remediations ordered DISABLE → DELETE → REDACT → ANONYMIZE, then verifications for the account, the retained audit record, and each remediated item (all with empty evidence — future work).

## 3. Decisions and the evidence behind them
| Decision | Evidence that forced it | Code |
|---|---|---|
| Activity results are claims | 368 of 890 DELETE_RECORD rows are FAILED, many SUCCESS rows are contradicted by later snapshots | `evidence/activity.py` |
| Two clocks (file capture + record time) | evidence_13 / evidence_36 contain rows recorded *after* their file was captured; case_09 cites evidence_93, not evidence_06 whose lines precede audit but whose file is captured after | `evidence/model.py::Observation.usable` |
| Request window | every one of the 75 sample citations lies in [requested_at, audit_at]; earlier observations belong to an earlier request of the same person | `evidence/index.py::state_at` |
| Membership may use post-audit evidence (state never) | 5 expected retained audit records are visible only in post-audit files (approved as constitution Art. 3.5) | `linking.py` horizon |
| Direct observation beats omission | case_21 cites evidence_92's 404, not the later empty snapshot evidence_51 | `index.py::state_at` |
| Omission only from topology snapshots / explicit empty extracts | case_04 cites evidence_54, never the empty inventory evidence_90 | `evidence/sql.py`, `records.py` |
| Workflow timing for identifier-less records | account delete within −90…+15 min of reported_at with result ↔ status; policy actions at fixed offsets (−29 analytics, −22 support, −15 flow, −8 backup) learned from identifier-linked workflows | `workflow.py` |
| Two-pass analytics attribution | INCOMPLETE cases never list compliant records, so they must not consume ambiguous ones (fixed cases 25/26) | `investigate.py` |
| Case-order tie-break (last resort) | matched 3/3 sample collision groups (subject order 2/3, queue order 1/2) | `workflow.py::_assign` |
| Exact identity only | duplicate names, decoys (`.jr` emails, popescu/ionescu, Berglund/Berg), unknown user ids | `identity.py`, `evidence/model.py::link_keys_from` |
| Catalog link rejected on identity conflict | marketing_001's screenshot shows another person's email while a catalog row links it to user_09 | `investigate.py::identity_conflict` |
| Analytics keyed only by an old hash → DELETE | sample case_12 (contact lookup by old email hash) | `evidence/logs.py`, `investigate.py::ACTIONS` |
| Support message REDACT vs attachment DELETE | rule_05 vs rule_06; samples 07/10/13 vs 11/18/19 | `interpret.py`, `investigate.py` |
| Account always verified; retained records verified present | every sample answer verifies the account; bulk cases verify the audit record | `policy.py` |
| COMPLETE account step with "" when nothing proves it | user decision (guardrails §6 amendment) | `policy.py::ACCOUNT_WITHOUT_EVIDENCE` |
| LLM = fact extractor, cached | determinism, cost, explainability; keyless reproducibility | `llm.py`, `image_extract.py` |

## 4. Numbers to quote
- Samples: status **32/32**, step F1 **0.990**, sequence **29/32 = ceiling**, evidence **75/75**; custom cases **12/12**; spot checks **21/21**; tests **152**.
- Eval output: 518 rows — COMPLETE 154, INCOMPLETE 354, NOT_APPLICABLE 10; validator green; deterministic.
- Identity: 418 current + 100 historical emails, 0 unresolved. Intent: 508 deletion + 10 not applicable.
- Evidence: 94 files → 3,000+ observations in ≈1 s; whole run ≈5 s.
- Confidence: 371/508 deletion cases (73%) use only high-confidence links.
- Gemini: 11 calls, 22,576 in / 3,943 out tokens, **$0.085 total, $0.00016 per request**; 0 live calls in the final run.

## 5. Hidden-test scenarios — what the system does
| If the test case has… | The system… | Where |
|---|---|---|
| a refusal in another language ("No quiero eliminar…", "Je ne demande pas la suppression") | override cue wins → NOT_APPLICABLE `[]` | `intent.py` OVERRIDE_CUES |
| a marketing opt-out / access / correction / restore request | override cue or non-deletion topic → NOT_APPLICABLE | `intent.py` |
| "delete my account, you may keep backups" | still DELETION; backups are BLOCK_RESTORE, never deleted | `intent.py`, `investigate.py` |
| an unclear text no rule decides | cached Gemini fallback; without an answer it stays non-deletion | `intent.classify_with_fallback` |
| a request using an old email | resolves through the audit log; old emails/hashes/phones all link evidence | `identity.py` |
| an email in UPPERCASE or inside free text | normalized / regex-extracted before matching | `identity.extract_emails` |
| a look-alike decoy (`.jr` email, similar name) | never linked — exact identifiers only, names ignored | `linking.py` |
| reported COMPLETE but data still present | INCOMPLETE with findings — reported status is ignored | `investigate.py` |
| deletion SUCCESS in the activity log but a later snapshot shows the row | the snapshot (latest observation) wins → finding | `index.state_at` |
| data deleted, then re-created by a sync/restore **before** audit_at | latest observation is PRESENT → finding (cc_10 shows it) | `index.py`, `activity.py` |
| re-creation **after** audit_at, or a file captured after audit_at | ignored (two clocks) | `Observation.usable` |
| primary deleted, a replica still holds the row | finding on `account_service` for that record | `sql.py`, `investigate.py` |
| a tombstone still showing name/email/phone/hash | REPORT_EXPOSED_PII → REDACT_RECORD (keep user_id) | `ACTIONS` |
| a legal hold or security audit record | VERIFY_RECORD_PRESENT; never deleted (cc_11) | `RETAINED` |
| a backup that can still be restored | REPORT_RESTORE_RISK → BLOCK_RESTORE → VERIFY_RESTORE_BLOCKED | `ACTIONS` |
| an enabled connector / heartbeat | REPORT_ACTIVE_DATA_FLOW → DISABLE first in remediation | `policy.OPERATION_ORDER` |
| analytics still showing identifiers | EXPOSED_PII → ANONYMIZE; all-null → verified ANONYMIZED | `interpret.py` |
| a screenshot or PDF as the only evidence | Gemini facts / pdfplumber text become observations with the file's capture time | `images.py`, `documents.py` |
| a catalog link contradicted by the record's own identifiers | link rejected | `identity_conflict` |
| several requests sharing reported_at with identifier-less records | joint assignment; last resort case order (known limitation) | `workflow.py` |
| no API key on the grader's machine | cache-only run, byte-identical output | `llm.py` |

**Why remediation is ordered DISABLE → BLOCK → DELETE → REDACT → ANONYMIZE:** stop anything that can re-create data (flows, restores) before deleting, otherwise a sync would bring the deleted record back; this is also the operation order the contract specifies.

## 6. Honest limitations (say these before being asked)
- Ties between concurrent identifier-less workflows are broken by case order — a generator-order artifact, documented, used only after evidence-based elimination; it affects mostly a verification `resource_id` in INCOMPLETE cases.
- Two sample-expected audit records exist nowhere in the data; we never fabricate them.
- case_45 verifies six audit records of one subject; the samples only show one per subject, and a retention-period rule that would separate them contradicts 12 sample records, so it was rejected.
- Three COMPLETE eval cases have no in-window evidence for the account; the step is kept with an empty evidence id by an explicit, documented decision.

## 7. Process story (for "how did you build it?")
Constitution + guardrails + phase gates; data exploration with re-runnable scripts before any pipeline code; every sample step explained by hand (20 conventions); each rule justified by evidence and measured on the samples; changes that did not help were reverted (2 recorded); custom cases written before running; LLM added last, behind a cache, measured against a frozen baseline; 21 eval cases checked manually against raw evidence. All in `log.txt` and `plan/`.
