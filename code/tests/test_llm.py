"""Tests for code/llm.py with a fake client (no network)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from llm import CachedLLM, Usage, cache_key, load_env  # noqa: E402


class FakeClient:
    provider, model = "fake", "fake-1"

    def __init__(self, response=None, fail=False):
        self.calls, self.response, self.fail = 0, response or {"ok": True}, fail

    def generate_json(self, prompt, images=()):
        self.calls += 1
        if self.fail:
            raise RuntimeError("boom")
        return self.response, Usage(100, 20)


def test_miss_then_hit_and_metering(tmp_path):
    client = FakeClient()
    llm = CachedLLM(client, cache_dir=tmp_path)
    img = [(b"\x89PNG...", "image/png")]
    assert llm.generate_json("t", "prompt", "v1", img) == {"ok": True}
    assert llm.generate_json("t", "prompt", "v1", img) == {"ok": True}
    assert client.calls == 1
    e = llm.meter.entries[("fake", "fake-1", "t")]
    assert (e.live_calls, e.cache_hits, e.input_tokens, e.output_tokens) == (1, 1, 100, 20)
    assert (e.cached_input_tokens, e.cached_output_tokens) == (100, 20)


def test_keyless_run_uses_cache_and_falls_back(tmp_path):
    CachedLLM(FakeClient(), cache_dir=tmp_path).generate_json("t", "p", "v1")
    keyless = CachedLLM(None, provider="fake", model="fake-1", cache_dir=tmp_path)
    assert keyless.generate_json("t", "p", "v1") == {"ok": True}       # cached answer reused
    assert keyless.generate_json("t", "other", "v1") is None           # no entry, no client → fallback


def test_key_changes_with_inputs():
    base = cache_key("g", "m", "t", "v1", "p", [(b"a", "image/png")])
    assert base != cache_key("g", "m", "t", "v2", "p", [(b"a", "image/png")])
    assert base != cache_key("g", "m", "t", "v1", "p", [(b"b", "image/png")])
    assert base != cache_key("g", "m2", "t", "v1", "p", [(b"a", "image/png")])


def test_failures_and_invalid_answers_are_not_cached(tmp_path):
    llm = CachedLLM(FakeClient(fail=True), cache_dir=tmp_path)
    assert llm.generate_json("t", "p", "v1") is None
    bad = CachedLLM(FakeClient(response={"x": 1}), cache_dir=tmp_path)
    assert bad.generate_json("t", "p", "v1", validate=lambda r: "records" in r) is None
    assert not list(tmp_path.glob("*.json"))
    assert llm.meter.entries[("fake", "fake-1", "t")].failures == 1


def test_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nX_TEST_A=from_file\nX_TEST_B='quoted'\n", encoding="utf-8")
    monkeypatch.setenv("X_TEST_A", "already")
    monkeypatch.delenv("X_TEST_B", raising=False)
    load_env(env)
    import os
    assert os.environ["X_TEST_A"] == "already" and os.environ["X_TEST_B"] == "quoted"


def test_intent_fallback_only_for_unsure(tmp_path):
    from intent import DELETION, classify_with_fallback

    class Classifier(FakeClient):
        def generate_json(self, prompt, images=()):
            self.calls += 1
            return {"label": DELETION, "reason": "asks to wipe data"}, Usage(50, 10)

    client = Classifier()
    llm = CachedLLM(client, cache_dir=tmp_path)
    assert classify_with_fallback("Please permanently delete my account.", llm).rule == "deletion_cue"
    assert client.calls == 0                                   # rules decided: no call
    unsure = "Hmm, about that thing we discussed last week."
    assert classify_with_fallback(unsure, None).label not in (DELETION,)      # keyless default: not a deletion
    r = classify_with_fallback(unsure, llm)
    assert (r.label, r.rule, client.calls) == (DELETION, "llm_fallback", 1)
    bad = CachedLLM(type("Bad", (FakeClient,), {"generate_json": lambda self, p, i=(): ({"label": "MAYBE"}, Usage())})(),
                    cache_dir=tmp_path / "b")
    assert classify_with_fallback(unsure, bad).label != DELETION  # invalid answer → deterministic default
