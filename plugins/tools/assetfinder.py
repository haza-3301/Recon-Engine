# plugins/tools/assetfinder.py
class Plugin:
    """Plugin untuk tool assetfinder."""

    def __init__(self):
        self.name = "assetfinder"
        # Assetfinder tidak menggunakan flag output, ia langsung print ke stdout.
        # Biarkan output_flag tidak ada.

    def get_command(self, domain):
        return ["assetfinder", "--subs-only", domain]
