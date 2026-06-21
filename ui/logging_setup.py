"""Logging setup tuned for clean recon.py output."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import List, Optional

try:
    from rich.console import Console
    from rich.logging import RichHandler

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class ReconNoiseFilter(logging.Filter):
    """Hide expected plugin noise in normal mode — failures show in live table."""

    HIDDEN_MARKERS = ("[LOADER]", "[API]", "[PLUGIN]")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if any(m in msg for m in self.HIDDEN_MARKERS):
            return False
        return True


def setup_recon_logging(
    *,
    silent: bool,
    debug: bool,
    console: Optional["Console"] = None,
) -> None:
    level = logging.WARNING if silent else logging.DEBUG if debug else logging.INFO
    handlers: List[logging.Handler] = []

    if silent:
        logging.basicConfig(level=logging.CRITICAL, handlers=[])
        return

    if RICH_AVAILABLE and console:
        handler = RichHandler(
            console=console,
            show_path=False,
            rich_tracebacks=True,
            markup=True,
            show_time=debug,
        )
        if not debug:
            handler.addFilter(ReconNoiseFilter())
        handlers.append(handler)
    else:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        if not debug:
            stream.addFilter(ReconNoiseFilter())
        handlers.append(stream)

    logging.basicConfig(level=level, handlers=handlers, force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("filelock").setLevel(logging.WARNING)
    logging.getLogger("dns").setLevel(logging.WARNING)
