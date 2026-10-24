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
- [ ] 7.1 `code/llm.py` (env loader, Usage, GeminiClient, CachedLLM, meter) + unit tests with a fake client (cache hit/miss, keyless fallback, invalid JSON handling, metering totals). No network in tests.
- [ ] 7.2 `code/prompts/image_facts.md` + `code/image_extract.py`; dry run on **one** image (evidence_04) and inspect the facts against the Phase 1 transcription before running all 11.
- [ ] 7.3 Run all 11 images; validate every facts file; compare against the Phase 1 transcriptions (test fixtures `code/tests/fixtures/image_facts_expected.json`, used **only** by tests, never by the pipeline): resource ids, states, identifiers.
- [ ] 7.4 Re-run the pipeline: samples must be unchanged (no sample cites an image) — status 32/32, F1 ≥ 0.990; report the eval deltas for the 12 image scenario cases (34, 35, 39, 45, 46, 50, 52, 53, 55, 61, 63, 33) and confirm the Q9 identity-conflict rule fires for marketing_001.
- [ ] 7.5 Intent fallback wired in (`intent.py` / `main.py`), tested with a fake client.
- [ ] 7.6 Keyless reproducibility check: temporarily hide `.env` (or set an env flag), run `main.py` → byte-identical `output.csv`; second run with key → 0 new calls (all cache hits).
- [ ] 7.7 Usage data for the final run captured; pricing source for `gemini-4-argon` provided/confirmed by the user (prices are not guessed).
- [ ] 7.8 Plans/notes updated; committed (cache included, `.env` never).

## 4. Exit gate
- [ ] 11/11 image facts files present and valid; fixture agreement reported (target: all resource ids and states correct).
- [ ] Samples unchanged (status 32/32, sequence 29/32); validator green; deterministic.
- [ ] Keyless run byte-identical; second keyed run makes 0 new calls.
- [ ] Usage numbers captured; tests green; committed.

## 5. Guardrail reminders
- The LLM extracts **facts**; it never decides findings, steps, or evidence ids.
- Never send the API key anywhere but Google's endpoint; never log or commit it; never print it.
- Send only what is needed (one image + the prompt); no dataset dumps.
- Temperature 0, cached, metered — a repeated run must not spend tokens.
