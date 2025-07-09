import logging
import os
from typing import Set, Dict, Any

class Plugin:
    """Plugin untuk mengambil data subdomain dari Chaos Dataset.
    
    CATATAN: API ini memerlukan kunci API yang diatur sebagai environment variable 'CHAOS_KEY'.
    Selain itu, fungsi `query_api_task` di skrip utama perlu diubah untuk mengirimkan
    header 'Authorization'.
    """

    def __init__(self):
        """Inisialisasi plugin."""
        self.name = "Chaos"
        self.url = "https://dns.projectdiscovery.io/dns/{domain}/subdomains"
        # Kunci API harus ditambahkan ke header request di 'reconV1.py'
        self.api_key = os.getenv("CHAOS_KEY") 

    def parse(self, data: Any) -> Set[str]:
        """Parser khusus untuk output JSON dari Chaos.
        
        Args:
            data: Data JSON yang diterima dari API, diharapkan berupa dict.

        Returns:
            Satu set subdomain yang unik.
        """
        if not self.api_key:
            logging.warning(f"[{self.name}] Kunci API 'CHAOS_KEY' tidak diatur, plugin dilewati.")
            return set()
            
        if not isinstance(data, dict) or "subdomains" not in data:
            logging.warning(
                f"[{self.name}] Respons API tidak valid atau tidak berisi 'subdomains', parsing dibatalkan."
            )
            return set()

        subdomains = {f"{sub}.{data.get('domain')}" for sub in data.get("subdomains", [])}
        return subdomains