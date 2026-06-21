# core/plugin_loader.py
import importlib
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.base_plugin import BaseAPIPlugin, BaseToolPlugin

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from core.paths import REPO_ROOT

BASE_DIR = REPO_ROOT
CONSOLE = Console(color_system="auto") if RICH_AVAILABLE else None

PluginInstance = Union[BaseAPIPlugin, BaseToolPlugin, Any]


def _validate_plugin(plugin_instance: PluginInstance, plugin_type: str, module_name: str) -> bool:
    if not hasattr(plugin_instance, "name") or not plugin_instance.name:
        logging.warning(f"[LOADER] Plugin {module_name} dilewati: atribut '.name' kosong.")
        return False

    if plugin_type == "tools":
        if not callable(getattr(plugin_instance, "get_command", None)):
            logging.warning(
                f"[LOADER] Plugin Tool '{plugin_instance.name}' dilewati: metode 'get_command' tidak valid."
            )
            return False
    elif plugin_type == "api":
        if not (hasattr(plugin_instance, "url") and callable(getattr(plugin_instance, "parse", None))):
            logging.warning(
                f"[LOADER] Plugin API '{plugin_instance.name}' dilewati: 'url' atau 'parse' tidak valid."
            )
            return False

    return True


def load_plugins(
    plugin_type: str,
    use_only: Optional[List[str]],
    exclude: Optional[List[str]],
) -> Dict[str, PluginInstance]:
    """Discover and load plugins from plugins/<type>/*.py."""
    loaded_plugins: Dict[str, PluginInstance] = {}
    plugin_dir = BASE_DIR / "plugins" / plugin_type
    if not plugin_dir.is_dir():
        logging.warning(f"[LOADER] Direktori plugin 'plugins/{plugin_type}' tidak ditemukan.")
        return {}

    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("__"):
            continue
        module_name = f"plugins.{plugin_type}.{py_file.stem}"
        try:
            module = importlib.import_module(module_name)
            plugin_instance = module.Plugin()

            if not _validate_plugin(plugin_instance, plugin_type, module_name):
                continue

            name_lower = plugin_instance.name.lower()
            if use_only and name_lower not in use_only:
                continue
            if exclude and name_lower in exclude:
                continue

            if plugin_type == "tools":
                tool_command = getattr(plugin_instance, "binary_name", plugin_instance.name.split()[0])
                if not shutil.which(tool_command):
                    logging.warning(
                        f"[LOADER] Tool '{tool_command}' untuk plugin '{plugin_instance.name}' "
                        "tidak terinstal. Plugin dilewati."
                    )
                    continue

            loaded_plugins[plugin_instance.name] = plugin_instance
        except Exception as e:
            logging.error(f"[LOADER] Plugin '{module_name}' gagal dimuat: {e}", exc_info=True)

    return loaded_plugins


def lint_plugins() -> int:
    """Validate all plugins and print a status report. Returns error count."""
    if not CONSOLE:
        print("Fitur linting memerlukan pustaka 'rich'. Mohon install: pip install rich")
        return 1

    CONSOLE.print(Panel.fit("[bold green]🔍 Menjalankan Linter untuk Plugin Recon Engine[/bold green]"))

    table = Table(title="Laporan Validasi Plugin")
    table.add_column("Nama Plugin", style="cyan", no_wrap=True)
    table.add_column("Tipe", style="magenta")
    table.add_column("Atribut", style="yellow")
    table.add_column("Status", style="bold")

    total_errors = 0

    for p_type in ("api", "tools"):
        plugin_dir = BASE_DIR / "plugins" / p_type
        if not plugin_dir.is_dir():
            continue

        for py_file in sorted(plugin_dir.glob("*.py")):
            if py_file.name.startswith("__"):
                continue

            module_name = f"plugins.{p_type}.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                plugin = module.Plugin()

                if hasattr(plugin, "name") and plugin.name:
                    table.add_row(plugin.name, p_type.capitalize(), ".name", "[green]OK[/green]")
                else:
                    table.add_row(
                        f"[dim]{module_name}[/dim]",
                        p_type.capitalize(),
                        ".name",
                        "[red]GAGAL (Atribut Wajib)[/red]",
                    )
                    total_errors += 1
                    continue

                if p_type == "api":
                    for attr, label in (("url", ".url"), ("parse", ".parse()")):
                        ok = hasattr(plugin, "url") if attr == "url" else callable(getattr(plugin, "parse", None))
                        if ok:
                            table.add_row(plugin.name, "API", label, "[green]OK[/green]")
                        else:
                            table.add_row(plugin.name, "API", label, "[red]GAGAL[/red]")
                            total_errors += 1
                    base_ok = isinstance(plugin, BaseAPIPlugin)
                    table.add_row(
                        plugin.name,
                        "API",
                        "BaseAPIPlugin",
                        "[green]OK[/green]" if base_ok else "[yellow]Legacy[/yellow]",
                    )
                else:
                    if callable(getattr(plugin, "get_command", None)):
                        table.add_row(plugin.name, "Tool", ".get_command()", "[green]OK[/green]")
                    else:
                        table.add_row(plugin.name, "Tool", ".get_command()", "[red]GAGAL[/red]")
                        total_errors += 1

                    tool_cmd = getattr(plugin, "binary_name", plugin.name.split()[0])
                    found = shutil.which(tool_cmd)
                    table.add_row(
                        plugin.name,
                        "Tool",
                        f"shutil.which('{tool_cmd}')",
                        "[green]Ditemukan[/green]" if found else "[red]Tidak Ditemukan[/red]",
                    )
                    if not found:
                        total_errors += 1
                    base_ok = isinstance(plugin, BaseToolPlugin)
                    table.add_row(
                        plugin.name,
                        "Tool",
                        "BaseToolPlugin",
                        "[green]OK[/green]" if base_ok else "[yellow]Legacy[/yellow]",
                    )

            except Exception as e:
                table.add_row(
                    f"[dim]{module_name}[/dim]",
                    p_type.capitalize(),
                    "Inisialisasi",
                    f"[red]GAGAL ({e})[/red]",
                )
                total_errors += 1

    CONSOLE.print(table)
    if total_errors == 0:
        CONSOLE.print("\n[bold green]✅ Semua plugin tervalidasi dengan sukses![/bold green]")
    else:
        CONSOLE.print(f"\n[bold red]❌ Ditemukan {total_errors} error pada konfigurasi plugin.[/bold red]")
    return total_errors
