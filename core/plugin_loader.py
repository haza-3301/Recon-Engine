# core/plugin_loader.py
import importlib
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

# Coba impor Rich untuk tampilan tabel yang lebih baik
try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

BASE_DIR = Path(__file__).parent.parent.resolve()
CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None

def load_plugins(plugin_type: str, use_only: Optional[List[str]], exclude: Optional[List[str]]) -> Dict[str, Any]:
    """
    Memuat dan memvalidasi plugin dari direktori yang ditentukan.
    """
    loaded_plugins: Dict[str, Any] = {}
    plugin_dir = BASE_DIR / "plugins" / plugin_type
    if not plugin_dir.is_dir():
        logging.warning(f"[LOADER] Direktori plugin 'plugins/{plugin_type}' tidak ditemukan.")
        return {}

    for py_file in plugin_dir.glob("*.py"):
        if py_file.name.startswith("__"):
            continue
        module_name = f"plugins.{plugin_type}.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            plugin_instance = module.Plugin()

            # Validasi Atribut Esensial
            if not hasattr(plugin_instance, "name"):
                logging.warning(f"[LOADER] Plugin {module_name} dilewati: tidak ada atribut '.name'.")
                continue
            
            # Validasi Spesifik Tipe Plugin
            if plugin_type == "tools" and not callable(getattr(plugin_instance, "get_command", None)):
                logging.warning(f"[LOADER] Plugin Tool '{plugin_instance.name}' dilewati: metode 'get_command' tidak valid.")
                continue
            if plugin_type == "api" and not (hasattr(plugin_instance, "url") and callable(getattr(plugin_instance, "parse", None))):
                logging.warning(f"[LOADER] Plugin API '{plugin_instance.name}' dilewati: atribut 'url' atau metode 'parse' tidak valid.")
                continue

            name_lower = plugin_instance.name.lower()
            if use_only and name_lower not in use_only:
                continue
            if exclude and name_lower in exclude:
                continue
            
            # Validasi dependensi tool eksternal
            if plugin_type == "tools":
                tool_command = plugin_instance.name.split()[0]
                if not shutil.which(tool_command):
                    logging.warning(f"[LOADER] Tool '{tool_command}' untuk plugin '{plugin_instance.name}' tidak terinstal. Plugin dilewati.")
                    continue
            
            loaded_plugins[plugin_instance.name] = plugin_instance
        except Exception as e:
            logging.error(f"[LOADER] Plugin '{module_name}' gagal dimuat: {e}", exc_info=True)
            
    return loaded_plugins

def lint_plugins():
    """
    Memvalidasi semua plugin yang ada dan menampilkan laporan status.
    """
    if not CONSOLE:
        print("Fitur linting memerlukan pustaka 'rich'. Mohon install: pip install rich")
        return

    CONSOLE.print(Panel.fit("[bold green]🔍 Menjalankan Linter untuk Plugin Recon Engine[/bold green]"))

    table = Table(title="Laporan Validasi Plugin")
    table.add_column("Nama Plugin", style="cyan", no_wrap=True)
    table.add_column("Tipe", style="magenta")
    table.add_column("Atribut", style="yellow")
    table.add_column("Status", style="bold")

    plugin_types = ["api", "tools"]
    total_errors = 0

    for p_type in plugin_types:
        plugin_dir = BASE_DIR / "plugins" / p_type
        if not plugin_dir.is_dir():
            continue
            
        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue

            module_name = f"plugins.{p_type}.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                plugin = module.Plugin()

                # Cek Atribut Nama
                if hasattr(plugin, "name"):
                    table.add_row(plugin.name, p_type.capitalize(), ".name", "[green]OK[/green]")
                else:
                    table.add_row(f"[dim]{module_name}[/dim]", p_type.capitalize(), ".name", "[red]GAGAL (Atribut Wajib)[/red]")
                    total_errors += 1
                    continue # Tidak bisa lanjut jika nama tidak ada

                # Cek Atribut Spesifik Tipe
                if p_type == "api":
                    if hasattr(plugin, "url"): table.add_row(plugin.name, "API", ".url", "[green]OK[/green]")
                    else: table.add_row(plugin.name, "API", ".url", "[red]GAGAL[/red]"); total_errors += 1
                    
                    if callable(getattr(plugin, "parse", None)): table.add_row(plugin.name, "API", ".parse()", "[green]OK[/green]")
                    else: table.add_row(plugin.name, "API", ".parse()", "[red]GAGAL[/red]"); total_errors += 1

                elif p_type == "tools":
                    if callable(getattr(plugin, "get_command", None)): table.add_row(plugin.name, "Tool", ".get_command()", "[green]OK[/green]")
                    else: table.add_row(plugin.name, "Tool", ".get_command()", "[red]GAGAL[/red]"); total_errors += 1

                    tool_cmd = plugin.name.split()[0]
                    if shutil.which(tool_cmd): table.add_row(plugin.name, "Tool", f"shutil.which('{tool_cmd}')", "[green]Ditemukan[/green]")
                    else: table.add_row(plugin.name, "Tool", f"shutil.which('{tool_cmd}')", "[red]Tidak Ditemukan[/red]"); total_errors += 1

            except Exception as e:
                table.add_row(f"[dim]{module_name}[/dim]", p_type.capitalize(), "Inisialisasi", f"[red]GAGAL ({e})[/red]")
                total_errors += 1

    CONSOLE.print(table)
    if total_errors == 0:
        CONSOLE.print("\n[bold green]✅ Semua plugin tervalidasi dengan sukses![/bold green]")
    else:
        CONSOLE.print(f"\n[bold red]❌ Ditemukan {total_errors} error pada konfigurasi plugin.[/bold red]")