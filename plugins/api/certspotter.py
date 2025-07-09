import logging
from typing import Set, List, Dict, Any

class Plugin:
    """Plugin untuk mengambil data subdomain dari CertSpotter."""

    def __init__(self):
        """Inisialisasi plugin."""
        self.name = "CertSpotter"
        self.url = "https://api.certspotter.com/v1/issuances?domain={domain}&include_subdomains=true&expand=dns_names"

    def parse(self, data: Any) -> Set[str]:
        """Parser khusus untuk output JSON dari CertSpotter.
        
        Args:
            data: Data JSON yang diterima dari API, diharapkan berupa list.

        Returns:
            Satu set subdomain yang unik.
        """
        if not isinstance(data, list):
            logging.warning(
                f"[{self.name}] Respons API bukan list, parsing dibatalkan."
            )
            return set()

        subdomains = set()
        for issuance in data:
            if "dns_names" in issuance and isinstance(issuance["dns_names"], list):
                subdomains.update(issuance["dns_names"])
        return subdomains