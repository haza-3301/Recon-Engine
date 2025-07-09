# plugins/tools/subfinder.py
class Plugin:
    """Plugin untuk tool subfinder."""

    def __init__(self):
        self.name = "subfinder"
        self.output_flag = "-o"  # Subfinder menggunakan flag output

    def get_command(self, domain):
        return ["subfinder", "-d", domain, "-silent"]
