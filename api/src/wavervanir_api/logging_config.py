"""Structured stdout logging for the API.

Render (and most PaaS) captures stdout, so we emit single-line key=value records
that are greppable in the log stream and cheap to parse — without pulling in a
logging framework. Call :func:`configure_logging` once at app construction, then
use :func:`get_logger` everywhere. Attach structured fields via the standard
``extra={"kv": {...}}`` convention; the formatter renders them inline.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

_ROOT = "wavervanir"
_CONFIGURED = False


def _fmt_val(v: Any) -> str:
    s = str(v)
    return f'"{s}"' if (s == "" or " " in s or "=" in s) else s


class KeyValueFormatter(logging.Formatter):
    """``ts=… level=… logger=… msg='…' k=v k=v`` one-liners (+ traceback on error)."""

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            f"ts={self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z')}",
            f"level={record.levelname}",
            f"logger={record.name}",
            f"msg={_fmt_val(record.getMessage())}",
        ]
        kv = getattr(record, "kv", None)
        if isinstance(kv, dict):
            parts += [f"{k}={_fmt_val(v)}" for k, v in kv.items()]
        line = " ".join(parts)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(settings: Any | None = None) -> None:
    """Install the stdout handler on the ``wavervanir`` logger tree. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = str(getattr(settings, "log_level", "INFO") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(KeyValueFormatter())
    root = logging.getLogger(_ROOT)
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    _CONFIGURED = True


def get_logger(name: str = "") -> logging.Logger:
    """Logger under the ``wavervanir`` namespace (e.g. ``wavervanir.http``)."""
    return logging.getLogger(f"{_ROOT}.{name}" if name else _ROOT)
