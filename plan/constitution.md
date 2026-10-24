# Constitution — Ghost Data Still Exists

The non-negotiable principles for this project. Every agent session, sub-agent, and code change must follow them. When anything conflicts, the order of authority is:

1. Official HackerRank event rules / user instructions
2. `AGENTS.md` (logging, project contract)
3. `problem_statement.md`
4. This constitution
5. `plan/guardrails.md`
6. `plan/phasewiseplan.md`

Deadline: **2026-10-26 06:00 IST (2026-10-26T00:30Z)**. Submission URL: https://wwww.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists

---

## Article 1 — Mission

Build a terminal-runnable deletion-audit agent that, for each of the 518 requests in `dataset/deletion_requests.csv`, decides `COMPLETE` / `INCOMPLETE` / `NOT_APPLICABLE` and emits a correct, ordered `steps_json`, written to root `output.csv`.

## Article 2 — Data Integrity

1. Use **only** files under `dataset/`. Never read, search for, or use organizer-only truth, golden answers, generator internals, or anything outside `dataset/` for predictions.
2. Never hardcode labels, case IDs, resource IDs, or sample answers. Logic must be general so it holds on hidden test cases.
3. `sample_output.csv` is for **learning conventions and evaluating**, not for lookup at prediction time.

## Article 3 — Truth Over Claims

1. `reported_status` and `reported_result` are claims, never proof.
2. A resource's state is what the evidence shows at `audit_at`.
3. Anything with a timestamp **after `audit_at`** (evidence `captured_at`, activity `event_time`, audit `event_time`) does not exist for that case.
4. Every finding and every `COMPLETE` verification must be backed by a real participant-visible `file_id`, `activity_id`, or `audit_id` that actually proves it.
5. **Amendment (2026-10-24, approved by the user):** *membership* (which resources belong to the subject) may be established from any participant evidence, including evidence captured after `audit_at`. *State* and *citations* use only evidence observed in `[requested_at, audit_at]` under the two-clock rule. Post-audit evidence can never create a finding or be cited. Rationale: 5 sample retained audit records (cases 09, 23, 24, 29, 30) are visible only in post-audit files, and every evidence cited in the samples lies in `[requested_at, audit_at]`.

## Article 4 — Identity

1. A subject is identified by a stable `user_id`, plus every current and historical email, phone, name, and email hash known at `audit_at`.
2. The request email may be current or historical. Both must resolve.
3. Global data has decoys and look-alikes. Link evidence only through grounded identifiers, never by approximate similarity alone.

## Article 5 — Policy Is Law

1. `deletion_rules.csv` decides the treatment of every record: DELETE, REDACT, ANONYMIZE, RETAIN.
2. Never delete what policy requires to be retained (legal hold, security audit log within retention, backup archive with blockable restore).
3. An `ACCOUNT_TOMBSTONE` keeps the stable `user_id` and loses name, email, phone, email hash, and any other direct identifier.
4. `COMPLETE` only when every copy has its required treatment, every required retained record still exists, and no active sync, import, or restore path can recreate the data.

## Article 6 — Output Contract

1. Header exactly `case_id,deletion_status,steps_json`. 518 rows. Sorted by `case_id`. One row per input case.
2. `NOT_APPLICABLE` ⇔ `steps_json = []`.
3. Steps: exactly the 7 fields `step_no, phase, system_id, resource_id, operation, state, evidence_id`. `step_no` starts at 1 and has no gaps.
4. Order: phase (FINDING → REMEDIATION → VERIFICATION), then the operation order in the problem-statement table, then `system_id`, then `resource_id`, ascending.
5. Only the allowed phase/operation/state combinations. Never invent new ones.
6. `INCOMPLETE` remediation and verification steps use `evidence_id = ""`. In `COMPLETE` cases every verification cites its proof, with one user-approved exception: the account verification is kept with `""` when nothing in the case window can prove it (guardrails §6 amendment, 2026-10-24).
7. Remediation order is safe: disable flows and block restores before changing records. Process downstream copies before their sources where there is a dependency.

