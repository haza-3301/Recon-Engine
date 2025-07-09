# ui/live_progress.py
"""
Modul untuk mengelola dan menampilkan Live Progress Table menggunakan Rich.
"""
import asyncio
from typing import Dict, Any, Optional
from rich.console import Console
from rich.live import Live
from rich.table import Table

class LiveProgressManager:
    """
    Mengelola status plugin dan me-render tabel live secara async-safe.
    """
    def __init__(self, console: Optional[Console], enabled: bool = True):
        self.console = console
        self.enabled = enabled and console is not None
        self.plugins_status: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._live: Optional[Live] = None

    def _generate_table(self) -> Table:
        """Membuat objek tabel Rich dari data status saat ini."""
        table = Table(title="[bold blue]Recon Engine Live Progress[/bold blue]", border_style="green")
        table.add_column("Sumber Plugin", style="cyan", no_wrap=True)
        table.add_column("Subdomain Baru", justify="right", style="magenta")
        table.add_column("Status", justify="center")

        status_colors = {
            "PENDING": "[grey50]PENDING[/]",
            "RUNNING": "[yellow]⏳ RUNNING[/]",
            "COMPLETED": "[green]✅ COMPLETED[/]",
            "FAILED": "[red]❌ FAILED[/]",
            "TIMEOUT": "[red]⏰ TIMEOUT[/]",
            "CACHED": "[blue]💾 CACHED[/]",
        }

        for name, data in sorted(self.plugins_status.items()):
            status_text = status_colors.get(data['status'], data['status'])
            table.add_row(name, str(data['count']), status_text)
        
        return table

    async def add_plugins(self, names: list):
        """Mendaftarkan semua plugin ke tabel dengan status PENDING."""
        async with self._lock:
            for name in names:
                self.plugins_status[name] = {'count': 0, 'status': 'PENDING'}
        await self._update_display()

    async def update_status(self, name: str, count_increment: int = 0, status: Optional[str] = None):
        """Memperbarui status dan jumlah subdomain untuk sebuah plugin."""
        if not self.enabled: return
        async with self._lock:
            if name not in self.plugins_status:
                self.plugins_status[name] = {'count': 0, 'status': 'PENDING'}
            
            self.plugins_status[name]['count'] += count_increment
            if status:
                self.plugins_status[name]['status'] = status
        await self._update_display()

    async def _update_display(self):
        """Memicu re-render tabel live."""
        if self.enabled and self._live:
            self._live.update(self._generate_table(), refresh=True)

    def start(self):
        """Memulai tampilan live table."""
        if self.enabled:
            # Menggunakan transient=False (default) agar tabel tetap terlihat
            self._live = Live(self._generate_table(), console=self.console, refresh_per_second=10)
            self._live.start()

    def stop(self):
        """Menghentikan tampilan live table."""
        if self.enabled and self._live:
            # Cukup hentikan live update. Tabel akan tetap di layar.
            self._live.stop()
            # HAPUS baris print di sini untuk menghilangkan duplikasi
            # self.console.print(self._generate_table())