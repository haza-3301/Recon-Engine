import logging
from typing import Set, Dict, Any

class Plugin:
    """Plugin untuk mengambil data subdomain dari AlienVault OTX."""

    def __init__(self):
        """Inisialisasi plugin."""
        self.name = "AlienVault OTX"
        self.url = "https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"

    def parse(self, data: Any) -> Set[str]:
        """Parser khusus untuk output JSON dari AlienVault OTX.
        
        Args:
            data: Data JSON yang diterima dari API, diharapkan berupa dict.

        Returns:
            Satu set subdomain yang unik.
        """
        if not isinstance(data, dict):
            logging.warning(
                f"[{self.name}] Respons API bukan dict, parsing dibatalkan."
            )
            return set()

        subdomains = set()
        if "passive_dns" in data and isinstance(data["passive_dns"], list):
            for record in data["passive_dns"]:
                if record.get("hostname"):
                    subdomains.add(record["hostname"])
        return subdomains