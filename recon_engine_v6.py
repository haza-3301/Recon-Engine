#!/usr/bin/env python3
"""
Recon Engine v6.9 - Non-Blocking Plugin Parsing
"""

# 1. Pustaka Standar
import argparse
import asyncio
import csv
import hashlib
import importlib
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
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Modul lokal diimpor setelahnya
from ui.live_progress import LiveProgressManager

# ===============================
# ⚙️ Konfigurasi & Utilitas
# ===============================

VERSION = "6.9"
BASE_DIR = Path(__file__).parent.resolve()
CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None

class PluginError(Exception): pass
class APIError(PluginError): pass

def safe_console_print(content: Any, **kwargs):
    """Wrapper untuk print yang aman jika Rich tidak tersedia."""
    if CONSOLE: CONSOLE.print(content, **kwargs)
    else: print(re.sub(r"\[.*?\]", "", str(content)))

def print_banner():
    """Menampilkan banner program."""
    safe_console_print(Panel.fit(
        Text(f"Recon Engine v{VERSION}", style="bold magenta", justify="center"),
        title="[bold white]Non-Blocking Parsing Edition[/bold white]",
        border_style="green"
    ))

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

def is_valid_domain(domain: str) -> bool:
    """Memvalidasi format domain, menolak IP, dan memvalidasi TLD."""
    if not domain or len(domain) > 253:
        return False

    try:
        ipaddress.ip_address(domain)
        return False
    except ValueError:
        pass

    try:
        encoded_domain = domain.encode("idna").decode("ascii")
        
        label_re = r"(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
        general_domain_re = rf"^({label_re}\.)+{label_re}$"
        if not re.match(general_domain_re, encoded_domain):
            return False
            
        tld = encoded_domain.split('.')[-1]
        if len(tld) < 2:
            return False
            
        if not tld.lower().startswith('xn--') and any(char.isdigit() for char in tld):
            return False
            
        return True
    except UnicodeError:
        return False

def normalize_subdomain(subdomain: str) -> str:
    """Membersihkan dan menormalkan nama subdomain."""
    return subdomain.lower().strip().lstrip("*.")

# ===============================
# 🔌 Pemuat & Eksekutor Plugin
# ===============================

def load_plugins(plugin_type: str, use_only: Optional[List[str]], exclude: Optional[List[str]]) -> Dict[str, Any]:
    """Memuat dan memvalidasi plugin dari direktori."""
    loaded_plugins: Dict[str, Any] = {}
    plugin_dir = BASE_DIR / "plugins" / plugin_type
    if not plugin_dir.is_dir():
        logging.warning(f"[LOADER] Direktori plugin 'plugins/{plugin_type}' tidak ditemukan.")
        return {}

    for py_file in plugin_dir.glob("*.py"):
        if py_file.name.startswith("__"): continue
        module_name = f"plugins.{plugin_type}.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            plugin_instance = module.Plugin()
            
            if not hasattr(plugin_instance, "name"):
                logging.warning(f"[LOADER] Plugin {module_name} dilewati: tidak ada atribut '.name'.")
                continue
            if plugin_type == "tools" and not callable(getattr(plugin_instance, "get_command", None)):
                logging.warning(f"[LOADER] Plugin Tool '{plugin_instance.name}' dilewati: metode 'get_command' tidak ada atau tidak bisa dipanggil.")
                continue
            if plugin_type == "api" and not (hasattr(plugin_instance, "url") and callable(getattr(plugin_instance, "parse", None))):
                logging.warning(f"[LOADER] Plugin API '{plugin_instance.name}' dilewati: atribut 'url' atau metode 'parse' tidak valid.")
                continue
            
            name_lower = plugin_instance.name.lower()
            if use_only and name_lower not in use_only: continue
            if exclude and name_lower in exclude: continue
            
            if plugin_type == "tools" and not shutil.which(plugin_instance.name.split()[0]):
                logging.warning(f"[LOADER] Tool '{plugin_instance.name}' tidak terinstal, plugin dilewati.")
                continue
            
            loaded_plugins[plugin_instance.name] = plugin_instance
        except Exception as e:
            logging.error(f"[LOADER] Plugin '{module_name}' gagal dimuat: {e}", exc_info=True)
    return loaded_plugins

