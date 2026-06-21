"""Recon pipeline — in-memory stages, single output file."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING
from urllib.parse import urlparse

from core import VERSION
from core.config import ReconConfig
from core.external_tools import ExternalToolError, ExternalToolResolver
from core.orchestrator import ReconOrchestrator
from core.plugin_loader import load_plugins
from core.scope_filter import filter_in_scope

if TYPE_CHECKING:
    from ui.presenter import ReconPresenter

FINAL_ARTIFACT = "recon.txt"

STAGES = (
    ("enumerate", "Enumerasi subdomain"),
    ("filter", "Filter in-scope"),
    ("dnsx", "DNS resolve"),
    ("httpx", "HTTP probe"),
    ("write", "Menulis hasil"),
)


@dataclass
class PipelineConfig:
    """Pipeline options — only ``output_file`` is written to disk."""

    output_file: Path
    enum_timeout: float = 300.0
    enum_only: bool = False
    httpx_probe_timeout: int = 10
    httpx_probe_retries: int = 2
    httpx_info_timeout: int = 5
    httpx_info_retries: int = 2
    max_host_length: int = 60
    skip_dnsx: bool = False
    httpx_bin: Optional[str] = None
    dnsx_bin: Optional[str] = None
    recon_config: Optional[ReconConfig] = None


def resolve_output_file(domain: str, output: Optional[str]) -> Path:
    if output:
        return Path(output)
    return Path(FINAL_ARTIFACT)


def clean_hostname(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if "://" in line:
        host = urlparse(line).hostname
        return host.lower() if host else line.lower()
    return line.lower().lstrip("*.")


def sanitize_httpx_output(lines: List[str], *, enum_only: bool) -> List[str]:
    if enum_only:
        hosts = sorted(
            {clean_hostname(ln) for ln in lines if ln and "[FAILED]" not in ln.upper()}
        )
        return [h for h in hosts if h]
    return [
        ln for ln in lines
        if "[SUCCESS]" in ln and "[FAILED]" not in ln.upper()
    ]


class ReconPipeline:
    """Runs all stages in memory; writes exactly one output file."""

    def __init__(
        self,
        domain: str,
        config: PipelineConfig,
        presenter: Optional["ReconPresenter"] = None,
        console=None,
        rich_available: bool = False,
    ):
        self.domain = domain.strip().lower()
        self.domain_ascii = self.domain.encode("idna").decode("ascii")
        self.config = config
        self.output_file = config.output_file
        self.ui = presenter
        self.tools = ExternalToolResolver(config.httpx_bin, config.dnsx_bin)
        self.recon_config = config.recon_config or ReconConfig(timeout=config.enum_timeout)
        self.orchestrator = ReconOrchestrator(
            version=VERSION,
            config=self.recon_config,
            console=console,
            rich_available=rich_available,
            print_fn=None,
        )
        self._started = time.monotonic()

    def _ok(self, msg: str) -> None:
        if self.ui:
            self.ui.stage_ok(msg)

    def _warn(self, msg: str) -> None:
        if self.ui:
            self.ui.stage_warn(msg)

    def _run_stdin_tool(self, binary: Path, args: List[str], hosts: List[str], label: str) -> List[str]:
        if not hosts:
            return []

        payload = "\n".join(hosts) + "\n"
        cmd = [str(binary), *args]
        logging.debug(f"[PIPELINE] {label}: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                input=payload,
                capture_output=True,
                text=True,
                timeout=max(self.config.enum_timeout, 600),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{label} timeout") from exc

        if proc.returncode not in (0, 1):
            stderr = proc.stderr.strip()
            raise RuntimeError(f"{label} gagal (exit {proc.returncode}): {stderr[:500]}")

        return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    async def _enumerate(self) -> List[str]:
        label = "Enumerasi subdomain"
        if self.ui and self.ui.enabled:
            with self.ui.stage(label) as (_progress, _task):
                hosts = await self._run_enum()
        else:
            hosts = await self._run_enum()
        if self.ui:
            self.ui.stats.enum = len(hosts)
        self._ok(f"{len(hosts)} host ditemukan")
        return hosts

    async def _run_enum(self) -> List[str]:
        tool_plugins = load_plugins("tools", None, None)
        api_plugins = load_plugins("api", None, None)
        for key in [k for k in api_plugins if "wayback" in k.lower()]:
            del api_plugins[key]

        if not tool_plugins and not api_plugins and not self.recon_config.wayback:
            raise RuntimeError("Tidak ada plugin aktif untuk enumerasi.")

        results = await self.orchestrator.run_for_domain(
            self.domain_ascii, tool_plugins, api_plugins, show_header=False
        )
        return sorted(results.get("subdomains", {}).keys())

    def _filter(self, hosts: List[str]) -> List[str]:
        label = f"Filter scope {self.domain}"
        if self.ui and self.ui.enabled:
            with self.ui.stage(label):
                filtered = filter_in_scope(hosts, self.domain, max_length=self.config.max_host_length)
        else:
            filtered = filter_in_scope(hosts, self.domain, max_length=self.config.max_host_length)

        dropped = len(hosts) - len(filtered)
        if self.ui:
            self.ui.stats.filtered = len(filtered)
            self.ui.stats.dropped = dropped
        self._ok(f"{len(filtered)} in-scope ({dropped} dibuang)")
        return filtered

    def _dnsx(self, hosts: List[str]) -> List[str]:
        if self.config.skip_dnsx:
            self._warn("dnsx dilewati (--skip-dnsx)")
            return hosts

        if not hosts:
            return []

        label = "DNS resolve (dnsx)"
        try:
            if self.ui and self.ui.enabled:
                with self.ui.stage(label):
                    resolved = self._run_stdin_tool(self.tools.dnsx(), ["-silent"], hosts, "dnsx")
            else:
                resolved = self._run_stdin_tool(self.tools.dnsx(), ["-silent"], hosts, "dnsx")
        except ExternalToolError as e:
            logging.warning(f"[PIPELINE] dnsx tidak tersedia: {e}")
            self._warn(f"dnsx dilewati — pass-through {len(hosts)} host")
            return hosts

        if self.ui:
            self.ui.stats.resolved = len(resolved)
        self._ok(f"{len(resolved)}/{len(hosts)} resolved")
        return resolved

    def _httpx_args(self) -> List[str]:
        if self.config.enum_only:
            return [
                "-silent", "-no-color",
                "-timeout", str(self.config.httpx_probe_timeout),
                "-retries", str(self.config.httpx_probe_retries),
            ]
        return [
            "-sc", "-cl", "-td", "-title", "-ip", "-probe", "-fhr",
            "-location", "-server", "-no-color",
            "-timeout", str(self.config.httpx_info_timeout),
            "-retries", str(self.config.httpx_info_retries),
        ]

    def _httpx(self, hosts: List[str]) -> List[str]:
        if not hosts:
            return []

        mode = "live check" if self.config.enum_only else "fingerprint"
        label = f"HTTP probe ({mode})"
        if self.ui and self.ui.enabled:
            with self.ui.stage(label):
                lines = self._run_httpx(hosts)
        else:
            lines = self._run_httpx(hosts)

        if self.ui:
            self.ui.stats.live = len(lines)
        self._ok(f"{len(lines)}/{len(hosts)} live")
        return lines

    def _run_httpx(self, hosts: List[str]) -> List[str]:
        raw = self._run_stdin_tool(self.tools.httpx(), self._httpx_args(), hosts, "httpx")
        lines = sanitize_httpx_output(raw, enum_only=self.config.enum_only)
        dropped = len(raw) - len(lines)
        if dropped:
            logging.debug(f"[PIPELINE] {dropped} baris FAILED dibuang")
        return lines

    def _write_output(self, lines: List[str]) -> Path:
        label = f"Menulis {self.output_file.name}"
        if self.ui and self.ui.enabled:
            with self.ui.stage(label):
                self.output_file.parent.mkdir(parents=True, exist_ok=True)
                self.output_file.write_text(
                    "\n".join(lines) + ("\n" if lines else ""),
                    encoding="utf-8",
                )
        else:
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            self.output_file.write_text(
                "\n".join(lines) + ("\n" if lines else ""),
                encoding="utf-8",
            )
        if self.ui:
            self.ui.stats.written = len(lines)
        return self.output_file

    async def run(self) -> Path:
        raw = await self._enumerate()
        scoped = self._filter(raw)
        resolved = self._dnsx(scoped)
        lines = self._httpx(resolved)
        path = self._write_output(lines)
        if self.ui:
            self.ui.summary(path, time.monotonic() - self._started)
        return path
