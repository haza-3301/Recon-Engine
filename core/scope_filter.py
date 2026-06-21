"""In-scope subdomain filtering (replaces grep/awk shell pipeline)."""

from __future__ import annotations

import re
from typing import Iterable, List, Set


def scope_regex(root_domain: str) -> re.Pattern[str]:
    """
    Match only hosts under ``root_domain`` with valid label grammar.

    Equivalent shell pattern (for ``padang.go.id``)::
        ^([a-zA-Z]([a-zA-Z0-9-]*[a-zA-Z0-9])?\\.)+padang\\.go\\.id$
    """
    root = root_domain.strip().lower().lstrip("*.")
    escaped = re.escape(root)
    label = r"[a-zA-Z]([a-zA-Z0-9-]*[a-zA-Z0-9])?"
    return re.compile(rf"^({label}\.)+{escaped}$")


_LONG_DIGIT_RUN = re.compile(r"[0-9]{5,}")


def filter_in_scope(
    hosts: Iterable[str],
    root_domain: str,
    *,
    max_length: int = 60,
    drop_long_digit_runs: bool = True,
) -> List[str]:
    """
    Keep unique in-scope hosts sorted alphabetically.

    Rules (mirror manual pipeline):
    - must match scope regex for ``root_domain``
    - reject lines with 5+ consecutive digits
    - reject length >= ``max_length``
    """
    pattern = scope_regex(root_domain)
    kept: Set[str] = set()

    for raw in hosts:
        host = raw.strip().lower().lstrip("*.")
        if not host or len(host) >= max_length:
            continue
        if drop_long_digit_runs and _LONG_DIGIT_RUN.search(host):
            continue
        if pattern.match(host):
            kept.add(host)

    return sorted(kept)


def filter_file(
    input_path: str,
    output_path: str,
    root_domain: str,
    **kwargs,
) -> int:
    from pathlib import Path

    lines = Path(input_path).read_text(encoding="utf-8").splitlines()
    filtered = filter_in_scope(lines, root_domain, **kwargs)
    Path(output_path).write_text("\n".join(filtered) + ("\n" if filtered else ""), encoding="utf-8")
    return len(filtered)
