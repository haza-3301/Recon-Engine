"""Base classes and typed contracts for Recon-Engine plugins."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Set


class BasePlugin(ABC):
    """Shared plugin contract."""

    name: str

    @abstractmethod
    def __init__(self) -> None:
        raise NotImplementedError


class BaseAPIPlugin(BasePlugin):
    """HTTP API source — implement ``url`` and ``parse``."""

    url: str
    is_json: bool = True
    api_key_env: Optional[str] = None

    @abstractmethod
    def parse(self, data: Any) -> Set[str]:
        """Parse API response into a set of subdomain strings."""

    def auth_headers(self) -> dict[str, str]:
        """Optional Bearer token from env or instance attribute."""
        if self.api_key_env:
            api_key = os.getenv(self.api_key_env)
            if api_key:
                return {"Authorization": f"Bearer {api_key}"}
        api_key = getattr(self, "api_key", None)
        if api_key:
            return {"Authorization": api_key}
        return {}


class BaseToolPlugin(BasePlugin):
    """External CLI tool — implement ``get_command``."""

    @abstractmethod
    def get_command(self, domain: str) -> List[str]:
        """Return argv list for subprocess (no shell=True)."""

    @property
    def binary_name(self) -> str:
        """First token of ``name`` — used for PATH lookup."""
        return self.name.split()[0]
