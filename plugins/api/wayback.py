# plugins/api/wayback.py
import logging
from urllib.parse import urlparse


class Plugin:
    """Plugin untuk mengambil data subdomain dari Wayback Machine."""

    def __init__(self):
        self.name = "WaybackMachine"
        self.url = "https://web.archive.org/cdx/search/cdx?url=*.{domain}&output=json&fl=original&collapse=urlkey"

    def parse(self, data):
        """Parser khusus untuk output JSON dari Wayback Machine."""
        if not isinstance(data, list):
            logging.warning(
                f"[{self.name}] Respons API bukan list, parsing dibatalkan."
            )
            return set()

        subdomains = set()
        urls = {item[0] for item in data if isinstance(item, list) and item}
        for u in urls:
            try:
                parsed_hostname = urlparse(u).hostname
                if parsed_hostname:
                    subdomains.add(parsed_hostname)
            except Exception:
                continue
        return subdomains
