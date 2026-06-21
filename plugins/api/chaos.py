import logging
import os
from typing import Any, Set

from core.base_plugin import BaseAPIPlugin


class Plugin(BaseAPIPlugin):
    """ProjectDiscovery Chaos dataset — requires CHAOS_KEY env var."""

    def __init__(self):
        self.name = "Chaos"
        self.url = "https://dns.projectdiscovery.io/dns/{domain}/subdomains"
        self.api_key = os.getenv("CHAOS_KEY")
        self.enabled = bool(self.api_key)
        if not self.enabled:
            logging.debug(f"[{self.name}] CHAOS_KEY tidak diset — plugin dinonaktifkan.")

    def parse(self, data: Any) -> Set[str]:
        if not self.api_key:
            logging.warning(f"[{self.name}] Kunci API 'CHAOS_KEY' tidak diatur, plugin dilewati.")
            return set()

        if not isinstance(data, dict) or "subdomains" not in data:
            logging.warning(f"[{self.name}] Respons API tidak valid, parsing dibatalkan.")
            return set()

        return {f"{sub}.{data.get('domain')}" for sub in data.get("subdomains", [])}
