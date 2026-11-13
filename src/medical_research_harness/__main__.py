"""Allow execution via `python -m medical_research_harness`."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
