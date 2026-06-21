"""Result cache with integrity checksum and file locking."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    from filelock import FileLock, Timeout

    FILELOCK_AVAILABLE = True
except ImportError:
    FILELOCK_AVAILABLE = False

    class Timeout(Exception):
        pass

    class FileLock:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass


class CacheManager:
    """JSON cache keyed by domain + active plugin fingerprint."""

    def __init__(self, version: str, cache_dir: Optional[Path], enabled: bool = True):
        self.version = version
        self.cache_dir = cache_dir
        self.enabled = enabled and cache_dir is not None and FILELOCK_AVAILABLE
        if cache_dir and not FILELOCK_AVAILABLE:
            logging.warning("[CACHE] Cache dinonaktifkan karena 'filelock' tidak ada.")

    def _fingerprint(
        self,
        tool_plugins: Dict[str, Any],
        api_plugins: Dict[str, Any],
        wayback: bool,
        resolve_ip: bool,
        asn_lookup: bool,
    ) -> str:
        sorted_keys = sorted(list(api_plugins.keys()) + list(tool_plugins.keys()))
        parts = [
            self.version,
            *sorted_keys,
            "wayback-on" if wayback else "wayback-off",
            "resolve-on" if resolve_ip else "resolve-off",
            "asn-on" if asn_lookup else "asn-off",
        ]
        return hashlib.md5("".join(parts).encode()).hexdigest()[:8]

    def paths_for(
        self,
        domain: str,
        tool_plugins: Dict[str, Any],
        api_plugins: Dict[str, Any],
        wayback: bool,
        resolve_ip: bool,
        asn_lookup: bool,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        if not self.enabled or not self.cache_dir:
            return None, None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fp = self._fingerprint(tool_plugins, api_plugins, wayback, resolve_ip, asn_lookup)
        cache_file = self.cache_dir / f"{domain}-{fp}.json"
        lock_file = self.cache_dir / f"{domain}-{fp}.lock"
        return cache_file, lock_file

    def read(self, cache_file: Path) -> Optional[Dict[str, Any]]:
        try:
            with FileLock(cache_file.with_suffix(".lock"), timeout=1):
                if not cache_file.exists():
                    return None
                cache_content = json.loads(cache_file.read_text("utf-8"))
                data_str = json.dumps(cache_content["data"], sort_keys=True)
                if hashlib.sha256(data_str.encode()).hexdigest() != cache_content["checksum"]:
                    logging.warning("[CACHE] Checksum tidak cocok — cache diabaikan.")
                    return None
                return cache_content["data"]
        except Timeout:
            logging.warning("[CACHE] Gagal mendapatkan lock untuk membaca cache.")
        except (json.JSONDecodeError, KeyError):
            logging.warning("[CACHE] Cache tidak bisa dibaca.")
        return None

    def write(self, cache_file: Path, results: Dict[str, Any]) -> None:
        lock_file = cache_file.with_suffix(".lock")
        try:
            with FileLock(lock_file, timeout=1):
                data_str = json.dumps(results, sort_keys=True)
                checksum = hashlib.sha256(data_str.encode()).hexdigest()
                payload = {"data": results, "checksum": checksum}
                tmp_cache = cache_file.with_suffix(".tmp")
                tmp_cache.write_text(json.dumps(payload), encoding="utf-8")
                tmp_cache.rename(cache_file)
        except Timeout:
            logging.warning("[CACHE] Gagal mendapatkan lock untuk menulis cache.")
