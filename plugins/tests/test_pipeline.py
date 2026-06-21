"""Tests for httpx output sanitization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.pipeline import clean_hostname, sanitize_httpx_output


def test_sanitize_full_drops_failed():
    lines = [
        "http://alive.example.com [SUCCESS] [200] [] [100] [OK] [1.2.3.4] []",
        "http://dead.example.com [FAILED]",
    ]
    out = sanitize_httpx_output(lines, enum_only=False)
    assert len(out) == 1
    assert "[SUCCESS]" in out[0]
    assert "[FAILED]" not in out[0]


def test_sanitize_enum_only_hostnames():
    lines = [
        "https://api.example.com/path",
        "http://dead.example.com [FAILED]",
    ]
    out = sanitize_httpx_output(lines, enum_only=True)
    assert out == ["api.example.com"]


def test_clean_hostname_from_url():
    assert clean_hostname("https://api.example.com/path") == "api.example.com"