## Article 7 — Determinism & Reproducibility

1. Same inputs produce byte-identical `output.csv`.
2. Sort everything explicitly. Serialize JSON with stable keys and separators.
3. LLM calls use temperature 0 and are cached on disk by input hash.
4. One command reproduces the output: `python code/main.py`.

## Article 8 — Security & Privacy

1. Secrets live only in environment variables or an uncommitted `.env`. Never in code, prompts, logs, reports, commits, or `code.zip`.
2. Never put dataset contents, PII, or large file dumps in `log.txt` or the reports.

## Article 9 — Transparency

1. Every user turn is logged to root `log.txt` per `AGENTS.md` §5, with an exact `tool=` and `model=`. Append only.
2. Evaluation numbers in reports must come from real runs. Never fabricate metrics, token counts, or costs.
3. Report failures honestly in `evaluation_report.md`.

## Article 10 — Phase Discipline

1. Work moves through the phases in `plan/phasewiseplan.md`. Each phase has a file in `plan/phases/phaseN.md`.
2. A phase starts only when its **entry gate** (Part II below and `guardrails.md` Part II) is met. It ends only when its **exit gate** is met, or the user explicitly waives the gate (the waiver is logged in `log.txt` and in the phase file).
3. Every completed task is ticked in its phase file with a date and a pointer to its artifact (script, notes, output).
4. Knowledge learned in one phase is written to `plan/data_notes.md` before the next phase relies on it. Memory of the conversation is not a source of truth.
5. Going back to an earlier phase is allowed and expected (e.g. fixing identity logic during evaluation). Record it in the phase file you returned to.

## Article 11 — Delivery First

1. Always keep a valid, submittable `output.csv` from the latest good run.
2. Correctness on core logic (identity, state at `audit_at`, policy, ordering) comes before LLM polish.
3. Submit with at least a 3-hour buffer before the deadline.
4. The developer must be able to explain every component in the AI interview. Prefer simple, explainable logic over opaque cleverness.

---

# Part II — Phase Articles

Each phase has a **purpose**, the **principles** that govern it, and what it must **never** do. Detailed checkable rules are in `guardrails.md` Part II.

## Phase 1 — Setup & Data Exploration
- **Purpose:** understand every input and explain every sample answer before writing pipeline logic.
- **Principles:**
  - Observation before assumption.
  - Every claim in `data_notes.md` is backed by a re-runnable script in `code/explore/` or by a specific file or row ID.
  - The samples are studied for *conventions*, never memorized as answers.
- **Never:**
  - write prediction logic here;
  - copy bulk PII into notes;
  - conclude a convention from a single example without marking it "tentative".

## Phase 2 — Request Intent Classification
- **Purpose:** decide whether `request_text` authorizes deletion.
- **Principles:**
  - Explicit refusal beats any deletion keyword ("not asking for deletion", "remove me from marketing lists **only**").
  - Language-independent: every language present must be handled.
  - When in doubt, look at the full text, not the first sentence.
  - The decision depends on `request_text` only. Activity rows such as `CLASSIFY_REQUEST` may corroborate it but never override the text.
- **Never:** classify from `reported_status`, the email, or any case-ID pattern.

## Phase 3 — Identity Resolution
- **Purpose:** turn one request email into the full set of identifiers of exactly one subject, as of `audit_at`.
- **Principles:**
  - Resolution is exact: normalized email, hash, phone, or `user_id`. One request maps to exactly one `user_id`.
  - Historical identifiers count only if their change happened at or before `audit_at`. A value the user held *before* `audit_at` remains an identifier even if it was later replaced.
  - The identifier set includes every email, every email hash (`sha256(email)`), every phone, the name(s), and the `user_id`.
