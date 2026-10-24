# Evaluation History

Every logic change is measured with `uv run python code/evaluation/main.py` (32 public samples + custom cases). Newest last.

| Date (UTC) | Change | Status acc. | Step P / R / F1 | Seq. exact | Custom | Notes |
|---|---|---|---|---|---|---|
| 2026-10-24 | Phase 4 first investigation (subject-order tie-break) | 32/32 | n/a | n/a | n/a | resource sets 28/32; case_03 wrong analytics |
| 2026-10-24 | Case-number tie-break (Q11 revised) + two-pass analytics | 32/32 | n/a | n/a | n/a | resource sets 29/32; evidence 75/75 |
| 2026-10-24 | Rejected: prefer in-window-evidenced account in ties | 32/32 | n/a | n/a | n/a | no sample gain; eval case_226 lost account evidence, reverted |
| 2026-10-24 | **Baseline after Phase 5** (policy + output) | 1.0000 | 0.9948 / 0.9845 / 0.9896 | 0.9062 (29/32 = ceiling) | n/a | diffs: unreachable audit_record_6645, audit_record_5569; case_23 3-way tie |
| 2026-10-24 | Phase 6 harness + 12 custom cases | 1.0000 | 0.9948 / 0.9845 / 0.9896 | 0.9062 | 10/12 then **12/12** | cc_05/cc_06 exposed tie-break sensitivity to case ids; harness variants keep the source id |

| 2026-10-24 | Phase 7: Gemini image facts (prompt v1 → v2 after a tombstone-definition bug), label resolution, Q9 rule active | 1.0000 | 0.9948 / 0.9845 / 0.9896 | 0.9062 | 12/12 | samples unchanged (no sample cites an image); 10 eval image scenarios changed; COMPLETE 162 → 154; COMPLETE without account evidence 11 → 3 |
| 2026-10-24 | Rejected: require a supplied retention period for retained audit records | n/a | n/a | n/a | n/a | 12 of 24 sample-expected audit records lack retention evidence, so the rule would break correct answers |

Field accuracy at baseline: step_no 0.9896, phase 0.9896, system_id 0.9689, resource_id 0.9637, operation 0.9689, state 0.9689, evidence_id 0.9896.
Eval output at baseline: 518 rows, COMPLETE 162 / INCOMPLETE 346 / NOT_APPLICABLE 10; the 11 image files are not used yet.
