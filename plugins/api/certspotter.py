import logging
from typing import Any, Set

from core.base_plugin import BaseAPIPlugin


class Plugin(BaseAPIPlugin):
    """CertSpotter certificate issuance API."""

    def __init__(self):
        self.name = "CertSpotter"
        self.url = (
            "https://api.certspotter.com/v1/issuances"
            "?domain={domain}&include_subdomains=true&expand=dns_names"
        )

    def parse(self, data: Any) -> Set[str]:
        if not isinstance(data, list):
            logging.warning(f"[{self.name}] Respons API bukan list, parsing dibatalkan.")
            return set()

        subdomains: Set[str] = set()
        for issuance in data:
            if "dns_names" in issuance and isinstance(issuance["dns_names"], list):
                subdomains.update(issuance["dns_names"])
        return subdomains
