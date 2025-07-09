import logging
from typing import Set, Any

class Plugin:
    """Plugin untuk mengambil data subdomain dari HackerTarget.
    
    CATATAN: API ini mengembalikan plain text, bukan JSON. Fungsi `query_api_task`
    di skrip utama perlu diubah agar memanggil `response.text` bukan `response.json()`
    dan meneruskannya ke fungsi parse ini.
    """

    def __init__(self):
        """Inisialisasi plugin."""
        self.name = "HackerTarget"
        self.url = "https://api.hackertarget.com/hostsearch/?q={domain}"
        self.is_json = False # Properti kustom untuk menandakan tipe data

    def parse(self, data: Any) -> Set[str]:
        """Parser khusus untuk output plain text dari HackerTarget.
        
        Args:
            data: Data mentah berupa string yang diterima dari API.

        Returns:
            Satu set subdomain yang unik.
        """
        if not isinstance(data, str):
            logging.warning(f"[{self.name}] Respons API bukan string, parsing dibatalkan.")
            return set()

        subdomains = set()
        for line in data.splitlines():
            if line.strip():
                # Formatnya adalah "subdomain.domain,ip_address"
                subdomain = line.split(',')[0]
                subdomains.add(subdomain)
        return subdomains