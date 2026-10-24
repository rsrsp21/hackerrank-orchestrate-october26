# Phase 5 — Policy Engine & Step Generation

**Time box:** ~3h (scheduled Oct 24 night; running ahead of plan)
**Goal:** turn every `CaseInvestigation` into the exact `deletion_status` + `steps_json`, write root `output.csv`, and measure step-level accuracy on the 32 samples. After this phase a complete, contract-valid submission exists (the image-dependent cases improve later in P7).
**Governing docs:** constitution Part II Phase 5 + Art. 6 (output contract); guardrails P5 + §6 + §9.2; sample_walkthrough C1–C7, C19; problem_statement "Allowed Operations" and "Rules".

---

## 1. Entry gate
- [x] P4 produces per-case resource states with evidence (`investigate_all`; samples status 32/32, recall 0.973, precision 0.991, evidence 75/75).
- [x] Conventions from P1 documented (C1–C20).

## 2. Facts this phase relies on
| Fact | Source |
|---|---|
| Sample JSON style: compact separators `,` `:`, standard CSV quoting (`""` inside quoted field); **key order varies between rows** (grader ignores it) | `dataset/sample_output.csv` |
| Eval status mix (pre-image-facts): 346 INCOMPLETE / 162 COMPLETE / 10 NOT_APPLICABLE | investigation_report.py |
| Compliant (already-treated) items occur **only** in COMPLETE cases: 124 anonymized analytics, 36 redacted support, 36 disabled flows, 36 blocked backups, 5 redacted tombstones; **no** non-account ABSENT items | phase-5 check |
| COMPLETE cases with no citable evidence: account in 11 cases (9 image-dependent + 126, 127); retained audit record in 8 cases | phase-4/5 checks |
| Case ids sort numerically (case_33 … case_550) and the input file is in that order | data_notes Q1 |

## 3. Design: `code/policy.py` (pure) + `code/main.py` (I/O)

### 3.1 Operation tables (problem statement)
| action | FINDING (state) | REMEDIATION (state) | VERIFICATION (state) |
|---|---|---|---|
| DELETE | REPORT_REMAINING_RECORD (PRESENT) | DELETE_RECORD (ABSENT) | VERIFY_RECORD_ABSENT (ABSENT) |
| REDACT | REPORT_EXPOSED_PII (PRESENT) | REDACT_RECORD (REDACTED) | VERIFY_RECORD_REDACTED (REDACTED) |
| ANONYMIZE | REPORT_EXPOSED_PII (PRESENT) | ANONYMIZE_RECORD (ANONYMIZED) | VERIFY_RECORD_ANONYMIZED (ANONYMIZED) |
| DISABLE | REPORT_ACTIVE_DATA_FLOW (ACTIVE) | DISABLE_DATA_FLOW (DISABLED) | VERIFY_DATA_FLOW_DISABLED (DISABLED) |
| BLOCK | REPORT_RESTORE_RISK (ACTIVE) | BLOCK_RESTORE (BLOCKED) | VERIFY_RESTORE_BLOCKED (BLOCKED) |
| RETAIN | — | — | VERIFY_RECORD_PRESENT (PRESENT) |
| compliant NONE (ABSENT/ANONYMIZED/REDACTED/DISABLED/BLOCKED) | — | — | the matching VERIFY_* (COMPLETE cases only) |

Operation order index (sort key), from the problem-statement table:
FINDING: REMAINING, EXPOSED_PII, ACTIVE_DATA_FLOW, RESTORE_RISK · REMEDIATION: DISABLE, BLOCK, DELETE, REDACT, ANONYMIZE · VERIFICATION: ABSENT, PRESENT, REDACTED, ANONYMIZED, DISABLED, BLOCKED.

### 3.2 Rules
1. **NOT_APPLICABLE** → `[]`.
2. **INCOMPLETE** (≥1 finding):
   - FINDING per action item (account included when it is a finding), `evidence_id` = the state evidence;
   - REMEDIATION per action item, `evidence_id=""`;
   - VERIFICATION: the account `VERIFY_RECORD_ABSENT` (always, C2), each retained record `VERIFY_RECORD_PRESENT`, each remediated item's verification; all `evidence_id=""`; compliant items are **not** listed (C5).
