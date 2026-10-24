# Guardrails — Ghost Data Still Exists

Concrete, checkable rules that put `plan/constitution.md` into practice. Before any change, check the relevant sections. Before any commit or submission, run the checklists in §9.

---

## 1. Session Guardrails (every agent session)

- [ ] Read `AGENTS.md`, `plan/constitution.md`, this file, and `plan/phasewiseplan.md` before acting.
- [ ] Append a `SESSION START` entry, then one per-turn entry, to root `log.txt`. `tool=Claude Code` and `model=<exact runtime id>`. Re-read the entry after writing it.
- [ ] State the time remaining until 2026-10-26T00:30Z (06:00 IST). If under 2h, remind the user to submit.
- [ ] Work on the current phase in `phasewiseplan.md`. Don't jump ahead without saying so.
- [ ] Sub-agents log to the same `log.txt` with `parent_agent=` set.

## 2. Data Access Guardrails

| Allowed | Forbidden |
|---|---|
| Anything under `dataset/` | Files outside `dataset/` used as prediction input |
| `sample_output.csv` for evaluation and learning conventions | Looking up sample answers at prediction time |
| Derived caches built from `dataset/` | Hardcoded `case_id` → answer maps, or `if case_id == ...` |
| Generic rules learned from samples | Rules that only fire for a specific sample resource ID |

- Never search the filesystem, git history, or the web for golden answers or generator code.
- Code must resolve paths relative to the repo root (works on Windows, macOS, and Linux).

## 3. Temporal Guardrails

