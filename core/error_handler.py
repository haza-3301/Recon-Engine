# core/error_handler.py
import logging
from typing import Any

class PluginError(Exception):
    """Exception dasar untuk semua error terkait plugin."""
    pass

class APIError(PluginError):
    """Exception spesifik untuk kegagalan API."""
    pass

def handle_plugin_exception(plugin_name: str, exception: Exception):
    """
    Menangani dan mencatat error umum yang terjadi saat eksekusi plugin.
    """
    logging.error(f"[PLUGIN] Task '{plugin_name}' gagal: {exception}", exc_info=False)

def handle_timeout(plugin_name: str, timeout_duration: float):
    """
    Mencatat pesan warning ketika sebuah task mengalami timeout.
    """
    logging.warning(f"[SYSTEM] Task '{plugin_name}' timeout setelah {timeout_duration} detik.")

def handle_http_error(plugin_name: str, url: str, attempt: int, max_retries: int, exception: Exception):
    """
    Menangani error terkait HTTP dari plugin API, termasuk logika retry.
    """
    if attempt < max_retries - 1:
        # Pesan ini hanya akan muncul di mode --debug, jadi tidak berisik
        logging.debug(f"[API] Percobaan {attempt + 1}/{max_retries} untuk '{plugin_name}' gagal, mencoba lagi...")
    else:
        # Error final setelah semua percobaan gagal
        logging.error(f"[API] Task '{plugin_name}' gagal setelah {max_retries} percobaan: {exception}")