3. **COMPLETE** (no finding): VERIFICATION only — account ABSENT, retained PRESENT, each compliant item's VERIFY_* — each citing its proving evidence (C4).
4. **Sort** within a phase by (operation index, system_id, resource_id); phases FINDING → REMEDIATION → VERIFICATION; `step_no` 1..n.
5. **One step per (phase, operation, resource)**: never duplicate the account verification when the account is also remediated.
6. **Serialize** `json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`; CSV via `csv.writer` (QUOTE_MINIMAL), header `case_id,deletion_status,steps_json`, rows sorted numerically by case id.
7. **Missing citable evidence in a COMPLETE case** (account in 11 eval cases, retained record in 8): ⚠ guardrails §6 says COMPLETE verifications must cite evidence → **stop-and-ask decision (task 5.4)**. Options: (a) emit the step with `evidence_id=""`; (b) omit the step; (c) cite the workflow activity (a claim, not proof). Recommendation: (a) for the account (C2 says it is always present) and (b) for retained records that are only known from post-audit evidence (they cannot be proven present at audit).

### 3.3 `code/main.py`
`uv run python code/main.py [--data dataset] [--out output.csv]` → build index → investigate_all → policy → write root `output.csv` (all 518 eval cases; samples are not written). Prints a run summary (status counts, timing).

### 3.4 Validator `code/validate_output.py` (guardrails §9.2; pulled forward from P8)
Header; 518 rows equal to the input case set; numeric sort; no duplicates; status vocabulary; JSON array of objects with exactly the 7 keys; consecutive step_no; phase order; within-phase sort order; allowed operation/state pairs; NOT_APPLICABLE ⇔ `[]`; COMPLETE ⇒ verification-only; INCOMPLETE ⇒ ≥1 finding and empty evidence on remediation/verification; every cited evidence id exists (file_id / activity_id / audit_id) and is dated ≤ the case's audit_at.

## 4. Tasks
- [x] 5.1 `code/policy.py` (2026-10-24): ACTION_STEPS / COMPLIANT_VERIFICATION / OPERATION_ORDER tables, explicit ALLOWED (15 pairs = problem statement), `steps_for(inv)`, `serialize()`. 5.4 policy knobs present with the recommended defaults (account without evidence → keep with ""; retained without evidence → omit), pending the user decision. **Samples: sequence exact 29/32 = ceiling** (diffs only cases 18, 20 unreachable, 23 tie).
- [x] 5.2 `code/tests/test_policy.py` (8 tests): allowed pairs, NOT_APPLICABLE `[]`, INCOMPLETE structure + empty evidence + flow-before-delete order, no duplicate account step, COMPLETE verification-only with evidence, every emitted pair allowed and sorted over all 550 cases, samples sequence-exact except the 3 known, compact sorted JSON round-trip. **Correction:** the sample file mixes JSON key orders (only 8/32 rows are byte-identical to sorted-key output), so equality is semantic (the grader parses JSON). Suite: 126 passed.
- [ ] 5.3 Sample scoring script `code/evaluation/score.py` (the seed of the P6 harness): status accuracy, step-level exact match (multiset), field-level accuracy per field, sequence exact match, per-case diff. Run on the 32 samples.
- [ ] 5.4 **Decision with the user:** policy for COMPLETE steps lacking citable evidence (§3.2 rule 7). Record it in the constitution/guardrails if the rule changes.
- [ ] 5.5 `code/main.py` + `code/validate_output.py`; generate root `output.csv`; the validator passes; two runs byte-identical.
- [ ] 5.6 Update data_notes / phase files; commit. A first submittable `output.csv` exists (fallback copy kept per guardrails P8).

## 5. Exit gate
- [ ] Samples: status 32/32; sequence exact ≥ 28/32 (ceiling: 29 given the 2 unreachable audit records and the case_23 tie); field-level accuracy reported.
- [ ] Root `output.csv`: 518 rows, validator green, deterministic (hash equal across two runs).
- [ ] Tests green; committed.

## 6. Guardrail reminders
- Only allowed operation/state pairs; never DELETE a RETAIN category or a tombstone.
- Remediation and verification in INCOMPLETE cases always have `evidence_id=""`.
- No hand edits of `output.csv`; it is produced only by `code/main.py`.
- Sample answers are used only for scoring, never read by the pipeline.