async def run_tool_task(plugin: Any, domain: str, timeout: float, progress_callback: Callable) -> Set[str]:
    """Menjalankan tool eksternal dan melaporkan progres."""
    await progress_callback(status='RUNNING')
    command = plugin.get_command(domain)
    if not isinstance(command, list):
        raise PluginError(f"Command dari '{plugin.name}' harus list.")
    
    loop = asyncio.get_running_loop()
    try:
        proc = await loop.run_in_executor(None, lambda: subprocess.run(command, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='ignore'))
        if proc.returncode != 0:
            raise PluginError(proc.stderr.strip() or "Proses gagal tanpa output error.")
        
        result = {line.strip() for line in proc.stdout.splitlines() if is_valid_domain(line.strip())}
        await progress_callback(count_increment=len(result), status='COMPLETED')
        return result
    except subprocess.TimeoutExpired:
        await progress_callback(status='TIMEOUT')
        logging.warning(f"[TOOL] Task '{plugin.name}' timeout.")
    except Exception as e:
        await progress_callback(status='FAILED')
        logging.error(f"[TOOL] Task '{plugin.name}' gagal: {e}")
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
            
            # Jalankan parsing yang berpotensi berat di thread terpisah
            loop = asyncio.get_running_loop()
            raw_result = await loop.run_in_executor(None, plugin.parse, data)
            
            if not isinstance(raw_result, set):
                raise PluginError(f"Plugin '{plugin.name}' tidak mengembalikan tipe data Set.")
            
            result = {sub for sub in raw_result if is_valid_domain(sub)}
            await progress_callback(count_increment=len(result), status='COMPLETED')
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, PluginError) as e:
            last_exception = e
            if attempt < retries - 1:
                logging.debug(f"[API] Percobaan {attempt + 1}/{retries} untuk '{plugin.name}' gagal, mencoba lagi...")
                await asyncio.sleep(2 ** attempt)
            else:
                await progress_callback(status='FAILED')
                logging.error(f"[API] Task '{plugin.name}' gagal setelah {retries} percobaan: {last_exception}")
    return set()

# ===============================
# 🚦 Orkestrasi & Pemrosesan Hasil
# ===============================

def process_final_results(domain: str, results: Dict, total_domains: int, domain_index: int, args: argparse.Namespace):
    """Menampilkan ringkasan akhir dan menulis hasil ke file."""
    sorted_domains = results["subdomains"]
    safe_console_print(f"\n[info]Total ditemukan [green]{len(sorted_domains)}[/green] subdomain unik untuk [yellow]{domain}[/yellow].[/info]")
    
    if args.output:
        output_path_str = args.output
        if '%' not in output_path_str and total_domains > 1:
            p = Path(output_path_str)
            output_path_str = str(p.with_name(f"{p.stem}-{domain_index}{p.suffix}"))
        
        output_path = Path(output_path_str.replace('%d', domain))

        if output_path.exists() and not args.overwrite:
            logging.warning(f"[SYSTEM] File output [yellow]{output_path}[/] sudah ada. Gunakan --overwrite untuk menimpa.")
            return
        
        ext = output_path.suffix.lower().strip()
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if ext == '.json':
                output_path.write_text(json.dumps(sorted_domains, indent=4), encoding="utf-8")
            elif ext == '.csv':
                with output_path.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f); writer.writerow(["subdomain"]); writer.writerows([d] for d in sorted_domains)
            else:
                output_path.write_text("\n".join(sorted_domains) + "\n", encoding="utf-8")
            logging.info(f"[SYSTEM] Hasil disimpan ke [cyan]{output_path}[/]")
        except IOError as e:
            logging.error(f"[SYSTEM] Gagal menulis file output {output_path}: {e}")

async def run_recon_for_domain(domain: str, args: argparse.Namespace, tool_plugins: Dict, api_plugins: Dict) -> Dict:
    """Orkestrasi utama untuk satu domain, mengembalikan hasil akhir."""
    progress_manager = LiveProgressManager(CONSOLE, enabled=RICH_AVAILABLE and not args.silent and not args.no_live_ui)
    
    safe_console_print(f"\n[bold blue]🚀 Memulai Recon untuk:[/bold blue] [bold yellow]{domain}[/bold yellow]")
    
    all_plugin_names = list(tool_plugins.keys()) + list(api_plugins.keys())
    await progress_manager.add_plugins(all_plugin_names)
    
    progress_manager.start()

    all_subdomains: Set[str] = set()
    source_contributions: Dict[str, int] = {}

    try:
        async with httpx.AsyncClient(verify=not args.insecure) as client:
            tasks = []
            
            def create_callback(name: str) -> Callable:
                async def callback(count_increment: int = 0, status: Optional[str] = None):
                    await progress_manager.update_status(name, count_increment, status)
                return callback

            for name, plugin in tool_plugins.items():
                tasks.append(run_tool_task(plugin, domain, args.timeout, create_callback(name)))
            
            for name, plugin in api_plugins.items():
                tasks.append(query_api_task(client, plugin, domain, args.api_retries, args.timeout, create_callback(name)))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_plugin_items = list(tool_plugins.items()) + list(api_plugins.items())
            
            for i, result in enumerate(results):
                name = all_plugin_items[i][0]
                if isinstance(result, set):
                    initial_size = len(all_subdomains)
                    all_subdomains.update(result)
                    source_contributions[name] = len(all_subdomains) - initial_size
                else:
                    source_contributions[name] = 0
    finally:
        progress_manager.stop()

    regex_str = rf"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{{0,61}}[a-zA-Z0-9])?\.)+{re.escape(domain)}$"
    final_subdomains = {s for s in all_subdomains if re.match(regex_str, s)}

    return {"subdomains": sorted(list(final_subdomains)), "contributions": source_contributions}

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
        return

    table = Table(title="Daftar Plugin")
    table.add_column("Tipe", style="cyan"); table.add_column("Nama Plugin", style="magenta")
    for name in sorted(tool_plugins.keys()): table.add_row("Tool", name)
    for name in sorted(api_plugins.keys()): table.add_row("API", name)
    safe_console_print(table)

