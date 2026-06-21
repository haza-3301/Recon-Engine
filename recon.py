#!/usr/bin/env python3
"""
Recon-Engine CLI.

  recon.py <domain> -t 300              → recon.txt (full fingerprint)
  recon.py <domain> -t 300 --enum-only  → recon.txt (live hostnames only)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from core import VERSION
from core.external_tools import ExternalToolResolver
from core.pipeline import FINAL_ARTIFACT, PipelineConfig, ReconPipeline, resolve_output_file
from ui.logging_setup import setup_recon_logging
from ui.presenter import ReconPresenter

try:
    from rich.console import Console

    RICH_AVAILABLE = True
    CONSOLE = Console(color_system="auto")
except ImportError:
    RICH_AVAILABLE = False
    CONSOLE = None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="recon.py",
        description=(
            f"Recon-Engine v{VERSION}\n\n"
            "Default: enum → filter → dnsx → httpx (fingerprint) → recon.txt\n"
            "--enum-only: enum → filter → dnsx → httpx (-silent) → recon.txt"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("domain", help="Domain root, e.g. tangerangkota.go.id")
    p.add_argument("-t", "--timeout", type=float, default=300.0, help="Timeout enumerasi (detik)")
    p.add_argument("-o", "--output", help=f"File output (default: {FINAL_ARTIFACT})")
    p.add_argument("--enum-only", action="store_true", help="Hostname live saja (httpx -silent)")
    p.add_argument("--skip-dnsx", action="store_true", help="Lewati dnsx")
    p.add_argument("--wayback", action="store_true", help="Sertakan Wayback")
    p.add_argument("-q", "--quiet", action="store_true", help="Tanpa banner & animasi")
    p.add_argument("--debug", action="store_true", help="Log verbose")
    p.add_argument("--show-tools", action="store_true", help="Tampilkan path tools_bin/")
    return p


async def async_main() -> int:
    args = build_parser().parse_args()
    setup_recon_logging(silent=args.quiet, debug=args.debug, console=CONSOLE)

    if args.show_tools:
        from core.paths import TOOLS_BIN

        presenter = ReconPresenter(CONSOLE, enabled=RICH_AVAILABLE)
        status = ExternalToolResolver().status()
        if RICH_AVAILABLE and CONSOLE:
            CONSOLE.print(f"[bold]tools_bin[/] ({TOOLS_BIN})")
            for name, path in status.items():
                label = "pd-httpx" if name == "httpx" else name
                CONSOLE.print(f"  {label}: [{'green' if path else 'red'}]{path or 'NOT FOUND'}[/]")
        return 0 if all(status.values()) else 1

    domain = args.domain.strip().lower()
    output_file = resolve_output_file(domain, args.output)
    mode = "live hostnames" if args.enum_only else "full fingerprint"

    from core.config import ReconConfig

    presenter = ReconPresenter(CONSOLE, enabled=RICH_AVAILABLE and not args.quiet)
    if not args.quiet:
        presenter.banner(VERSION)
        presenter.mission(domain, output_file.resolve(), mode)

    recon_cfg = ReconConfig(
        timeout=args.timeout,
        wayback=args.wayback,
        silent=args.quiet,
        no_live_ui=args.quiet,
    )
    pipe_cfg = PipelineConfig(
        output_file=output_file,
        enum_timeout=args.timeout,
        enum_only=args.enum_only,
        skip_dnsx=args.skip_dnsx,
        recon_config=recon_cfg,
    )

    pipeline = ReconPipeline(
        domain=domain,
        config=pipe_cfg,
        presenter=presenter,
        console=CONSOLE,
        rich_available=RICH_AVAILABLE and not args.quiet,
    )

    try:
        await pipeline.run()
    except Exception as e:
        if RICH_AVAILABLE and CONSOLE:
            CONSOLE.print(f"\n[bold red]Gagal:[/] {e}")
        else:
            print(f"Gagal: {e}")
        if args.debug:
            logging.exception("pipeline error")
        return 1

    return 0


def main() -> None:
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        if CONSOLE:
            CONSOLE.print("\n[bold red]Dihentikan.[/bold red]")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
