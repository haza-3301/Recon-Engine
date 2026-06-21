#!/usr/bin/env python3
"""
Recon Engine — CLI entry point.
Author: haza-3301
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import logging.handlers
import re
import sys
from pathlib import Path
from typing import Any, List, Optional

import httpx

from core import VERSION
from core.cache import CacheManager
from core.config import ReconConfig
from core.orchestrator import ReconOrchestrator
from core.output_writer import write_output
from core.plugin_loader import lint_plugins, load_plugins
from core.utils import is_valid_domain

try:
    from rich.console import Console, Group
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from jinja2 import Environment  # noqa: F401

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

try:
    import dns.asyncresolver  # noqa: F401

    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False

BASE_DIR = Path(__file__).parent.resolve()
CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None


def safe_console_print(content: Any, **kwargs) -> None:
    if CONSOLE:
        CONSOLE.print(content, **kwargs)
    else:
        print(re.sub(r"\[.*?\]", "", str(content)))


def print_banner() -> None:
    plain_ascii_art = r"""
    ____                __         ____
   / __ \___  ___ ___  / /_ ___   / __/__  ___ ________
  / /_/ / _ \/ -_) _ \/ / // -_) / _// _ \/ -_) __/ _ \
  \____/ .__/\__/_//_/_/\_,/\__/ /_/  \___/\__/_/ /_//_/
      /_/
