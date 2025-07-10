#!/usr/bin/env python3
"""
Recon Engine v8.0.0 - Final Edition
Author: haza-3301
"""

# 1. Pustaka Standar
import argparse
import asyncio
import csv
import hashlib
import ipaddress
import json
import logging
import logging.handlers
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# 2. Pustaka Pihak Ketiga & Modul Lokal
import httpx

try:
    from filelock import FileLock, Timeout
    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False

try:
    import dns.asyncresolver
    from dns.exception import DNSException
    DNSPYTHON_AVAILABLE = True
except ImportError:
    DNSPYTHON_AVAILABLE = False
    class DNSException(Exception): pass

try:
    from rich.console import Console, Group
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from jinja2 import Environment
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

# Modul lokal diimpor setelahnya
from ui.live_progress import LiveProgressManager
from core.error_handler import (APIError, PluginError, handle_http_error,
                              handle_plugin_exception, handle_timeout)
from core.plugin_loader import load_plugins, lint_plugins
from core.output_writer import write_output
from core.ip_resolver import (resolve_domains_to_ips, lookup_ips_asn,
                              DNSPYTHON_AVAILABLE as IP_RESOLVER_AVAILABLE)
from core.utils import is_valid_domain, normalize_subdomain


# ===============================
# ⚙️ Konfigurasi & Utilitas
# ===============================

VERSION = "8.0.0"
BASE_DIR = Path(__file__).parent.resolve()
CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None

def safe_console_print(content: Any, **kwargs):
    """Wrapper untuk print yang aman jika Rich tidak tersedia."""
    if CONSOLE: CONSOLE.print(content, **kwargs)
    else: print(re.sub(r"\[.*?\]", "", str(content)))

def print_banner():
    """Menampilkan banner program."""
    plain_ascii_art = r"""
    ____                __         ____                  
   / __ \___  ___ ___  / /_ ___   / __/__  ___ ________  
  / /_/ / _ \/ -_) _ \/ / // -_) / _// _ \/ -_) __/ _ \ 
  \____/ .__/\__/_//_/_/\_,/\__/ /_/  \___/\__/_/ /_//_/ 
      /_/                                               
"""
    art_text = Text(plain_ascii_art.strip(), style="bold cyan", justify="center")
    version_text = Text(f"v{VERSION} - Final Edition", style="bold magenta", justify="center")

    render_group = Group(art_text, version_text)
    safe_console_print(Panel(render_group, border_style="green", expand=False))


def setup_logging(is_silent: bool, is_debug: bool, log_file: Optional[str]):
    """Mengatur konfigurasi logging ke konsol dan file (opsional)."""
    level = logging.WARNING if is_silent else logging.DEBUG if is_debug else logging.INFO
    handlers: List[logging.Handler] = []
    log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)-7s] %(message)s")

    if RICH_AVAILABLE and not is_silent:
        handlers.append(RichHandler(console=CONSOLE, show_path=False, rich_tracebacks=True, markup=True))
    elif not is_silent:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_formatter)
        handlers.append(stream_handler)

    if log_file:
        try:
            handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
            handler.setFormatter(log_formatter)
            handlers.append(handler)
        except IOError as e:
            logging.error(f"[SYSTEM] Tidak dapat menulis ke file log {log_file}: {e}")
    
    logging.basicConfig(level=level, format="%(message)s", datefmt="[%X]", handlers=handlers)
    if is_debug: logging.getLogger("httpx").setLevel(logging.INFO)
    else: logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("filelock").setLevel(logging.WARNING)
    logging.getLogger("dns").setLevel(logging.WARNING)
    logging.getLogger("jinja2").setLevel(logging.WARNING)

# ===============================
# 🔌 Pemuat & Eksekutor Plugin
# ===============================

