from typing import List

from core.base_plugin import BaseToolPlugin


class Plugin(BaseToolPlugin):
    """ProjectDiscovery subfinder."""

    def __init__(self):
        self.name = "subfinder"

    def get_command(self, domain: str) -> List[str]:
        return ["subfinder", "-d", domain, "-silent"]