"""
    art_text = Text(plain_ascii_art.strip(), style="bold cyan", justify="center")
    version_text = Text(f"v{VERSION}", style="bold magenta", justify="center")
    safe_console_print(Panel(Group(art_text, version_text), border_style="green", expand=False))


def setup_logging(is_silent: bool, is_debug: bool, log_file: Optional[str]) -> None:
    level = logging.WARNING if is_silent else logging.DEBUG if is_debug else logging.INFO
    handlers: List[logging.Handler] = []
    log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-7s] %(message)s")

    if RICH_AVAILABLE and not is_silent:
        handlers.append(
            RichHandler(console=CONSOLE, show_path=False, rich_tracebacks=True, markup=True)
        )
    elif not is_silent:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        handlers.append(stream_handler)

    if log_file:
        try:
            handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(log_formatter)
            handlers.append(handler)
        except OSError as e:
            logging.error(f"[SYSTEM] Tidak dapat menulis ke file log {log_file}: {e}")

    logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]", handlers=handlers)
    logging.getLogger("httpx").setLevel(logging.INFO if is_debug else logging.WARNING)
    logging.getLogger("filelock").setLevel(logging.WARNING)
    logging.getLogger("dns").setLevel(logging.WARNING)
    logging.getLogger("jinja2").setLevel(logging.WARNING)


def display_available_plugins() -> None:
    safe_console_print("[bold green]🔌 Plugin yang Tersedia:[/bold green]")
    tool_plugins = load_plugins("tools", None, None)
    api_plugins = load_plugins("api", None, None)

    if not tool_plugins and not api_plugins:
        safe_console_print(
            "[yellow]Tidak ada plugin yang ditemukan.[/yellow] "
            "Pastikan direktori 'plugins/api' dan 'plugins/tools' ada."
        )

    table = Table(title="Daftar Plugin")
    table.add_column("Tipe", style="cyan")
    table.add_column("Nama Plugin", style="magenta")
    for name in sorted(tool_plugins.keys()):
        table.add_row("Tool", name)
    for name in sorted(api_plugins.keys()):
        table.add_row("API", name)
    table.add_row("Built-in", f"Wayback (`--wayback`)")
    safe_console_print(table)


def _strip_wayback_api_plugins(api_plugins: dict) -> None:
    """Wayback is a built-in flag, not an API plugin file."""
    for key in [k for k in api_plugins if "wayback" in k.lower()]:
        del api_plugins[key]
        logging.debug(f"Plugin API '{key}' diabaikan — gunakan flag --wayback.")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Recon Engine v{VERSION}",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    group_target = parser.add_mutually_exclusive_group(required=True)
    group_target.add_argument("-d", "--domain", help="Domain target tunggal.")
    group_target.add_argument("-i", "--input", help="File berisi daftar domain.")
    group_target.add_argument(
        "--list-plugins", action="store_true", help="Tampilkan semua plugin dan keluar."
    )
    group_target.add_argument(
        "--lint-plugins", action="store_true", help="Validasi semua plugin dan keluar."
    )

    group_plugin = parser.add_mutually_exclusive_group()
    group_plugin.add_argument("--use-plugins", help="Hanya gunakan plugin spesifik (pisah koma).")
    group_plugin.add_argument("--exclude-plugins", help="Kecualikan plugin spesifik (pisah koma).")

    group_output = parser.add_argument_group("Output & Formatting")
    group_output.add_argument(
        "-o",
        "--output",
        help="File output: .txt, .csv, .json, .burp, .gnmap, .html. Gunakan '%%d' untuk nama domain.",
    )
    group_output.add_argument("--overwrite", action="store_true", help="Timpa file output jika sudah ada.")
    group_output.add_argument(
        "--html-template", type=Path, help="Template Jinja2 kustom untuk laporan HTML."
    )

    group_tuning = parser.add_argument_group("Tuning & Performance")
    group_tuning.add_argument("-t", "--timeout", type=float, default=15.0, help="Timeout per task (detik).")
    group_tuning.add_argument(
        "--global-timeout", type=float, default=None, help="Timeout global per domain (detik)."
    )
    group_tuning.add_argument(
        "--max-subdomains", type=int, default=25000, help="Batas maksimal subdomain per domain."
    )
    group_tuning.add_argument("--api-retries", type=int, default=3, help="Jumlah percobaan ulang API.")

    group_features = parser.add_argument_group("Additional Features")
    group_features.add_argument("--wayback", action="store_true", help="Aktifkan Wayback Machine.")
    group_features.add_argument("--resolve-ip", action="store_true", help="Resolve subdomain ke IP.")
    group_features.add_argument(
        "--asn-lookup", action="store_true", help="Lookup ASN (memerlukan --resolve-ip)."
    )
    group_features.add_argument("--insecure", action="store_true", help="Bypass verifikasi SSL/TLS.")

    group_cache = parser.add_argument_group("Caching")
    group_cache.add_argument("--cache-dir", type=Path, help="Direktori cache hasil scan.")
    group_cache.add_argument("--no-cache", action="store_true", help="Nonaktifkan cache.")

    group_verbosity = parser.add_argument_group("Verbosity & Logging")
    group_verbosity.add_argument("--no-live-ui", action="store_true", help="Nonaktifkan live progress table.")
    group_verbosity.add_argument("-s", "--silent", action="store_true", help="Mode senyap.")
    group_verbosity.add_argument("--debug", action="store_true", help="Logging DEBUG.")
    group_verbosity.add_argument("--log-file", help="Simpan log ke file.")

    args = parser.parse_args()

    if args.asn_lookup and not args.resolve_ip:
        parser.error("argumen --asn-lookup hanya bisa digunakan bersama dengan --resolve-ip.")
    if args.html_template and (not args.output or not args.output.endswith(".html")):
        parser.error("argumen --html-template hanya bisa digunakan dengan output .html (-o report.html).")

    setup_logging(args.silent, args.debug, args.log_file)

    if args.list_plugins:
        display_available_plugins()
        sys.exit(0)
    if args.lint_plugins:
        lint_plugins()
        sys.exit(0)

    if not args.silent:
        print_banner()

    use_plugins = [p.strip().lower() for p in args.use_plugins.split(",")] if args.use_plugins else None
    exclude_plugins = (
        [p.strip().lower() for p in args.exclude_plugins.split(",")] if args.exclude_plugins else None
    )

    all_domains: List[str] = []
    if args.input:
        try:
            with open(args.input, encoding="utf-8") as f:
                for line in f:
                    domain = line.strip()
                    if is_valid_domain(domain):
                        all_domains.append(domain)
                    elif domain:
                        logging.warning(f"[SYSTEM] Format domain tidak valid, dilewati: '{domain}'")
        except FileNotFoundError:
            logging.error(f"[SYSTEM] File input tidak ditemukan: {args.input}")
            sys.exit(1)
    elif is_valid_domain(args.domain):
        all_domains.append(args.domain)
    else:
        logging.error(f"[SYSTEM] Format domain tidak valid: '{args.domain}'")
        sys.exit(1)

    if not all_domains:
        logging.error("[SYSTEM] Tidak ada domain valid untuk dipindai.")
        sys.exit(1)

    tool_plugins = load_plugins("tools", use_only=use_plugins, exclude=exclude_plugins)
    api_plugins = load_plugins("api", use_only=use_plugins, exclude=exclude_plugins)
    _strip_wayback_api_plugins(api_plugins)

    if not tool_plugins and not api_plugins and not args.wayback:
        logging.error("[SYSTEM] Tidak ada plugin yang dimuat dan --wayback tidak aktif.")
        sys.exit(1)

    config = ReconConfig.from_namespace(args)
    orchestrator = ReconOrchestrator(
        version=VERSION,
        config=config,
        console=CONSOLE,
        rich_available=RICH_AVAILABLE,
        print_fn=safe_console_print,
    )
    cache = CacheManager(VERSION, args.cache_dir, enabled=not args.no_cache)

    for i, domain in enumerate(all_domains):
        domain_to_scan = domain.encode("idna").decode("ascii")
        cache_file, _ = cache.paths_for(
            domain_to_scan,
            tool_plugins,
            api_plugins,
            args.wayback,
            args.resolve_ip,
            args.asn_lookup,
        )

        if cache_file:
            cached = cache.read(cache_file)
            if cached is not None:
                safe_console_print(
                    f"\n[green]Memuat hasil untuk [yellow]{domain}[/yellow] dari cache...[/green]"
                )
                found_count = len(cached.get("subdomains", {}))
                safe_console_print(f"[info]Total ditemukan [green]{found_count}[/green] subdomain unik.[/info]")
                if args.output:
                    args.total_domains = len(all_domains)
                    args.domain_index = i + 1
                    write_output(domain, cached, args)
                continue

        try:
            recon_task = orchestrator.run_for_domain(domain_to_scan, tool_plugins, api_plugins)
            if args.global_timeout:
                results = await asyncio.wait_for(recon_task, timeout=args.global_timeout)
            else:
                results = await recon_task

            found_count = len(results.get("subdomains", {}))
            safe_console_print(
                f"\n[info]Total ditemukan [green]{found_count}[/green] subdomain unik "
                f"untuk [yellow]{domain}[/yellow].[/info]"
            )

            if cache_file:
                cache.write(cache_file, results)

            if args.output:
                args.total_domains = len(all_domains)
                args.domain_index = i + 1
                write_output(domain, results, args)

        except asyncio.TimeoutError:
            logging.error(
                f"[SYSTEM] Recon untuk {domain} dihentikan — timeout global ({args.global_timeout}s)."
            )
        except Exception as e:
            logging.error(f"[SYSTEM] Error saat memproses {domain}: {e}", exc_info=True)

    safe_console_print("\n[bold green]✅ Semua task selesai.[/bold green]")


def run() -> None:
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if not RICH_AVAILABLE:
        print("WARNING: Pustaka 'rich' tidak ditemukan. Tampilan UI akan terbatas.", file=sys.stderr)
    if not JINJA2_AVAILABLE:
        print("WARNING: Pustaka 'Jinja2' tidak ditemukan. Laporan .html tidak tersedia.", file=sys.stderr)
    if not DNSPYTHON_AVAILABLE:
        print(
            "WARNING: Pustaka 'dnspython' tidak ditemukan. --resolve-ip / --asn-lookup tidak berfungsi.",
            file=sys.stderr,
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        safe_console_print("\n[bold red]Program dihentikan oleh pengguna.[/bold red]")
    except httpx.ConnectError as e:
        logging.critical(f"Koneksi gagal: {e}. Pastikan Anda terhubung ke internet.")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