async def main():
    """Fungsi utama untuk parsing argumen dan menjalankan program."""
    parser = argparse.ArgumentParser(description=f"Recon Engine v{VERSION}", formatter_class=argparse.RawTextHelpFormatter)
    
    group_target = parser.add_mutually_exclusive_group(required=True)
    group_target.add_argument("-d", "--domain", help="Domain target tunggal.")
    group_target.add_argument("-i", "--input", help="File berisi daftar domain.")
    group_target.add_argument("--list-plugins", action="store_true", help="Tampilkan semua plugin yang tersedia dan keluar.")
    
    group_plugin = parser.add_mutually_exclusive_group()
    group_plugin.add_argument("--use-plugins", help="Hanya gunakan plugin spesifik (pisah koma).")
    group_plugin.add_argument("--exclude-plugins", help="Kecualikan plugin spesifik (pisah koma).")
    
    parser.add_argument("-o", "--output", help="File output (format dari ekstensi). Gunakan '%%d' untuk nama domain.")
    parser.add_argument("-t", "--timeout", type=float, default=30.0, help="Timeout per task (detik).")
    parser.add_argument("--threads", type=int, default=10, help="Jumlah thread untuk tool eksternal.")
    parser.add_argument("--api-retries", type=int, default=3, help="Jumlah percobaan ulang API.")
    parser.add_argument("--insecure", action="store_true", help="Bypass verifikasi SSL/TLS.")
    parser.add_argument("--overwrite", action="store_true", help="Timpa file output jika sudah ada.")
    parser.add_argument("--no-live-ui", action="store_true", help="Nonaktifkan tampilan Live Progress Table.")
    parser.add_argument("-s", "--silent", action="store_true", help="Mode senyap.")
    parser.add_argument("--debug", action="store_true", help="Aktifkan logging DEBUG.")
    parser.add_argument("--log-file", help="Simpan log ke file (dengan rotasi otomatis).")
    parser.add_argument("--cache-dir", type=Path, help="Direktori untuk menyimpan cache hasil.")
    parser.add_argument("--no-cache", action="store_true", help="Jangan gunakan cache untuk pemindaian ini.")
    
    args = parser.parse_args()

    setup_logging(args.silent, args.debug, args.log_file)
    
    if args.list_plugins:
        display_available_plugins()
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

    if not tool_plugins and not api_plugins:
        logging.error("[SYSTEM] Tidak ada plugin yang berhasil dimuat. Pastikan direktori 'plugins/' ada.")
        sys.exit(1)

    for i, domain in enumerate(all_domains):
        domain_to_scan = domain.encode("idna").decode("ascii")
        cache_file, lock_file = None, None
        
        if args.cache_dir and not args.no_cache:
            if not FILELOCK_AVAILABLE:
                logging.warning("[CACHE] Cache dinonaktifkan karena 'filelock' tidak ada.")
            else:
                args.cache_dir.mkdir(parents=True, exist_ok=True)
                plugin_hash = hashlib.md5(f"{VERSION}{sorted(api_plugins.keys() | tool_plugins.keys())}".encode()).hexdigest()[:8]
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
                                    process_final_results(domain, cache_content['data'], len(all_domains), i + 1, args)
                                    continue
                                else: logging.warning(f"[CACHE] Cache untuk {domain} rusak. Scan ulang.")
                            except (json.JSONDecodeError, KeyError): logging.warning(f"[CACHE] Cache untuk {domain} tidak bisa dibaca. Scan ulang.")
                except Timeout: logging.warning(f"[CACHE] Gagal mendapatkan lock untuk cache {domain}, melanjutkan tanpa cache.")
        
        try:
            recon_task = run_recon_for_domain(domain_to_scan, args, tool_plugins, api_plugins)
            results = await asyncio.wait_for(recon_task, timeout=getattr(args, 'global_timeout', None))
            
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

            process_final_results(domain, results, len(all_domains), i + 1, args)
        except asyncio.TimeoutError:
            logging.error(f"[SYSTEM] Recon untuk [red]{domain}[/] dihentikan karena timeout global.")
        except Exception as e:
            logging.error(f"[SYSTEM] Error tak terduga saat memproses [red]{domain}[/red]: {e}", exc_info=True)

    safe_console_print("\n[bold green]✅ Semua task selesai.[/bold green]")

if __name__ == "__main__":
    if sys.platform == "win32" and sys.version_info >= (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    if RICH_AVAILABLE is False:
        print("WARNING: Pustaka 'rich' tidak ditemukan. Tampilan UI akan terbatas.", file=sys.stderr)
    
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