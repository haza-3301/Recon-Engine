"""Scan configuration — decoupled from argparse."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ReconConfig:
    """Runtime options for a recon scan."""

    timeout: float = 15.0
    global_timeout: Optional[float] = None
    api_retries: int = 3
    max_subdomains: int = 25000
    wayback: bool = False
    resolve_ip: bool = False
    asn_lookup: bool = False
    insecure: bool = False
    silent: bool = False
    no_live_ui: bool = False
    cache_dir: Optional[Path] = None
    no_cache: bool = False

    @classmethod
    def from_namespace(cls, args) -> "ReconConfig":
        return cls(
            timeout=args.timeout,
            global_timeout=args.global_timeout,
            api_retries=args.api_retries,
            max_subdomains=args.max_subdomains,
            wayback=args.wayback,
            resolve_ip=args.resolve_ip,
            asn_lookup=args.asn_lookup,
            insecure=args.insecure,
            silent=args.silent,
            no_live_ui=args.no_live_ui,
            cache_dir=args.cache_dir,
            no_cache=args.no_cache,
        )
