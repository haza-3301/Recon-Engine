"""Repository-root paths — portable, no hardcoded user/machine paths."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_BIN = REPO_ROOT / "tools_bin"