async def run_tool_task(plugin: Any, domain: str, timeout: float, progress_callback: Callable) -> Set[str]:
    """Menjalankan tool eksternal secara non-blocking dan melaporkan progres."""
    await progress_callback(status='RUNNING')
    command = plugin.get_command(domain)
    if not isinstance(command, list) or not command:
        raise PluginError(f"Command dari '{plugin.name}' harus list dan tidak boleh kosong.")

    try:
        proc = await asyncio.create_subprocess_exec(
            command[0], *command[1:],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        
        stdout = stdout_bytes.decode('utf-8', errors='ignore')
        stderr = stderr_bytes.decode('utf-8', errors='ignore')

        if proc.returncode != 0:
            raise PluginError(stderr.strip() or f"Proses gagal dengan kode {proc.returncode} tanpa output error.")
        
        result = {line.strip() for line in stdout.splitlines() if is_valid_domain(line.strip())}
        await progress_callback(count_increment=len(result), status='COMPLETED')
        return result
        
    except asyncio.TimeoutError:
        await progress_callback(status='TIMEOUT')
        handle_timeout(plugin.name, timeout)
        if 'proc' in locals() and proc.returncode is None:
            try:
                proc.kill()
                await proc.wait()
            except ProcessLookupError:
                pass
    except FileNotFoundError:
        await progress_callback(status='FAILED')
        logging.error(f"[TOOL] Perintah '{command[0]}' tidak ditemukan. Pastikan tool terinstal dan ada di PATH.")
    except Exception as e:
        await progress_callback(status='FAILED')
        handle_plugin_exception(plugin.name, e)
        
    return set()

async def query_api_task(client: httpx.AsyncClient, plugin: Any, domain: str, retries: int, timeout: float, progress_callback: Callable) -> Set[str]:
    """Melakukan query ke API dengan parsing non-blocking."""
    await progress_callback(status='RUNNING')
    url = plugin.url.format(domain=domain)
    headers = {"User-Agent": f"Recon Engine/{VERSION}"}

    if hasattr(plugin, "api_key_env"):
        api_key = os.getenv(plugin.api_key_env)
        if api_key: headers["Authorization"] = f"Bearer {api_key}"
    elif hasattr(plugin, "api_key"):
        headers["Authorization"] = plugin.api_key
    
    last_exception = None
    for attempt in range(retries):
        try:
            resp = await client.get(url, headers=headers, timeout=httpx.Timeout(timeout, connect=5.0))
            resp.raise_for_status()
            data = resp.json() if getattr(plugin, "is_json", True) else resp.text
            
            loop = asyncio.get_running_loop()
            raw_result = await loop.run_in_executor(None, plugin.parse, data)
            
            if not isinstance(raw_result, set):
                raise PluginError(f"Plugin '{plugin.name}' tidak mengembalikan tipe data Set.")
            
            result = {sub for sub in raw_result if is_valid_domain(sub)}
            await progress_callback(count_increment=len(result), status='COMPLETED')
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, PluginError) as e:
            last_exception = e
            handle_http_error(plugin.name, url, attempt, retries, e)
            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                await progress_callback(status='FAILED')
    return set()

async def run_wayback_task(client: httpx.AsyncClient, domain: str, timeout: float, progress_callback: Callable) -> Set[str]:
    """Mengambil URL dari Wayback Machine dan mengekstrak subdomain."""
    await progress_callback(status='RUNNING')
    url = f"http://web.archive.org/cdx/search/cdx?url=*.{domain}/*&output=json&fl=original&collapse=urlkey"
    headers = {"User-Agent": f"Recon Engine/{VERSION}"}
    subdomains = set()

    try:
        resp = await client.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        url_pattern = re.compile(r"https?://(?:www\.)?([a-zA-Z0-9.-]+\." + re.escape(domain) + ")")
        
        for item in data[1:]:
            if not item:
                continue
            
            match = url_pattern.match(item[0])
            if match:
                subdomain = match.group(1)
                if is_valid_domain(subdomain):
                    subdomains.add(normalize_subdomain(subdomain))
        
        await progress_callback(count_increment=len(subdomains), status='COMPLETED')
        return subdomains
    except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
        logging.error(f"[WAYBACK] Gagal mengambil data dari Wayback Machine: {e}")
        await progress_callback(status='FAILED')
    except Exception as e:
        logging.error(f"[WAYBACK] Terjadi error tak terduga saat parsing data Wayback: {e}")
        await progress_callback(status='FAILED')
    
    return set()

