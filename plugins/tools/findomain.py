import shutil
from typing import List

from core.base_plugin import BaseToolPlugin


class Plugin(BaseToolPlugin):
    """Findomain passive subdomain discovery."""

    def __init__(self):
        self.name = "findomain"

    def get_command(self, domain: str) -> List[str]:
        base_command = ["findomain", "-t", domain, "-q"]
        if shutil.which("stdbuf"):
            return ["stdbuf", "-o0"] + base_command
        return base_command
