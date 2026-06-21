#!/usr/bin/env python3

# --- Error Handling untuk Modul Eksternal ---
import sys

missing_modules = []

try:
    import click
except ImportError:
    missing_modules.append("click")

try:
    from rich import print
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    missing_modules.append("rich")

def render_missing_module_notice(modules):
    if not RICH_AVAILABLE:
        # Fallback jika rich tidak tersedia
        print("\n[!] Modul berikut belum terinstal:")
        for mod in modules:
            print(f"   - {mod}")
        print("\n➜ Jalankan perintah berikut untuk menginstal:")
        print(f"   pip install {' '.join(modules)}\n")
    else:
        # Tampilan mewah dengan rich
        console = Console()
        table = Table.grid(padding=(1, 2))
        table.add_column(justify="left")

        table.add_row("[bold red]Modul berikut belum terinstal:[/]")
        for mod in modules:
            table.add_row(f"[yellow]- {mod}[/]")

        table.add_row("")
        table.add_row("[bold green]➜ Jalankan perintah berikut untuk menginstal:[/]")
        table.add_row(f"[bold white on blue]pip install {' '.join(modules)}[/]")

        panel = Panel(table, title="Dependency Checker", border_style="red", expand=False)
        console.print(panel)

if missing_modules:
    render_missing_module_notice(missing_modules)
    sys.exit(1)

# --- Modul Standar ---
import os
import subprocess
import shutil
from pathlib import Path

from core.paths import REPO_ROOT

console = Console()
TOOLS_DIR = REPO_ROOT / "tools_bin"

@click.group()
def cli():
    pass