# ===============================
# 🚦 Orkestrasi & Pemrosesan Hasil
# ===============================

async def run_recon_for_domain(domain: str, args: argparse.Namespace, tool_plugins: Dict, api_plugins: Dict) -> Dict:
    """Orkestrasi utama untuk satu domain, mengembalikan hasil akhir."""
    progress_manager = LiveProgressManager(CONSOLE, enabled=RICH_AVAILABLE and not args.silent and not args.no_live_ui)
    
    safe_console_print(f"\n[bold blue]🚀 Memulai Recon untuk:[/bold blue] [bold yellow]{domain}[/bold yellow]")
    
    all_plugin_names = list(tool_plugins.keys()) + list(api_plugins.keys())
    if args.wayback:
        all_plugin_names.append("Wayback (Built-in)")

    await progress_manager.add_plugins(all_plugin_names)
    
    progress_manager.start()

    all_subdomains: Set[str] = set()
    source_contributions: Dict[str, int] = {}

    try:
        async with httpx.AsyncClient(verify=not args.insecure) as client:
            tasks = []
            
            def create_callback(name: str) -> Callable:
                async def callback(count_increment: int = 0, status: Optional[str] = None):
                    try:
                        await progress_manager.update_status(name, count_increment, status)
                    except Exception as e:
                        logging.debug(f"[CALLBACK] Error saat update status untuk plugin '{name}': {e}")
                return callback

            for name, plugin in tool_plugins.items():
                tasks.append(run_tool_task(plugin, domain, args.timeout, create_callback(name)))
            
            for name, plugin in api_plugins.items():
                tasks.append(query_api_task(client, plugin, domain, args.api_retries, args.timeout, create_callback(name)))
            
            if args.wayback:
                tasks.append(run_wayback_task(client, domain, args.timeout, create_callback("Wayback (Built-in)")))
            
            plugin_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_plugin_items = list(tool_plugins.items()) + list(api_plugins.items())
            if args.wayback:
                all_plugin_items.append(("Wayback (Built-in)", None))

            for i, result in enumerate(plugin_results):
                name = all_plugin_items[i][0]
                if isinstance(result, set):
                    initial_size = len(all_subdomains)
                    all_subdomains.update(result)
                    source_contributions[name] = len(all_subdomains) - initial_size
                else:
                    source_contributions[name] = 0
                    if not isinstance(result, Exception):
                           logging.error(f"[SYSTEM] Hasil tidak valid dari '{name}': {result}")

    finally:
        progress_manager.stop()

    final_subdomains_set = {s for s in all_subdomains if is_valid_domain(s)}

    if args.max_subdomains and len(final_subdomains_set) > args.max_subdomains:
        logging.warning(f"[SYSTEM] Jumlah subdomain ({len(final_subdomains_set)}) melebihi batas --max-subdomains ({args.max_subdomains}). Hasil akan dipotong.")
        final_subdomains_set = set(sorted(list(final_subdomains_set))[:args.max_subdomains])

    results_dict: Dict[str, Dict] = {sub: {} for sub in sorted(list(final_subdomains_set))}

    if args.resolve_ip or args.asn_lookup:
        if not IP_RESOLVER_AVAILABLE:
            logging.warning("[SYSTEM] Opsi --resolve-ip atau --asn-lookup memerlukan 'dnspython'. Langkah ini dilewati.")
        else:
            safe_console_print(f"\n[info]🔍 Me-resolve [green]{len(results_dict)}[/green] subdomain ke alamat IP...[/info]")
            ip_map = await resolve_domains_to_ips(set(results_dict.keys()))
            all_unique_ips = set()
            
            for sub, ips in ip_map.items():
                if sub in results_dict:
                    results_dict[sub]['ips'] = [{"address": ip} for ip in ips]
                    all_unique_ips.update(ips)
            
            if args.asn_lookup and all_unique_ips:
                asn_map = await lookup_ips_asn(all_unique_ips)
                for sub_details in results_dict.values():
                    if 'ips' in sub_details:
                        for ip_info in sub_details['ips']:
                            ip_addr = ip_info['address']
                            if ip_addr in asn_map:
                                ip_info['asn_info'] = asn_map[ip_addr]
    
    return {"subdomains": results_dict, "contributions": source_contributions}

