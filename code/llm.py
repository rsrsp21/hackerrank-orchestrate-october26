"""LLM access: provider adapters behind one interface, a committed response cache, and usage metering.

Design (plan/phases/phase7.md §2.1):
  * the model only extracts facts or classifies text; it never decides findings, steps, or evidence ids;
  * every response is cached as JSON in code/llm_cache/responses/<key>.json, keyed by provider, model, task,
    prompt version, prompt text, and image hashes. The folder is committed and shipped, so a run without any
    API key reproduces the same output;
  * cache miss + no client (no key) → None, and callers fall back deterministically;
  * every live call is metered (calls, input/output tokens) per provider/model/task; cached entries keep the
    usage of the call that produced them.
Secrets are read from the environment or the uncommitted root .env and are never logged or stored.
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "code" / "llm_cache" / "responses"


def load_env(path=ROOT / ".env"):
    """Load KEY=VALUE lines from .env without overriding variables already set."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self):
        return self.input_tokens + self.output_tokens


class GeminiClient:
    """Google Gemini adapter (google-genai SDK). Temperature 0, JSON output."""

    provider = "google"

    def __init__(self, api_key, model, timeout_s=120, retries=3):
        from google import genai

        self.model = model
        self._client = genai.Client(api_key=api_key, http_options={"timeout": timeout_s * 1000})
        self._retries = retries

    def generate_json(self, prompt, images=()):
        from google.genai import types

        parts = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images] + [prompt]
        config = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")
        last = None
        for attempt in range(self._retries):
            try:
                resp = self._client.models.generate_content(model=self.model, contents=parts, config=config)
                meta = resp.usage_metadata
                out_tokens = (meta.candidates_token_count or 0) + (getattr(meta, "thoughts_token_count", 0) or 0)
                return json.loads(resp.text), Usage(meta.prompt_token_count or 0, out_tokens)
            except Exception as exc:  # transient network/API errors: back off and retry
                last = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Gemini call failed after {self._retries} attempts: {type(last).__name__}")


@dataclass
class MeterEntry:
    live_calls: int = 0
    cache_hits: int = 0
    failures: int = 0
    input_tokens: int = 0          # tokens of live calls made in this run
    output_tokens: int = 0
    cached_input_tokens: int = 0   # tokens originally spent to produce the cache entries reused in this run
    cached_output_tokens: int = 0


@dataclass
class Meter:
    entries: dict = field(default_factory=dict)

    def entry(self, provider, model, task):
        return self.entries.setdefault((provider, model, task), MeterEntry())

    def summary(self):
        return [{"provider": p, "model": m, "task": t, **asdict(e)} for (p, m, t), e in sorted(self.entries.items())]


def cache_key(provider, model, task, prompt_version, prompt, images=()):
    h = hashlib.sha256()
    for part in (provider, model, task, prompt_version, prompt):
        h.update(part.encode("utf-8") + b"\x00")
    for data, mime in images:
        h.update(hashlib.sha256(data).hexdigest().encode() + mime.encode() + b"\x00")
    return h.hexdigest()


class CachedLLM:
    """Wraps a client (or None) with the response cache and the usage meter."""

    def __init__(self, client=None, provider="google", model=None, cache_dir=CACHE_DIR, meter=None):
        self.client = client
        self.provider = getattr(client, "provider", provider)
        self.model = getattr(client, "model", model) or "unknown"
        self.cache_dir = Path(cache_dir)
        self.meter = meter or Meter()

    def generate_json(self, task, prompt, prompt_version, images=(), validate=None):
        """Cached JSON answer, or None when there is no cache entry and no client (or the call/validation fails)."""
        key = cache_key(self.provider, self.model, task, prompt_version, prompt, images)
        path = self.cache_dir / f"{key}.json"
        entry = self.meter.entry(self.provider, self.model, task)
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            entry.cache_hits += 1
            entry.cached_input_tokens += cached["usage"]["input_tokens"]
            entry.cached_output_tokens += cached["usage"]["output_tokens"]
            return cached["response"]
        if self.client is None:
            return None
        try:
            response, usage = self.client.generate_json(prompt, images)
        except Exception:
            entry.failures += 1
            return None
        entry.live_calls += 1
        entry.input_tokens += usage.input_tokens
        entry.output_tokens += usage.output_tokens
        if validate is not None and not validate(response):
            entry.failures += 1
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        record = {"provider": self.provider, "model": self.model, "task": task, "prompt_version": prompt_version,
                  "response": response, "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}}
        path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return response


def default_llm(cache_dir=CACHE_DIR, meter=None):
    """Gemini when GEMINI_API_KEY is set (env or .env), otherwise cache-only."""
    load_env()
    key, model = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_MODEL", "gemini-4-argon")
    client = GeminiClient(key, model) if key else None
    return CachedLLM(client, provider="google", model=model, cache_dir=cache_dir, meter=meter)
