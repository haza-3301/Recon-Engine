"""Async recon orchestration — plugin execution and result aggregation."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, Optional, Set

import httpx

from core.config import ReconConfig
from core.error_handler import PluginError, handle_http_error, handle_plugin_exception, handle_timeout
from core.ip_resolver import DNSPYTHON_AVAILABLE as IP_RESOLVER_AVAILABLE
from core.ip_resolver import lookup_ips_asn, resolve_domains_to_ips
from core.utils import is_valid_domain, normalize_subdomain
from ui.live_progress import LiveProgressManager

WAYBACK_LABEL = "Wayback (Built-in)"


class ReconOrchestrator:
    """Runs all plugins for one domain and returns structured results."""

    def __init__(
        self,
        version: str,
        config: ReconConfig,
        console: Any = None,
        rich_available: bool = False,
        print_fn: Optional[Callable] = None,
    ):
        self.version = version
        self.config = config
        self.console = console
        self.rich_available = rich_available
        self._print = print_fn or (lambda msg, **kw: print(msg))

    async def run_tool_task(
        self,
        plugin: Any,
        domain: str,
        progress_callback: Callable,
    ) -> Set[str]:
        await progress_callback(status="RUNNING")
        command = plugin.get_command(domain)
        if not isinstance(command, list) or not command:
            raise PluginError(f"Command dari '{plugin.name}' harus list dan tidak boleh kosong.")

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                command[0],
                *command[1:],
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=self.config.timeout
            )
            stdout = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")

            if proc.returncode != 0:
                raise PluginError(
                    stderr.strip() or f"Proses gagal dengan kode {proc.returncode} tanpa output error."
                )

            result = {line.strip() for line in stdout.splitlines() if is_valid_domain(line.strip())}
            await progress_callback(count_increment=len(result), status="COMPLETED")
            return result

        except asyncio.TimeoutError:
            await progress_callback(status="TIMEOUT")
            handle_timeout(plugin.name, self.config.timeout)
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
        except FileNotFoundError:
            await progress_callback(status="FAILED")
            logging.error(
                f"[TOOL] Perintah '{command[0]}' tidak ditemukan. Pastikan tool terinstal dan ada di PATH."
            )
        except Exception as e:
            await progress_callback(status="FAILED")
            handle_plugin_exception(plugin.name, e)

        return set()

    async def query_api_task(
        self,
        client: httpx.AsyncClient,
        plugin: Any,
        domain: str,
        progress_callback: Callable,
    ) -> Set[str]:
        if getattr(plugin, "enabled", True) is False:
            await progress_callback(status="SKIPPED")
            logging.debug(f"[API] Plugin '{plugin.name}' dilewati — tidak dikonfigurasi.")
            return set()

        await progress_callback(status="RUNNING")
        url = plugin.url.format(domain=domain)
        headers = {"User-Agent": f"Recon Engine/{self.version}", **plugin.auth_headers()}

        for attempt in range(self.config.api_retries):
            try:
                resp = await client.get(
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(self.config.timeout, connect=5.0),
                )
                resp.raise_for_status()
                data = resp.json() if getattr(plugin, "is_json", True) else resp.text

                loop = asyncio.get_running_loop()
                raw_result = await loop.run_in_executor(None, plugin.parse, data)

                if not isinstance(raw_result, set):
                    raise PluginError(f"Plugin '{plugin.name}' tidak mengembalikan tipe data Set.")

                result = {sub for sub in raw_result if is_valid_domain(sub)}
                await progress_callback(count_increment=len(result), status="COMPLETED")
                return result

            except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError, PluginError) as e:
                handle_http_error(plugin.name, url, attempt, self.config.api_retries, e)
                if attempt < self.config.api_retries - 1:
                    await asyncio.sleep(2**attempt)
                else:
                    await progress_callback(status="FAILED")

        return set()

    async def run_wayback_task(
        self,
        client: httpx.AsyncClient,
        domain: str,
        progress_callback: Callable,
    ) -> Set[str]:
        await progress_callback(status="RUNNING")
        url = (
            f"http://web.archive.org/cdx/search/cdx"
            f"?url=*.{domain}/*&output=json&fl=original&collapse=urlkey"
        )
        headers = {"User-Agent": f"Recon Engine/{self.version}"}
        subdomains: Set[str] = set()

        try:
            resp = await client.get(url, headers=headers, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
            url_pattern = re.compile(
                r"https?://(?:www\.)?([a-zA-Z0-9.-]+\." + re.escape(domain) + ")"
            )

            for item in data[1:]:
                if not item:
                    continue
                match = url_pattern.match(item[0])
                if match:
                    subdomain = match.group(1)
                    if is_valid_domain(subdomain):
                        subdomains.add(normalize_subdomain(subdomain))

            await progress_callback(count_increment=len(subdomains), status="COMPLETED")
            return subdomains

        except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError) as e:
            logging.error(f"[WAYBACK] Gagal mengambil data dari Wayback Machine: {e}")
            await progress_callback(status="FAILED")
        except Exception as e:
            logging.error(f"[WAYBACK] Terjadi error tak terduga saat parsing data Wayback: {e}")
            await progress_callback(status="FAILED")

        return set()

    async def run_for_domain(
        self,
        domain: str,
        tool_plugins: Dict[str, Any],
        api_plugins: Dict[str, Any],
        *,
        show_header: bool = True,
    ) -> Dict[str, Any]:
        """Orchestrate scan for a single domain."""
        progress_manager = LiveProgressManager(
            self.console,
            enabled=self.rich_available and not self.config.silent and not self.config.no_live_ui,
        )

        if show_header:
            self._print(f"\n[bold blue]🚀 Memulai Recon untuk:[/bold blue] [bold yellow]{domain}[/bold yellow]")

        all_plugin_names = list(tool_plugins.keys()) + list(api_plugins.keys())
        if self.config.wayback:
            all_plugin_names.append(WAYBACK_LABEL)

        await progress_manager.add_plugins(all_plugin_names)
        progress_manager.start()

        all_subdomains: Set[str] = set()
        source_contributions: Dict[str, int] = {}

        try:
            async with httpx.AsyncClient(verify=not self.config.insecure) as client:
                tasks = []

                def create_callback(name: str) -> Callable:
                    async def callback(count_increment: int = 0, status: Optional[str] = None):
                        try:
                            await progress_manager.update_status(name, count_increment, status)
                        except Exception as e:
                            logging.debug(f"[CALLBACK] Error update status '{name}': {e}")

                    return callback

                for name, plugin in tool_plugins.items():
                    tasks.append(self.run_tool_task(plugin, domain, create_callback(name)))

                for name, plugin in api_plugins.items():
                    tasks.append(
                        self.query_api_task(client, plugin, domain, create_callback(name))
                    )

                if self.config.wayback:
                    tasks.append(
                        self.run_wayback_task(client, domain, create_callback(WAYBACK_LABEL))
                    )

                plugin_results = await asyncio.gather(*tasks, return_exceptions=True)

                all_plugin_items = list(tool_plugins.items()) + list(api_plugins.items())
                if self.config.wayback:
                    all_plugin_items.append((WAYBACK_LABEL, None))

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

        if self.config.max_subdomains and len(final_subdomains_set) > self.config.max_subdomains:
            logging.warning(
                f"[SYSTEM] Jumlah subdomain ({len(final_subdomains_set)}) melebihi batas "
                f"--max-subdomains ({self.config.max_subdomains}). Hasil akan dipotong."
            )
            final_subdomains_set = set(sorted(final_subdomains_set)[: self.config.max_subdomains])

        results_dict: Dict[str, Dict] = {sub: {} for sub in sorted(final_subdomains_set)}

        if self.config.resolve_ip or self.config.asn_lookup:
            if not IP_RESOLVER_AVAILABLE:
                logging.warning(
                    "[SYSTEM] Opsi --resolve-ip atau --asn-lookup memerlukan 'dnspython'. Langkah ini dilewati."
                )
            else:
                self._print(
                    f"\n[info]🔍 Me-resolve [green]{len(results_dict)}[/green] subdomain ke alamat IP...[/info]"
                )
                ip_map = await resolve_domains_to_ips(set(results_dict.keys()))
                all_unique_ips: Set[str] = set()

                for sub, ips in ip_map.items():
                    if sub in results_dict:
                        results_dict[sub]["ips"] = [{"address": ip} for ip in ips]
                        all_unique_ips.update(ips)

                if self.config.asn_lookup and all_unique_ips:
                    asn_map = await lookup_ips_asn(all_unique_ips)
                    for sub_details in results_dict.values():
                        if "ips" in sub_details:
                            for ip_info in sub_details["ips"]:
                                ip_addr = ip_info["address"]
                                if ip_addr in asn_map:
                                    ip_info["asn_info"] = asn_map[ip_addr]

        return {"subdomains": results_dict, "contributions": source_contributions}