# ===============================
# 🚀 Main Execution
# ===============================

def display_available_plugins():
    """Memuat dan menampilkan semua plugin yang tersedia."""
    safe_console_print("[bold green]🔌 Plugin yang Tersedia:[/bold green]")
    tool_plugins = load_plugins("tools", None, None)
    api_plugins = load_plugins("api", None, None)

    if not tool_plugins and not api_plugins:
        safe_console_print("[yellow]Tidak ada plugin yang ditemukan.[/yellow] Pastikan direktori 'plugins/api' dan 'plugins/tools' ada.")
    
    table = Table(title="Daftar Plugin")
    table.add_column("Tipe", style="cyan"); table.add_column("Nama Plugin", style="magenta")
    for name in sorted(tool_plugins.keys()):
        if 'wayback' not in name.lower():
            table.add_row("Tool", name)
    for name in sorted(api_plugins.keys()):
        if 'wayback' not in name.lower():
            table.add_row("API", name)
    
    table.add_row("Built-in", "Wayback (`--wayback`)")
    safe_console_print(table)

async def main():
    """Fungsi utama untuk parsing argumen dan menjalankan program."""
    parser = argparse.ArgumentParser(description=f"Recon Engine v{VERSION}", formatter_class=argparse.RawTextHelpFormatter)
    
    group_target = parser.add_mutually_exclusive_group(required=True)
    group_target.add_argument("-d", "--domain", help="Domain target tunggal.")
    group_target.add_argument("-i", "--input", help="File berisi daftar domain.")
    group_target.add_argument("--list-plugins", action="store_true", help="Tampilkan semua plugin yang tersedia dan keluar.")
    group_target.add_argument("--lint-plugins", action="store_true", help="Validasi semua plugin dan keluar.")

    group_plugin = parser.add_mutually_exclusive_group()
    group_plugin.add_argument("--use-plugins", help="Hanya gunakan plugin spesifik (pisah koma).")
    group_plugin.add_argument("--exclude-plugins", help="Kecualikan plugin spesifik (pisah koma).")
    
    group_output = parser.add_argument_group("Output & Formatting")
    group_output.add_argument("-o", "--output", help="File output. Format: .txt, .csv, .json, .burp, .gnmap, .html. Gunakan '%%d' untuk nama domain.")
    group_output.add_argument("--overwrite", action="store_true", help="Timpa file output jika sudah ada.")
    group_output.add_argument("--html-template", type=Path, help="Path ke file template Jinja2 kustom untuk laporan HTML.")

    group_tuning = parser.add_argument_group("Tuning & Performance")
    group_tuning.add_argument("-t", "--timeout", type=float, default=15.0, help="Timeout per task (detik). Default: 15")
    group_tuning.add_argument("--global-timeout", type=float, default=None, help="Timeout global untuk pemindaian satu domain (detik).")
    group_tuning.add_argument("--max-subdomains", type=int, default=25000, help="Batas maksimal subdomain per domain. Default: 25000")
    group_tuning.add_argument("--api-retries", type=int, default=3, help="Jumlah percobaan ulang API.")
    
    group_features = parser.add_argument_group("Additional Features")
    group_features.add_argument("--wayback", action="store_true", help="Aktifkan pencarian dari Wayback Machine (bisa lambat).")
    group_features.add_argument("--resolve-ip", action="store_true", help="Resolve setiap subdomain yang ditemukan ke alamat IP.")
    group_features.add_argument("--asn-lookup", action="store_true", help="Cari info ASN untuk setiap IP (memerlukan --resolve-ip).")
    group_features.add_argument("--insecure", action="store_true", help="Bypass verifikasi SSL/TLS.")

    group_cache = parser.add_argument_group("Caching")
    group_cache.add_argument("--cache-dir", type=Path, help="Direktori untuk menyimpan cache hasil.")
    group_cache.add_argument("--no-cache", action="store_true", help="Jangan gunakan cache untuk pemindaian ini.")

    group_verbosity = parser.add_argument_group("Verbosity & Logging")
    group_verbosity.add_argument("--no-live-ui", action="store_true", help="Nonaktifkan tampilan Live Progress Table.")
    group_verbosity.add_argument("-s", "--silent", action="store_true", help="Mode senyap (hanya output error).")
    group_verbosity.add_argument("--debug", action="store_true", help="Aktifkan logging DEBUG.")
    group_verbosity.add_argument("--log-file", help="Simpan log ke file (dengan rotasi otomatis).")
    
    args = parser.parse_args()

    if args.asn_lookup and not args.resolve_ip:
        parser.error("argumen --asn-lookup hanya bisa digunakan bersama dengan --resolve-ip.")

    if args.html_template and (not args.output or not args.output.endswith('.html')):
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
    exclude_plugins = [p.strip().lower() for p in args.exclude_plugins.split(",")] if args.exclude_plugins else None

    all_domains = []
    if args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                for line in f:
                    domain = line.strip()
                    if is_valid_domain(domain):
                        all_domains.append(domain)
                    elif domain:
                        logging.warning(f"[SYSTEM] Format domain tidak valid, dilewati: '{domain}'")
        except FileNotFoundError:
            logging.error(f"[SYSTEM] File input [red]{args.input}[/] tidak ditemukan.")
            sys.exit(1)
    else:
        if is_valid_domain(args.domain):
            all_domains.append(args.domain)
        else:
            logging.error(f"[SYSTEM] Format domain tidak valid: '{args.domain}'")
            sys.exit(1)
    
    if not all_domains:
        logging.error("[SYSTEM] Tidak ada domain valid untuk dipindai.")
        sys.exit(1)

    tool_plugins = load_plugins("tools", use_only=use_plugins, exclude=exclude_plugins)
    api_plugins = load_plugins("api", use_only=use_plugins, exclude=exclude_plugins)

    wayback_keys_to_remove = [k for k in api_plugins if 'wayback' in k.lower()]
    for key in wayback_keys_to_remove:
        del api_plugins[key]
        logging.debug(f"Plugin dinamis '{key}' dihapus untuk memberi jalan pada fitur --wayback built-in.")

    if not tool_plugins and not api_plugins and not args.wayback:
        logging.error("[SYSTEM] Tidak ada plugin yang berhasil dimuat dan --wayback tidak aktif. Tidak ada sumber data.")
        sys.exit(1)

    for i, domain in enumerate(all_domains):
        domain_to_scan = domain.encode("idna").decode("ascii")
        cache_file, lock_file = None, None
        
        if args.cache_dir and not args.no_cache:
            if not FILELOCK_AVAILABLE:
                logging.warning("[CACHE] Cache dinonaktifkan karena 'filelock' tidak ada.")
            else:
                args.cache_dir.mkdir(parents=True, exist_ok=True)
                sorted_keys = sorted(list(api_plugins.keys()) + list(tool_plugins.keys()))
                wayback_status = "wayback-on" if args.wayback else "wayback-off"
                resolve_status = "resolve-on" if args.resolve_ip else "resolve-off"
                asn_status = "asn-on" if args.asn_lookup else "asn-off"
                plugin_hash = hashlib.md5(f"{VERSION}{sorted_keys}{wayback_status}{resolve_status}{asn_status}".encode()).hexdigest()[:8]
                cache_file = args.cache_dir / f"{domain_to_scan}-{plugin_hash}.json"
                lock_file = args.cache_dir / f"{domain_to_scan}-{plugin_hash}.lock"
                
                try:
                    with FileLock(lock_file, timeout=1):
                        if cache_file.exists():
                            try:
                                cache_content = json.loads(cache_file.read_text('utf-8'))
                                data_str = json.dumps(cache_content['data'], sort_keys=True)
                                if hashlib.sha256(data_str.encode()).hexdigest() == cache_content['checksum']:
                                    safe_console_print(f"\n[green]Memuat hasil untuk [yellow]{domain}[/yellow] dari cache...[/green]")
                                    found_count = len(cache_content['data'].get("subdomains", {}))
                                    safe_console_print(f"[info]Total ditemukan [green]{found_count}[/green] subdomain unik.[/info]")
                                    if args.output:
                                        args.total_domains = len(all_domains)
                                        args.domain_index = i + 1
                                        write_output(domain, cache_content['data'], args)
                                    continue
                                else: logging.warning(f"[CACHE] Cache untuk {domain} rusak. Scan ulang.")
                            except (json.JSONDecodeError, KeyError): logging.warning(f"[CACHE] Cache untuk {domain} tidak bisa dibaca. Scan ulang.")
                except Timeout: logging.warning(f"[CACHE] Gagal mendapatkan lock untuk cache {domain}, melanjutkan tanpa cache.")
        
        try:
            recon_task = run_recon_for_domain(domain_to_scan, args, tool_plugins, api_plugins)
            
            if args.global_timeout:
                results = await asyncio.wait_for(recon_task, timeout=args.global_timeout)
            else:
                results = await recon_task
            
            found_count = len(results.get("subdomains", {}))
            safe_console_print(f"\n[info]Total ditemukan [green]{found_count}[/green] subdomain unik untuk [yellow]{domain}[/yellow].[/info]")

            if cache_file and FILELOCK_AVAILABLE:
                try:
                    with FileLock(lock_file, timeout=1):
                        data_str = json.dumps(results, sort_keys=True)
                        checksum = hashlib.sha256(data_str.encode()).hexdigest()
                        payload = {'data': results, 'checksum': checksum}
                        
                        tmp_cache = cache_file.with_suffix(".tmp")
                        tmp_cache.write_text(json.dumps(payload), encoding='utf-8')
                        tmp_cache.rename(cache_file)
                except Timeout: logging.warning(f"[CACHE] Gagal mendapatkan lock untuk menulis cache {domain}.")

            if args.output:
                args.total_domains = len(all_domains)
                args.domain_index = i + 1
                write_output(domain, results, args)

        except asyncio.TimeoutError:
            logging.error(f"[SYSTEM] Recon untuk [red]{domain}[/] dihentikan karena timeout global ({args.global_timeout}s).")
        except Exception as e:
            logging.error(f"[SYSTEM] Error tak terduga saat memproses [red]{domain}[/red]: {e}", exc_info=True)

    safe_console_print("\n[bold green]✅ Semua task selesai.[/bold green]")

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Memberi peringatan jika pustaka opsional tidak ada
    if RICH_AVAILABLE is False:
        print("WARNING: Pustaka 'rich' tidak ditemukan. Tampilan UI akan terbatas.", file=sys.stderr)
    
    if JINJA2_AVAILABLE is False:
        print("WARNING: Pustaka 'Jinja2' tidak ditemukan. Laporan .html tidak dapat dibuat.", file=sys.stderr)
    
    if DNSPYTHON_AVAILABLE is False:
        print("WARNING: Pustaka 'dnspython' tidak ditemukan. Fitur --resolve-ip dan --asn-lookup tidak akan berfungsi.", file=sys.stderr)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        safe_console_print("\n[bold red]Program dihentikan oleh pengguna.[/bold red]")
    except httpx.ConnectError as e:
        logging.critical(f"Koneksi gagal: {e}. Pastikan Anda terhubung ke internet.")
        sys.exit(1)
    except Exception as e:
        logging.critical(f"Terjadi error fatal yang tidak tertangani: {e}", exc_info=True)
        sys.exit(1)