- **Never:**
  - fuzzy-match on names;
  - merge two users;
  - use identity changes dated after `audit_at`.

## Phase 4 — Evidence Indexing & State Reconstruction
- **Purpose:** for the subject, establish the true state of every resource, flow, and backup at `audit_at`.
- **Principles:**
  - Evidence first, claims second. A `SUCCESS` delete is confirmed only by a later observation showing absence. A `FAILED` or `PARTIAL` result means the state is still unknown, not that the data is present; look for an observation.
  - The latest observation at or before `audit_at` wins.
  - Recreation counts: a sync, index, restore, or connector event after a deletion and before `audit_at` can make a deleted resource present again.
  - Every replica is its own resource state. A clean primary does not clean its replicas.
  - Each fact carries its proving ID (`file_id`, `activity_id`, `audit_id`).
- **Never:**
  - read a file or row timestamped after `audit_at` for that case;
  - attribute a resource to a user without a grounded identifier link;
  - let one case's state leak into another (state is computed per case).

## Phase 5 — Policy Engine & Step Generation
- **Purpose:** convert the reconstructed state into the exact `deletion_status` and `steps_json`.
- **Principles:**
  - Policy is applied per resource from `deletion_rules.csv`, with the category determined from evidence.
  - Status follows from the findings (no findings ⇒ COMPLETE), not the other way round.
  - Remediation is safe: stop flows and block restores first, then fix copies (downstream before source).
  - Every remediated item has a verification. Retained items are verified present, never deleted.
  - Ordering and serialization are fully deterministic.
- **Never:**
  - emit an operation/state pair outside the allowed table;
  - cite evidence on an INCOMPLETE remediation or verification step;
  - add a step not supported by evidence or required by a learned convention.

## Phase 6 — Local Evaluation Harness
- **Purpose:** measure correctness honestly and drive improvement.
- **Principles:**
  - Metrics are computed by code, reproducibly, from `sample_output.csv` and the custom cases.
  - Every fix must generalize. A fix explained only by "this makes sample X pass" is rejected.
  - Custom cases cover the behaviors the samples do not: NOT_APPLICABLE, historical-email cases, temporal cut-offs, retention, tombstones, flows, and restores.
- **Never:**
  - tune against the eval set without ground truth by guessing answers;
  - report numbers you did not just compute.

## Phase 7 — LLM Integration & Usage Tracking
- **Purpose:** use models only where deterministic logic is weak (multilingual intent fallback, image/PDF fact extraction).
- **Principles:**
  - LLM output is *input* to deterministic logic, never the final answer by itself.
  - temperature 0, a disk cache keyed by input hash, and structured (JSON) responses validated before use.
  - Every call is metered (model, input/output tokens, cost).
- **Never:**
  - send secrets;
  - send more data than needed;
  - make uncached repeated calls;
  - let a model invent evidence IDs.

## Phase 8 — Full Run & Output Validation
- **Purpose:** produce the submission `output.csv` and prove it is contract-valid.
- **Principles:**
  - The validator is the judge of format. A file that fails it is never submitted.
  - Keep the last valid output as a fallback before overwriting.
  - The full run is a clean run from `python code/main.py` with no manual edits.
- **Never:** hand-edit `output.csv`.

## Phase 9 — Reports & Documentation
- **Purpose:** make the work evaluable and explainable.
- **Principles:**
  - Every number in the reports comes from the final run's logs or evaluation output.
  - Failures are reported honestly.
  - The README lets a stranger run it from scratch.
- **Never:** pad the reports with unverifiable claims.

## Phase 10 — Packaging & Submission
- **Purpose:** ship the right files, safely, on time.
- **Principles:**
  - Inspect the zip's contents before uploading.
  - Submit ≥3h before the deadline.
  - `log.txt` is complete and valid.
- **Never:**
  - include `dataset/`, `.venv`, caches, secrets, or nested archives;
  - submit an unvalidated `output.csv`.
