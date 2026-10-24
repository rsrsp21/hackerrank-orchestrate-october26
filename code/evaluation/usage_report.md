# Usage Report — Token Usage and Cost

Covers the final full-dataset run that produced the submitted `output.csv` (518 requests, sha256 `0d80a7d4bad67187…`), plus the development spend for transparency. Source of the numbers: `code/llm_cache/usage_last_run.json` (written by `code/main.py`) and the per-call usage stored in every cached answer under `code/llm_cache/responses/`.

## 1. Models and where they are used

| Provider | Model | Task | Used for | Calls needed for the output |
|---|---|---|---|---|
| Google | `gemini-4-argon` | `image_facts` | reading the 11 screenshot evidence files into structured facts (prompt `code/prompts/image_facts.md`, v2) | 11 |
| Google | `gemini-4-argon` | `intent_fallback` | classifying request texts the multilingual rules mark UNSURE (prompt `code/prompts/intent_fallback.md`) | 0 — no eval text is UNSURE |

Everything else — identity resolution, parsing 83 non-image evidence files (SQL, JSON, TXT, 7 log formats, PDFs via pdfplumber), linking, state reconstruction, policy, step generation — is deterministic Python with **no model calls**. The model only extracts facts; it never decides findings, steps, or evidence ids.

**Pricing** (provided by the team on 2026-10-24 for `gemini-4-argon`): **$2.00 per 1M input tokens, $10.00 per 1M output tokens**. Configured as `LLM_PRICE_INPUT_PER_MTOK` / `LLM_PRICE_OUTPUT_PER_MTOK`.

## 2. Final full-dataset run (the run that produced `output.csv`)

The final run reads every model answer from the committed cache, so it makes **0 live calls**. The tokens below are those of the 11 cached calls whose answers the output depends on — i.e. the true model cost of producing this output.

| Model | Task | Model calls | Input tokens | Output tokens | Total tokens | Cost (USD) |
|---|---|---|---|---|---|---|
| gemini-4-argon | image_facts | 11 | 22,576 | 3,943 | 26,519 | $0.084582 |
| gemini-4-argon | intent_fallback | 0 | 0 | 0 | 0 | $0.000000 |
| **Total (single model, single provider)** | | **11** | **22,576** | **3,943** | **26,519** | **$0.084582** |

| Per-request figures (518 requests) | Value |
|---|---|
| Average model calls per request | 0.021 (11 / 518) |
| Average input tokens per request | 43.6 |
| Average output tokens per request | 7.6 |
| **Average total tokens per request** | **51.2** |
| **Estimated cost per request** | **$0.000163** |
| Average per model call | 2,052 input + 358 output tokens; $0.007689 |
| Cost split | input $0.045152 · output $0.039430 |

Live calls during the final run itself: **0** (all 11 answers served from `code/llm_cache/`). Wall-clock time of the run: ≈5 s.

## 3. Development spend (all calls ever made)

| Stage | Calls | Input tokens | Output tokens | Total | Cost (USD) |
|---|---|---|---|---|---|
| Prompt v1 extraction (1 dry run + 10), superseded after a definition bug was found | 11 | 22,323 | 5,559 | 27,882 | $0.100236 |
| Prompt v2 extraction (the answers used by the output) | 11 | 22,576 | 3,943 | 26,519 | $0.084582 |
| **Overall development total** | **22** | **44,899** | **9,502** | **54,401** | **$0.184818** |

(One extra `models.list` call was made to verify the model id exists; it consumes no tokens.)

## 4. Why the cost is this low — and stays reproducible
- **Use the model only where rules cannot see:** 83 of 94 evidence files are machine-readable; only the 11 screenshots need vision. Request intent is decided by rules for all 518 texts.
- **One call per image, not per request:** a screenshot is read once and its facts are linked to whichever cases they concern.
- **Committed cache keyed by** provider, model, task, prompt version, prompt text, and image hashes: re-runs cost nothing; changing a prompt invalidates only its own entries.
- **Keyless reproducibility:** without `GEMINI_API_KEY` (or with `--no-llm`) the pipeline produces a byte-identical `output.csv` from the cache.
- **Metered by design:** `CachedLLM` records live calls, cache hits, failures, and input/output tokens per (provider, model, task); `code/main.py` writes the summary with cost to `code/llm_cache/usage_last_run.json` on every run.
