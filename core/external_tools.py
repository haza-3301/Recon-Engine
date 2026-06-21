"""Resolve bundled PD binaries in ``tools_bin/`` — isolated from Python httpx library."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import List, Optional

from core.paths import TOOLS_BIN

# pd-httpx: avoids clash with Python ``httpx`` package in venv
BUNDLED = {
    "httpx": TOOLS_BIN / "pd-httpx",
    "dnsx": TOOLS_BIN / "dnsx",
}


class ExternalToolError(RuntimeError):
    pass


class ExternalToolResolver:
    """
    Invoke ProjectDiscovery CLIs by absolute path under ``<repo>/tools_bin/``.

    Resolution order:
    1. ``RECON_HTTPX_BIN`` / ``RECON_DNSX_BIN`` env (user override)
    2. ``tools_bin/pd-httpx`` / ``tools_bin/dnsx`` (bundled in repo)
    """

    PD_MARKER = "projectdiscovery"

    def __init__(self, httpx_bin: Optional[str] = None, dnsx_bin: Optional[str] = None):
        self._httpx_override = httpx_bin or os.getenv("RECON_HTTPX_BIN")
        self._dnsx_override = dnsx_bin or os.getenv("RECON_DNSX_BIN")
        self._cache: dict[str, Path] = {}

    @staticmethod
    def is_pd_binary(path: Path) -> bool:
        try:
            proc = subprocess.run(
                [str(path), "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return ExternalToolResolver.PD_MARKER in (proc.stdout + proc.stderr).lower()

    def _candidates(self, tool: str) -> List[Path]:
        found: List[Path] = []
        seen: set[str] = set()

        def add(path: Optional[Path]) -> None:
            if not path:
                return
            resolved = path.resolve()
            key = str(resolved)
            if key not in seen and resolved.is_file():
                seen.add(key)
                found.append(resolved)

        override = self._httpx_override if tool == "httpx" else self._dnsx_override
        if override:
            add(Path(override))
        add(BUNDLED.get(tool))
        return found

    def resolve(self, tool: str) -> Path:
        if tool in self._cache:
            return self._cache[tool]

        for candidate in self._candidates(tool):
            if self.is_pd_binary(candidate):
                self._cache[tool] = candidate
                logging.debug(f"[TOOLS] {tool} → {candidate}")
                return candidate

        raise ExternalToolError(
            f"Binary '{tool}' tidak ditemukan.\n"
            f"  • Jalankan: python install.py install\n"
            f"  • Lokasi: {TOOLS_BIN}/\n"
            f"  • Override: export RECON_{'HTTPX' if tool == 'httpx' else 'DNSX'}_BIN=/path/to/binary\n"
            f"  • httpx bundled = pd-httpx (bukan library Python httpx)"
        )

    def httpx(self) -> Path:
        return self.resolve("httpx")

    def dnsx(self) -> Path:
        return self.resolve("dnsx")

    def status(self) -> dict[str, Optional[str]]:
        out: dict[str, Optional[str]] = {}
        for name in ("httpx", "dnsx"):
            try:
                out[name] = str(self.resolve(name))
            except ExternalToolError:
                out[name] = None
        return out
