# plugins/tools/findomain.py
import shutil


class Plugin:
    """Plugin untuk tool findomain."""

    def __init__(self):
        self.name = "findomain"

    def get_command(self, domain):
        base_command = ["findomain", "-t", domain, "-q"]
        # Gunakan stdbuf jika tersedia untuk unbuffered output
        if shutil.which("stdbuf"):
            return ["stdbuf", "-o0"] + base_command
        return base_command
