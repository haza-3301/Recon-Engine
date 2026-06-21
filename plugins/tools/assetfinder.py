from typing import List

from core.base_plugin import BaseToolPlugin


class Plugin(BaseToolPlugin):
    """tomnomnom assetfinder."""

    def __init__(self):
        self.name = "assetfinder"

    def get_command(self, domain: str) -> List[str]:
        return ["assetfinder", "--subs-only", domain]
