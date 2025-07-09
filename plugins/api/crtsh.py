# plugins/api/crtsh.py
import logging


class Plugin:
    """Plugin untuk mengambil data subdomain dari crt.sh."""

    def __init__(self):
        self.name = "crt.sh"
        self.url = "https://crt.sh/?q=%.{domain}&output=json"

    def parse(self, data):
        """Parser khusus untuk output JSON dari crt.sh."""
        if not isinstance(data, list):
            logging.warning(
                f"[{self.name}] Respons API bukan list, parsing dibatalkan."
            )
            return set()

        subdomains = set()
        for entry in data:
            if "name_value" in entry:
                subdomains.update(
                    name.strip()
                    for name in entry["name_value"].split("\n")
                    if name.strip()
                )
        return subdomains
