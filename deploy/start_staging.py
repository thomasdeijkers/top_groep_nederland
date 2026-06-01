from __future__ import annotations

import sys
import traceback
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "runtime" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    sys.stdout = (LOG_DIR / "staging.out.log").open("a", encoding="utf-8", buffering=1)
    sys.stderr = (LOG_DIR / "staging.err.log").open("a", encoding="utf-8", buffering=1)
    uvicorn.run("apps.api.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        with (LOG_DIR / "staging.err.log").open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        raise
