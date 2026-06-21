import logging
from typing import Any, Set

from core.base_plugin import BaseAPIPlugin


class Plugin(BaseAPIPlugin):
    """HackerTarget host search API (plain text response)."""

    def __init__(self):
        self.name = "HackerTarget"
        self.url = "https://api.hackertarget.com/hostsearch/?q={domain}"
        self.is_json = False

    def parse(self, data: Any) -> Set[str]:
        if not isinstance(data, str):
            logging.warning(f"[{self.name}] Respons API bukan string, parsing dibatalkan.")
            return set()

        subdomains: Set[str] = set()
        for line in data.splitlines():
            if line.strip():
                subdomains.add(line.split(",")[0])
        return subdomains
