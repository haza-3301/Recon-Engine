import logging
from typing import Any, Set

from core.base_plugin import BaseAPIPlugin


class Plugin(BaseAPIPlugin):
    """AlienVault OTX passive DNS."""

    def __init__(self):
        self.name = "AlienVault OTX"
        self.url = "https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"

    def parse(self, data: Any) -> Set[str]:
        if not isinstance(data, dict):
            logging.warning(f"[{self.name}] Respons API bukan dict, parsing dibatalkan.")
            return set()

        subdomains: Set[str] = set()
        if "passive_dns" in data and isinstance(data["passive_dns"], list):
            for record in data["passive_dns"]:
                if record.get("hostname"):
                    subdomains.add(record["hostname"])
        return subdomains