- Filter before reasoning: `captured_at <= audit_at`, `event_time <= audit_at`.
- **Two clocks per observation** (data_notes §3.1): use it only if **both** the file's manifest `captured_at` **and** the record-level time (`observed_at` / `recorded_at` / snapshot `captured_at` / log line ts) are `<= audit_at`. Known traps: evidence_13 (`account_1417`, FOUND @08-14 after capture 08-12) and evidence_36 (`account_5043`, FOUND @04-11 after capture 04-09).
- **Request window:** state evidence must be observed in `[requested_at, audit_at]`. Earlier observations describe an earlier episode (e.g. object_19 / account_6523 for the same subjects' earlier requests).
- **Membership vs state (constitution Art. 3.5):** linking may use post-audit evidence; state and citations never do.
- Identity history is valid only up to `audit_at`.
- Never cite evidence captured after `audit_at`. The validator must enforce this.
- Compare timestamps as parsed UTC datetimes, never as raw strings with mixed formats.

## 4. Evidence Guardrails

- A finding needs the specific evidence ID that shows the record or flow **at or before `audit_at`**, linked through an identifier of the subject.
- `reported_result=SUCCESS` on a delete is not proof of absence. Look for a later snapshot or record showing the state.
- A sync, import, or restore after a deletion can recreate data. Check events after the deletion and before `audit_at`.
- With SQL replicas, check every replica table. Primary absent but replica present means the replica is a finding.
- If several files prove the same fact, follow the convention learned from the samples (document it in `plan/data_notes.md`), and apply it consistently.
- PDFs and images: extract the facts once, cache them, and match the identifiers exactly (after normalization).

## 5. Identity Guardrails

- Normalize: emails lowercased and trimmed; phones compared digits-only; names Unicode NFC, case-folded.
- Check the email-hash algorithm against `user_identities.csv` before relying on it.
- Request email not resolvable → don't guess. Investigate, and log it as a known failure in the evaluation report.
- Matching on name alone is not enough to link a record (decoys exist). It needs email, phone, hash, `user_id`, or resource-ID linkage.

## 6. Policy & Step Guardrails

Allowed combinations only:

| Phase | Operation → State |
|---|---|
| FINDING | REPORT_REMAINING_RECORD→PRESENT, REPORT_EXPOSED_PII→PRESENT, REPORT_ACTIVE_DATA_FLOW→ACTIVE, REPORT_RESTORE_RISK→ACTIVE |
| REMEDIATION | DISABLE_DATA_FLOW→DISABLED, BLOCK_RESTORE→BLOCKED, DELETE_RECORD→ABSENT, REDACT_RECORD→REDACTED, ANONYMIZE_RECORD→ANONYMIZED |
| VERIFICATION | VERIFY_RECORD_ABSENT→ABSENT, VERIFY_RECORD_PRESENT→PRESENT, VERIFY_RECORD_REDACTED→REDACTED, VERIFY_RECORD_ANONYMIZED→ANONYMIZED, VERIFY_DATA_FLOW_DISABLED→DISABLED, VERIFY_RESTORE_BLOCKED→BLOCKED |

- Sort key inside a phase: (operation index in the table above, `system_id`, `resource_id`).
- Every remediated record or flow gets a matching verification step.
- RETAIN categories are never deleted. They get `VERIFY_RECORD_PRESENT` where the convention requires it.
- Tombstone gets REDACT (keep `user_id`), not DELETE.
- `COMPLETE` ⇒ only VERIFICATION steps, all with non-empty evidence IDs.
- `INCOMPLETE` ⇒ at least one FINDING; REMEDIATION and VERIFICATION `evidence_id == ""`.
- `NOT_APPLICABLE` ⇒ `[]`.

## 7. Intent Classification Guardrails

- Deletion means erase, close-and-delete, or remove personal data, in any language.
- Non-deletion: access, copy or export, correction or update, marketing opt-out or unsubscribe, questions, complaints, or anything else.
- A text mentioning deletion only to say they *don't* want it, or asking a question about deletion, is not authorization.
- Rule-based first; LLM only for ambiguous or non-English texts; cache the results.

## 8. Code & LLM Guardrails

- Entry point: `python code/main.py` writes root `output.csv`. Evaluation: `python code/evaluation/main.py`.
- Keep modules small and explainable (loaders, intent, identity, investigate, policy, llm, validate).
- LLM: temperature 0, disk cache keyed by input hash, every call's tokens recorded for `usage_report.md`.
- API keys only via env vars. `.env` and `code/cache/` in `.gitignore`.
- Prompts live in `.py` or `.md` files (the code judge ignores `.json` and `.csv`).
- Don't run the LLM over all 518 cases until the deterministic pipeline works on the samples.
- No sample-score regressions: re-run the sample evaluation after every logic change.

## 9. Checklists

### 9.1 Before every commit
- [ ] Sample evaluation re-run; score not lower than before (or the drop is explained).
- [ ] No secrets, `.env`, caches containing PII, or dataset copies staged.
- [ ] `log.txt` updated for this turn.

### 9.2 `output.csv` validator (must pass before any submission)
- [ ] Header is exactly `case_id,deletion_status,steps_json`
- [ ] 518 rows; the case_id set equals the input set; sorted; no duplicates
- [ ] Status ∈ {COMPLETE, INCOMPLETE, NOT_APPLICABLE}
- [ ] `steps_json` parses to a list of objects, each with exactly the 7 keys
- [ ] `step_no` = 1..n, consecutive
- [ ] Phase order respected; within-phase sort order respected
- [ ] Only allowed operation/state pairs
- [ ] Evidence rules (§6) hold; every cited ID exists in the dataset and is dated ≤ `audit_at`
- [ ] NOT_APPLICABLE ⇔ `[]`

### 9.3 Before packaging `code.zip`
- [ ] `README.md` has setup, env vars (names only), and run commands
- [ ] `code/evaluation/evaluation_report.md`: case, step, field, and sequence accuracy, ≥3 custom cases, failures and improvements
- [ ] `code/evaluation/usage_report.md`: providers, models, calls, tokens in/out, total/avg per request, cost total/per request, per-model and overall
- [ ] No `__pycache__`, `.venv`, `dataset/`, nested archives, `.env`, or secrets
- [ ] `code/requirements.txt` re-exported from `uv.lock` (`uv export --no-hashes --no-dev --format requirements-txt -o code/requirements.txt`)
- [ ] `Compress-Archive -Path README.md, pyproject.toml, uv.lock, code -DestinationPath code.zip -Force`

### 9.4 Submission
- [ ] `code.zip`, root `output.csv`, and `log.txt` (chat transcript) uploaded at the submission URL in `constitution.md`
- [ ] Submitted ≥3h before 06:00 IST, Oct 26

## 10. Stop-and-Ask Triggers

Pause and ask the user before:
- deleting or overwriting any file under `dataset/` (never needed);
- force-pushing or rewriting git history;
- spending a lot on LLM calls (such as a full 518-case multimodal pass) without caching in place;
- changing the output contract or this rule set.

---

# Part II — Phase Guardrails

Format for every phase:
- **Entry gate:** what must be true before starting.
- **Do:** mandatory practices.
- **Don't:** prohibited actions.
- **Self-checks:** run or answer before ticking a task.
- **Exit gate:** what must be true to close the phase.
- **Artifacts:** what must exist afterwards.

Gate protocol: before starting a phase, state in your reply which entry-gate items are met. Before closing it, show the exit-gate checklist with evidence (command output, file path). A waived gate is logged in `log.txt` and in the phase file.

## P1 — Setup & Data Exploration

- **Entry gate:**
  - [x] uv env works (`uv run python -c "import pdfplumber, pymupdf"`).
  - [x] `.gitignore` covers `.venv/`, `.env*`, and `code/cache/`.
- **Do:**
  - Put every exploration in a re-runnable script under `code/explore/` (no one-off REPL findings left undocumented).
  - Write findings to `plan/data_notes.md` with the source (script + section, or file/row ID).
  - Mark conventions inferred from fewer than 3 examples as **(tentative)**.
  - Open every evidence file family at least once. Images and PDFs are viewed, not assumed.
  - Cache extracted text to `code/cache/extracted/` with a deterministic file name per `file_id`.
- **Don't:**
  - write pipeline modules (`code/*.py` outside `explore/`) in this phase;
  - paste full names, emails, or phones into the notes when an ID will do;
  - treat the sample answers as a lookup table.
- **Self-checks:**
  - Can every step of every sample be explained by a specific evidence ID and rule?
  - Does each SQL file's table and column list exist in `data_notes.md`?
  - Have the temporal traps (files after a sample's `audit_at`) been identified?
- **Exit gate:**
  - [x] All 94 evidence files profiled.
  - [x] `plan/sample_walkthrough.md` explains all 32 samples.
  - [x] The system→category→operations catalogue is confirmed against the samples.
  - [x] Conventions written: evidence selection, account verification, tombstone, retain-verify, flow and restore.
  - [x] Open questions listed, each with a planned resolution phase.
- **Artifacts:** `code/explore/*.py`, `plan/data_notes.md`, `plan/sample_walkthrough.md`, `code/cache/extracted/`.

### P1 task-specific
| Task | Extra guardrails |
|---|---|
| 1.3 SQL | Load each file into its **own** in-memory SQLite DB; never mutate the source `.sql`. Record each table's columns, row counts, and the replica role (primary, read, regional, reporting, failover). Compare the same resource across replicas and snapshots to describe drift. Note how deleted, redacted, and anonymized values are represented. |
| 1.4 JSON/TXT/LOG | Record the JSON key structure per file family. For logs, record the line grammar and whether each line has its own timestamp. Decide which timestamp governs the cutoff (line time vs `captured_at`) and record the decision in data_notes. |
| 1.5 PDF/PNG | Extract PDFs with pdfplumber (pymupdf as fallback). View each PNG and transcribe *facts only* (system, resource IDs, identifiers, states, dates). Store transcriptions as `.md` under `code/cache/extracted/` (judges ignore `.json`). Use Phase 7 LLM vision in the pipeline later. |
| 1.6 Samples | For each case: resolved `user_id`, current or historical match, every expected step → proving evidence + rule + timestamp, and the plausible-but-excluded records and why. |
| 1.7 Catalogue | Every `system_id` in the samples' outputs mapped. Unseen systems are listed as "inferred from rules". |

## P2 — Request Intent Classification

- **Entry gate:**
  - [x] All distinct intent sentences and negation sentences catalogued (data_notes §1.3).
- **Do:**
  - Classify on the full text.
  - Build a rule set with two lists: deletion cues (all languages present) and override cues (negations, "only", "not a request to", "keep the account", access/export/correction/marketing/login topics).
  - Output a label plus the matched cue (for explainability).
  - Unit-test every distinct template sentence.
- **Don't:**
  - use `reported_status`, the email, the case ID, or `CLASSIFY_REQUEST` as the deciding signal;
  - call an LLM for texts the rules decide confidently.
- **Self-checks:**
  - All 508 template-deletion texts → deletion.
  - All 10 non-deletion texts (case_533–542) → NOT_APPLICABLE.
  - Trap sentences ("remove me from marketing lists only", "not a request to erase") → NOT_APPLICABLE.
- **Exit gate:**
  - [x] Classifier module and tests exist.
  - [x] Counts printed on eval (expected 508 / 10; investigate any deviation).
  - [x] ≥3 custom non-deletion cases added for Phase 6.

## P3 — Identity Resolution

- **Entry gate:**
  - [x] Hash algorithm confirmed: sha256(email).
  - [x] Audit-log semantics documented.
- **Do:**
  - Match the email against the current snapshot **and** every audit `old_value`/`new_value`, using only events with `event_time <= audit_at`.
  - Build the identifier set: emails, `sha256` of each, phones (raw + digits-only), name(s), `user_id`.
  - Return the provenance of the match (current vs historical, plus the `audit_id`).
- **Don't:**
  - match on name alone;
  - resolve to more than one user (raise and log instead);
  - include identifiers from changes dated after `audit_at`.
- **Self-checks:**
  - Eval: 518/518 resolved (418 current + 100 historical).
  - Samples: 32/32.
  - The two cases sharing one email resolve consistently.
- **Exit gate:**
  - [x] Resolution counts printed and matching expectations.
  - [x] Unit tests for current, historical, and post-`audit_at` change cases.

## P4 — Evidence Indexing & State Reconstruction

- **Entry gate:**
  - [x] P1 exit gate met (all evidence families understood).
  - [x] P3 resolver ready.
- **Do:**
  - Build the index once: identifier → occurrences `(evidence_id, system_id, resource_id, observed_at, fields)`.
  - Filter per case on `captured_at` / `event_time` ≤ `audit_at`.
  - Compute the state per resource from the latest observation. Layer the activity on top: flows (CHECK_DATA_FLOW "remains enabled", DISABLE_DATA_FLOW), restores (CHECK_RESTORE_ACCESS, BLOCK_RESTORE, RESTORE_BACKUP), and recreation (SYNC/INDEX/"repopulated" after a delete).
  - Track replicas as separate resources.
  - Use `LINK_RESOURCE_IDENTITY` rows as grounded links.
  - Keep the proving ID with every fact.
- **Don't:**
  - treat `reported_result=SUCCESS` as absence without an observation;
  - link through name similarity;
  - read post-`audit_at` data;
  - share mutable state across cases.
- **Self-checks:**
  - For each sample, does the reconstructed resource set equal the set of resources in the expected steps? List the extras and misses.
  - Is every fact's evidence ID dated ≤ `audit_at`?
- **Exit gate:**
  - [x] Resource-set recall and precision on the samples reported.
  - [x] Misses are explained.
  - [x] No temporal violations (an assertion in the code).

## P5 — Policy Engine & Step Generation

- **Entry gate:**
  - [ ] P4 produces per-case resource states with evidence.
  - [ ] Conventions from P1 are documented.
- **Do:**
  - Category → rule → operation triple from the catalogue.
  - Generate FINDING → REMEDIATION → VERIFICATION, sorted by (operation table index, `system_id`, `resource_id`).
  - Renumber `step_no` from 1.
  - Apply the account-verification and retain-verify conventions.
  - Use `json.dumps(steps, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
- **Don't:**
  - hardcode resource IDs;
  - emit an evidence ID on INCOMPLETE remediation or verification steps;
  - emit DELETE for a RETAIN category;
  - emit DELETE for a tombstone.
- **Self-checks:**
  - Do the remediation steps have one-to-one verifications?
  - Is the remediation order safe (flows and restores first)?
  - Does `json.loads(dumps)` round-trip?
- **Exit gate:**
  - [ ] All 32 samples are produced end-to-end.
  - [ ] The output passes the §9.2 validator on the sample subset.

## P6 — Local Evaluation Harness

- **Entry gate:**
  - [ ] The pipeline runs end-to-end on the samples.
- **Do:**
  - Compute case status accuracy, step-level exact match (multiset), field-level accuracy per field, and sequence exact match.
  - Print per-case diffs.
  - Keep a results history (date, metrics, change made) in `plan/eval_history.md`.
  - Maintain ≥3 custom cases (documented in `.md`, data in `.csv`, under `code/evaluation/`), each with a hand-derived expected output and a justification.
- **Don't:**
  - change logic without re-running the evaluation;
  - accept a fix that has no generic justification;
  - tune toward guessed eval answers.
- **Self-checks:**
  - Does the metric drop on any previously-passing sample?
  - Is each failure categorized (intent, identity, discovery, policy, ordering, evidence choice)?
- **Exit gate:**
  - [ ] Samples ≥ 90% sequence-exact (target 100%).
  - [ ] Custom cases pass.
  - [ ] History recorded.

## P7 — LLM Integration & Usage Tracking

- **Entry gate:**
  - [ ] A deterministic baseline exists and its weaknesses are identified.
  - [ ] API key present in env (never printed).
- **Do:**
  - One `llm.py` wrapper: provider, model, temperature 0, JSON-shaped responses, disk cache (`code/cache/llm/` keyed by sha256 of model + prompt + input), retry with backoff, and a meter that records calls and tokens per model.
  - Keep the prompts in `code/prompts/*.md`.
  - Validate every response, and fall back to the deterministic default on invalid output.
- **Don't:**
  - let the LLM produce steps or evidence IDs directly;
  - send full SQL dumps or unnecessary PII;
  - run an uncached full pass;
  - commit the cache.
- **Self-checks:**
  - Does a second run make 0 new calls (cache hit)?
  - Does the meter total equal the sum of individual calls?
- **Exit gate:**
  - [ ] LLM-assisted components improve or hold the sample metrics.
  - [ ] The usage numbers are captured for the report.

## P8 — Full Run & Output Validation

- **Entry gate:**
  - [ ] P6 exit gate met (or waived and logged).
- **Do:**
  - Back up the previous `output.csv` to `code/cache/output_prev.csv`.
  - Run `uv run python code/main.py` clean.
  - Run the validator (§9.2).
  - Diff against the previous output and explain large swings.
  - Spot-check ≥20 eval cases across statuses and languages.
- **Don't:**
  - hand-edit the output;
  - submit when the validator fails;
  - skip the determinism check (run twice → identical hash).
- **Exit gate:**
  - [ ] Validator passes.
  - [ ] Two runs are byte-identical.
  - [ ] Status distribution printed and plausible.
  - [ ] Committed.

## P9 — Reports & Documentation

- **Entry gate:**
  - [ ] Final P8 run done.
  - [ ] Metrics and usage captured from that run.
- **Do:**
  - `evaluation_report.md`: metrics tables, custom cases (input, expected, actual, verdict), failure analysis, improvements timeline (from `plan/eval_history.md`).
  - `usage_report.md`: per-model and overall calls, tokens, averages, costs (state the pricing source and date).
  - `README.md`: setup (uv and pip), env var names, run commands, architecture, module map.
- **Don't:**
  - include secrets, PII samples, or numbers not produced by code;
  - leave placeholders.
- **Exit gate:**
  - [ ] Every required report bullet (AGENTS.md §6.8) is present.
  - [ ] A fresh-clone dry run of the README instructions works.

## P10 — Packaging & Submission

- **Entry gate:**
  - [ ] P8 and P9 exit gates met.
  - [ ] ≥3h before 2026-10-26T00:30Z (06:00 IST).
- **Do:**
  - Clean `__pycache__`.
  - Re-export `requirements.txt`.
  - Build the zip with the §9.3 command.
  - **List the zip contents** and verify there are no forbidden files.
  - Validate the root `output.csv` one last time.
  - Confirm `log.txt` entries all have `tool=` and `model=`.
- **Don't:**
  - zip `dataset/`, `.venv`, `code/cache/`, `.env`, or nested archives;
  - upload an `output.csv` other than the validated one.
- **Exit gate:**
  - [ ] `code.zip`, `output.csv`, and `log.txt` uploaded at the submission URL.
  - [ ] Interview talking points ready (architecture, identity/time, policy, remediation order, evaluation, tokens/cost).
