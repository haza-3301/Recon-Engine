"""Rich CLI presenter — banner, stage animation, summary."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@dataclass
class StageStats:
    enum: int = 0
    filtered: int = 0
    dropped: int = 0
    resolved: int = 0
    live: int = 0
    written: int = 0


class ReconPresenter:
    """Polished terminal output for recon.py."""

    def __init__(self, console: Optional["Console"], *, enabled: bool = True):
        self.console = console
        self.enabled = enabled and console is not None and RICH_AVAILABLE
        self.stats = StageStats()

    def _print(self, content: Any, **kwargs) -> None:
        if self.enabled and self.console:
            self.console.print(content, **kwargs)
        elif not self.enabled:
            import re
            print(re.sub(r"\[.*?\]", "", str(content)))

    def banner(self, version: str) -> None:
        if not self.enabled:
            return
        art = r"""
  ____                __         ____
 / __ \___  ___ ___  / /_ ___   / __/__  ___ ________
/ /_/ / _ \/ -_) _ \/ / // -_) / _// _ \/ -_) __/ _ \
\____/ .__/\__/_//_/_/\_,/\__/ /_/  \___/\__/_/ /_//_/
    /_/"""
        self._print(
            Panel(
                Group(
                    Text(art.strip(), style="bold cyan", justify="center"),
                    Text(f"v{version}", style="bold magenta", justify="center"),
                ),
                border_style="bright_green",
                padding=(0, 2),
                expand=False,
            )
        )

    def mission(self, domain: str, output: Path, mode: str) -> None:
        if not self.enabled:
            self._print(f"Target: {domain} → {output} ({mode})")
            return
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold cyan", justify="right", no_wrap=True)
        grid.add_column(style="white", no_wrap=True)
        grid.add_row("Target", f"[bold yellow]{domain}[/]")
        grid.add_row("Output", f"[cyan]{str(output)}[/]")
        grid.add_row("Mode", f"[dim]{mode}[/]")
        self._print(Panel(grid, title="[bold]Recon[/]", border_style="blue", expand=False))

    @contextmanager
    def stage(self, label: str, total: Optional[int] = None):
        """Spinner while a stage runs."""
        if not self.enabled:
            print(f"▶ {label}…")
            yield None, None
            return

        columns = [
            SpinnerColumn("dots", style="cyan"),
            TextColumn("[bold cyan]{task.description}[/]"),
        ]
        if total:
            columns.extend([BarColumn(bar_width=24), TaskProgressColumn()])

        with Progress(*columns, console=self.console, transient=True) as progress:
            task = progress.add_task(label, total=total)
            yield progress, task

    def stage_ok(self, message: str) -> None:
        self._print(f"  [green]✓[/] {message}")

    def stage_warn(self, message: str) -> None:
        self._print(f"  [yellow]![/] {message}")

    def summary(self, output: Path, elapsed_s: float) -> None:
        s = self.stats
        if not self.enabled:
            print(f"Done: {s.written} lines → {output}")
            return

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim")
        table.add_column("Val", style="bold")
        table.add_row("Enumerated", str(s.enum))
        table.add_row("In-scope", str(s.filtered))
        table.add_row("DNS resolved", str(s.resolved))
        table.add_row("Live", str(s.live))
        table.add_row("Written", f"[green]{s.written}[/]")
        table.add_row("Time", f"{elapsed_s:.0f}s")

        self._print(
            Panel(
                Group(table, Text(f"📄 {output}", style="bold cyan")),
                title="[bold green]Complete[/]",
                border_style="green",
                expand=False,
            )
        )
