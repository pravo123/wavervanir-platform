"""Recompute + cache the live conditions snapshot — run on a schedule.

The terminal's ``/v1/desk/conditions`` endpoint serves a cached snapshot
instantly. This tool does the slow multi-upstream build and writes it to the
cache, so customers always hit a warm cache instead of paying the ~15-20s cost.

Run it on a scheduler (e.g. a Render Cron Job, GitHub Action, or cron) every
~30-60 minutes:

    python -m wavervanir_api.tools.refresh_conditions

Needs the same env as the API (DB url + FRED_API_KEY + FINANCIALDATA_API_KEY)
so the FRED + financialdata lenses populate.
"""

from __future__ import annotations

import datetime as _dt
import sys
from typing import Sequence

from wavervanir_api import desk_conditions
from wavervanir_api.config import get_settings


def main(argv: Sequence[str] | None = None) -> int:
    settings = get_settings()
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap = desk_conditions.build_cached(
        source="live", settings=settings, force=True, generated_at_utc=stamp
    )
    s = snap["summary"]
    print(f"[refresh_conditions] cached live snapshot: {s['live']}/{s['total']} live "
          f"({s['unavailable']} unavailable) @ {stamp}")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    sys.exit(main())
