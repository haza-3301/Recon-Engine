import logging
from typing import Any, Set

from core.base_plugin import BaseAPIPlugin


class Plugin(BaseAPIPlugin):
    """Certificate transparency via crt.sh."""

    def __init__(self):
        self.name = "crt.sh"
        self.url = "https://crt.sh/?q=%.{domain}&output=json"

    def parse(self, data: Any) -> Set[str]:
        if not isinstance(data, list):
            logging.warning(f"[{self.name}] Respons API bukan list, parsing dibatalkan.")
            return set()

        subdomains: Set[str] = set()
        for entry in data:
            if "name_value" in entry:
                subdomains.update(
                    name.strip() for name in entry["name_value"].split("\n") if name.strip()
                )
        return subdomains
