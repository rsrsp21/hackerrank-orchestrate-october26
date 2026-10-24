"""Phase 7 pre-flight: confirm the configured Gemini model exists for this API key (key value is never printed).

Run: uv run python code/explore/check_gemini.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env(path=ROOT / ".env"):
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    load_env()
    key, model = os.environ.get("GEMINI_API_KEY"), os.environ.get("GEMINI_MODEL", "")
    if not key:
        sys.exit("GEMINI_API_KEY is not set")
    from google import genai

    client = genai.Client(api_key=key)
    names = sorted(m.name.removeprefix("models/") for m in client.models.list())
    gemini = [n for n in names if "gemini" in n]
    print(f"{len(names)} models visible to this key; Gemini models ({len(gemini)}):")
    for n in gemini:
        print("  ", n)
    print(f"\nconfigured GEMINI_MODEL={model!r}: {'FOUND' if model in names else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