def sync_tools_from_dir(src_root: Path):
    """Copy PD binaries from an external directory into tools_bin/."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    pairs = [("httpx", "pd-httpx"), ("dnsx", "dnsx")]
    for src_name, dst_name in pairs:
        src = src_root / src_name
        dst = TOOLS_DIR / dst_name
        if not src.is_file():
            raise FileNotFoundError(f"Tidak ditemukan: {src}")
        shutil.copy2(src, dst)
        dst.chmod(0o755)
        console.print(f"[green]✔[/] {src} → {dst}")


def ensure_pd_binaries():
    """Download pd-httpx & dnsx from GitHub if not already in tools_bin/."""
    if (TOOLS_DIR / "pd-httpx").is_file() and (TOOLS_DIR / "dnsx").is_file():
        return
    console.print("[yellow]Mengunduh pd-httpx & dnsx ke tools_bin/...[/]")
    install_zip_binary(
        "pd-httpx",
        "https://github.com/projectdiscovery/httpx/releases/latest/download/httpx_linux_amd64.zip",
    )
    install_zip_binary(
        "dnsx",
        "https://github.com/projectdiscovery/dnsx/releases/latest/download/dnsx_linux_amd64.zip",
    )


@cli.command("sync-tools")
@click.argument("source_dir", required=False, type=click.Path(exists=True, file_okay=False))
def sync_tools_cmd(source_dir):
    """
    Salin pd-httpx & dnsx ke tools_bin/ dari direktori sumber.

    Gunakan argumen path, atau set env HEPH_TOOLS=/path/to/bin
    """
    try:
        src = Path(source_dir) if source_dir else Path(os.environ["HEPH_TOOLS"])
        sync_tools_from_dir(src)
        console.print("[bold green]Sync tools_bin selesai.[/]")
    except KeyError:
        console.print("[bold red]Berikan path argumen atau set HEPH_TOOLS=/path/to/bin[/]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Gagal:[/] {e}")
        sys.exit(1)


@cli.command()
def install():
    layout = Table.grid(expand=True)
    layout.add_column(justify="center", ratio=1)

    layout.add_row(Panel.fit(
        "[bold green]🚀 Recon Engine Installer v1.0.0[/]",
        subtitle="by Haza",
        padding=(1, 4),
        border_style="green",
    ))

    layout.add_row(get_env_panel())

    tasks = [
        ("Memeriksa alat sistem dasar", lambda: check_tools(["curl", "wget", "unzip", "git"])),
        ("Memeriksa Golang", check_golang),
        ("Menginstal dependensi Python", check_python_dependencies),
        ("Sync binary PD (pd-httpx, dnsx)", ensure_pd_binaries),
        ("Menginstal tools eksternal", install_tools),
        ("Menambahkan PATH ke shell config", update_shell_path),
    ]

    for message, task in tasks:
        run_with_spinner(message, task)

    layout.add_row(Panel.fit(
        "[bold green]🚀 Instalasi selesai![/]\n[bold yellow]   python recon.py example.com -t 300[/]",
        border_style="green",
    ))

    console.print(Panel(layout, border_style="bright_blue"))

def get_env_panel():
    table = Table.grid(padding=(0, 2))
    table.add_column("Komponen", style="cyan", no_wrap=True, justify="right")
    table.add_column("Versi / Path", style="white", justify="left")

    table.add_row("Python", sys.version.split()[0])
    table.add_row("Go", get_go_version())
    table.add_row("Virtualenv", os.environ.get("VIRTUAL_ENV", "- (tidak aktif)"))

    return Panel(table, title="Environment Info", border_style="cyan", padding=(0, 1))

def get_go_version():
    if not shutil.which("go"):
        return "Tidak ditemukan"
    try:
        output = subprocess.check_output(["go", "version"], text=True).strip()
        parts = output.split()
        return parts[2] if len(parts) > 2 else output
    except subprocess.CalledProcessError:
        return "Error saat membaca versi Go"

def run_with_spinner(message, func):
    with Progress(SpinnerColumn(), TextColumn(f"[yellow]{message}..."), transient=True) as progress:
        task = progress.add_task("run", start=True)
        try:
            func()
            progress.update(task, description=f"[green]✔ {message}")
        except Exception as e:
            progress.update(task, description=f"[red]✘ {message}: {e}")
            sys.exit(1)

def check_tools(tools):
    for tool in tools:
        if shutil.which(tool):
            continue
        install_package(tool)

def install_package(pkg):
    if shutil.which("apt"):
        subprocess.run(["sudo", "apt", "update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        subprocess.run(["sudo", "apt", "install", "-y", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    elif shutil.which("pkg") and not shutil.which("apt"):
        subprocess.run(["pkg", "install", "-y", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    else:
        raise RuntimeError(f"Tidak bisa menginstal {pkg}, silakan instal manual.")

def check_golang():
    if not shutil.which("go"):
        install_package("golang")
    os.environ["PATH"] = f"{Path.home()}/go/bin:" + os.environ.get("PATH", "")

def check_python_dependencies():
    if not Path("requirements.txt").exists():
        raise FileNotFoundError("File requirements.txt tidak ditemukan!")
    subprocess.run(["pip", "install", "--upgrade", "pip"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    result = subprocess.run(["pip", "install", "-r", "requirements.txt"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        raise RuntimeError("Gagal menginstal dependensi Python")

def install_zip_binary(name, url):
    """Download PD release zip and extract single binary into tools_bin."""
    import tempfile
    import zipfile

    bin_path = TOOLS_DIR / name
    if bin_path.exists():
        return

    TOOLS_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "tool.zip"
        result = subprocess.run(["curl", "-sL", "-o", str(zip_path), url], check=False)
        if result.returncode != 0 or not zip_path.exists():
            raise RuntimeError(f"Gagal mengunduh {name} dari {url}")
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.namelist() if not m.endswith("/")]
            if not members:
                raise RuntimeError(f"Arsip zip {name} kosong")
            extracted = Path(tmp) / Path(members[0]).name
            zf.extract(members[0], tmp)
            src = Path(tmp) / members[0]
            shutil.copy(src, bin_path)
        bin_path.chmod(0o755)


def install_tools():
    TOOLS_DIR.mkdir(exist_ok=True)
    tools = [
        ("subfinder", "https://github.com/projectdiscovery/subfinder/releases/latest/download/subfinder-linux-amd64"),
        ("findomain", "https://github.com/Findomain/Findomain/releases/latest/download/findomain-linux"),
    ]

    for name, url in tools:
        bin_path = TOOLS_DIR / name
        if not bin_path.exists():
            result = subprocess.run(["curl", "-sLo", str(bin_path), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0 or not bin_path.exists():
                raise RuntimeError(f"Gagal mengunduh {name} dari {url}")
            bin_path.chmod(0o755)

    install_go_tool("assetfinder", "github.com/tomnomnom/assetfinder")
    install_go_tool("amass", "github.com/owasp-amass/amass/v4/...")

def install_go_tool(name, go_path):
    bin_path = TOOLS_DIR / name
    if bin_path.exists():
        return

    subprocess.run(["go", "install", f"{go_path}@latest"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    go_bin = Path.home() / "go" / "bin" / name
    if go_bin.exists():
        shutil.copy(go_bin, bin_path)
        bin_path.chmod(0o755)
    else:
        raise FileNotFoundError(f"{name} tidak ditemukan setelah go install")

def update_shell_path():
    shell_rcs = [Path.home() / f for f in [".bashrc", ".zshrc"]]
    path_entry = f'export PATH="{TOOLS_DIR.absolute()}:$HOME/go/bin:$PATH"'

    for rc in shell_rcs:
        if rc.exists() and path_entry not in rc.read_text():
            with rc.open("a") as f:
                f.write(f"\n{path_entry}\n")

if __name__ == '__main__':
    cli()
