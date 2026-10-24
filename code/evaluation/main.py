"""Evaluation entry point (starter layout): uv run python code/evaluation/main.py [--markdown results.md]

The harness logic lives in harness.py so it does not shadow code/main.py when both are imported.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import main  # noqa: E402

if __name__ == "__main__":
    main()
