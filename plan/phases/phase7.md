# Phase 7 — LLM Integration (Gemini) & Usage Tracking

**Time box:** ~3–4h
**Goal:** use Gemini only where deterministic logic is weak — (1) reading the 11 screenshots into structured image facts, (2) a fallback for request texts the intent rules mark UNSURE — while keeping the pipeline reproducible **without** a key and metering every call for `usage_report.md`.
**Governing docs:** constitution Part II Phase 7; guardrails P7 + §8; phasewiseplan Phase 7 (reproducibility design); phase4.md §2 (image-facts schema, `code/evidence/images.py`).

---

## 1. Entry gate
- [x] Deterministic baseline exists and its weakness is known: 11 images contribute nothing → 12 eval scenario cases affected; 9 COMPLETE cases lack account evidence (phase4.md 4.9).
- [x] API key present in `.env` (filled; gitignored; value never printed).
- [x] Model verified: `gemini-4-argon` FOUND in the key's model list (`code/explore/check_gemini.py`, 2026-10-24). SDK `google-genai` 2.33.0 installed.

## 2. Design

### 2.1 `code/llm.py` — provider-agnostic, cached, metered
```python
class LLMClient(Protocol):                     # one adapter per provider
    provider: str; model: str
    def generate_json(self, prompt: str, schema: dict, images: list[bytes] = ()) -> tuple[dict, Usage]

class GeminiClient(LLMClient)                  # google-genai; temperature 0; response_mime_type=application/json + response_schema
class CachedLLM:                               # wraps any client
    def generate_json(self, task, prompt, schema, images=(), prompt_version) -> dict
        key = sha256(provider | model | task | prompt_version | prompt | sha256(each image))
        hit  → code/llm_cache/responses/<key>.json (response + original usage)
        miss → call the client (if available), validate JSON, store, record usage
        no client and no entry → return None (callers fall back deterministically)
    meter: per (provider, model, task): live calls, cache hits, input/output tokens
```
- `.env` loader (no extra dependency): `GEMINI_API_KEY`, `GEMINI_MODEL`; optional price settings `LLM_PRICE_INPUT_PER_MTOK`, `LLM_PRICE_OUTPUT_PER_MTOK` (USD per 1M tokens) for the cost estimate.
- Retries with exponential backoff on transient errors (max 3), timeouts; errors never crash the pipeline (fallback instead).
- The cache folder `code/llm_cache/` is **committed and shipped** in code.zip → a keyless clean run reproduces output.csv byte-for-byte.

### 2.2 Screenshot facts (`code/image_extract.py` + `code/prompts/image_facts.md`)
- One call per image (11 total): the prompt asks for **facts only** (no verdicts) in the documented facts schema (phase4.md / `evidence/images.py`): records `{resource_id, category, state, emails, phones, user_ids, references, observed_at?}`, plus an explicit instruction to include *every* resource row shown (decoys included — linking decides ownership, not the model).
- Output validated by `images._record_observation` rules (bad ids/categories dropped); written to `code/llm_cache/image_facts/<file_id>.json` with the model id and prompt version.
- Category/state vocabulary is given in the prompt with definitions taken from data_notes §2.2/§3 (e.g. connector Continuous+Healthy → DATA_FLOW/FLOW_ACTIVE; archive with no restore block → BACKUP_ARCHIVE/RESTORE_ALLOWED; "Retained reference" with no PII → ACCOUNT_TOMBSTONE/REDACTED).
- `main.py` runs extraction for images whose facts file is missing (only when a key is available), before building the index.

### 2.3 Intent fallback
- `intent.classify` UNSURE → one cached LLM call (prompt `code/prompts/intent_fallback.md`, JSON `{label, reason}`), else the deterministic default (NOT_APPLICABLE unless a deletion cue exists). Today 0 eval texts are UNSURE → 0 calls; this covers hidden-test robustness.

### 2.4 Usage accounting (`code/llm_cache/usage.json` + report data)
Per model and overall: live calls, cache hits, input tokens, output tokens, total, average per request (÷ 518), estimated cost (USD) from the configured prices with the pricing source and date stated in `usage_report.md`.

## 3. Tasks
- [x] 7.1 `code/llm.py` (2026-10-24): `.env` loader, `GeminiClient` (temperature 0, JSON output, retries), `CachedLLM` (committed response cache keyed by provider/model/task/prompt version/prompt/image hashes; keyless fallback; invalid answers never cached), `Meter`. `code/tests/test_llm.py` (fake client, no network).
- [x] 7.2 `code/prompts/image_facts.md` + `code/image_extract.py`; dry run on evidence_04 matched the Phase 1 transcription exactly (2,029 in / 136 out tokens). Image facts gained `labels`, resolved through catalog links (`delivery_confirmation_19.pdf` → object_19, `user_17` → tombstone_17), the same mechanism as PDFs.
- [x] 7.3 All 11 images extracted. **Prompt bug found and fixed (v1 → v2):** v1 defined IDENTIFIABLE as "name, email, phone, *or user id* shown", so the evidence_42 tombstone (only the permitted stable user_id) came back IDENTIFIABLE; v2 counts user ids as identifying only for analytics (tombstones and support messages keep the stable reference; rule_15 / sample case_26). All 11 re-extracted with v2 for consistency; superseded v1 answers removed from the cache (their tokens still counted as spend). `code/tests/test_image_facts.py`: **11/11 images agree with the manual transcriptions** (resource ids, categories, states, key identifiers); the manual transcriptions are test fixtures only.
- [x] 7.4 Pipeline rerun: **samples unchanged** (status 1.0000, step F1 0.9896, sequence 0.9062), custom cases 12/12, validator green. Eval changes confined to the 10 image scenarios (34, 35, 39, 45, 46, 50, 52, 53, 55, 61): status COMPLETE 162 → 154, INCOMPLETE 346 → 354. COMPLETE cases without citable account evidence 11 → 3 (45, 126, 127). Q9 rule fires: marketing_001 dropped for case_63 ("catalog link contradicted by the record's own identifiers"). Checked and rejected a "retained audit record needs a supplied retention period" rule: 12 of 24 sample-expected audit records have no retention-bearing evidence. So case_45 verifies all 6 audit records of user_03 (known uncertainty: the samples only ever show one per subject).
- [x] 7.5 `intent.classify_with_fallback` + `code/prompts/intent_fallback.md`: only UNSURE texts are sent (0 in eval today); invalid or absent answers keep the deterministic default; wired through `investigate_all(..., llm=)`. Test with a fake client.
- [x] 7.6 Reproducibility: keyed run, keyless run (`GEMINI_API_KEY=`), and `--no-llm` produce **byte-identical** output.csv (sha256 0d80a7d4bad67187…). Keyed re-run made **0 live calls** (facts and answers come from the committed cache).
- [x] 7.7 Usage captured (`code/llm_cache/usage_last_run.json`): the final output relies on 11 cached `gemini-4-argon` image-facts answers = **22,576 input + 3,943 output tokens**; total spent during development including the superseded v1 extraction = 44,899 input + 9,502 output tokens. **Prices (user-provided, 2026-10-24): $2 / 1M input, $10 / 1M output tokens** → final output **$0.084582** total, **$0.000163 per request** (51.2 tokens/request over 518 requests); all 22 development calls $0.184818. Prices live in `.env` / `.env.example` (`LLM_PRICE_*_PER_MTOK`); `usage_last_run.json` now includes `cost_usd`.
- [x] 7.8 Plans/notes updated; committed (`code/llm_cache/` included, `.env` never).

## 4. Exit gate
- [x] 11/11 image facts files present and valid; fixture agreement 11/11.
- [x] Samples unchanged (status 32/32, sequence 29/32); validator green; deterministic.
- [x] Keyless run byte-identical; keyed re-run makes 0 new calls.
- [x] Usage numbers and cost captured; tests green (152); committed.

## 5. Guardrail reminders
- The LLM extracts **facts**; it never decides findings, steps, or evidence ids.
- Never send the API key anywhere but Google's endpoint; never log or commit it; never print it.
- Send only what is needed (one image + the prompt); no dataset dumps.
- Temperature 0, cached, metered — a repeated run must not spend tokens.
