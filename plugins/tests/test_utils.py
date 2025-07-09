# tests/test_utils.py
import sys
import os
import pytest

# Tambahkan direktori utama (root) ke path agar bisa mengimpor dari recon_engine
# Asumsi struktur: /lab/recon_engine_v6.py dan /lab/tests/test_utils.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Impor fungsi dari nama file yang benar: recon_engine_v6
from recon_engine_v6 import is_valid_domain, normalize_subdomain

# === Test untuk fungsi is_valid_domain ===

def test_is_valid_domain_success():
    """Menguji domain yang seharusnya valid, termasuk IDN."""
    assert is_valid_domain("google.com")
    assert is_valid_domain("sub.domain.co.id")
    assert is_valid_domain("a-b.com")
    assert is_valid_domain("example-123.net")
    # Menambahkan test untuk domain internasional (Punycode)
    assert is_valid_domain("пример.рф")
    assert is_valid_domain("xn--e1afmkfd.xn--p1ai") # Bentuk Punycode dari пример.рф
    assert is_valid_domain("very-long-label-that-is-still-valid-and-not-over-63-chars.com")

def test_is_valid_domain_failure():
    """Menguji domain yang seharusnya TIDAK valid."""
    assert not is_valid_domain("-invalid.com")
    assert not is_valid_domain("invalid-.com")
    assert not is_valid_domain("no_underscore.com")
    assert not is_valid_domain("domain.c")  # TLD minimal 2 karakter
    assert not is_valid_domain(".startwithdot.com")
    assert not is_valid_domain("google..com") # Double dot
    assert not is_valid_domain("http://google.com") # Mengandung protokol
    assert not is_valid_domain("google.com/") # Mengandung path
    assert not is_valid_domain("a" * 64 + ".com") # Label terlalu panjang
    assert not is_valid_domain("") # String kosong
    assert not is_valid_domain("123.123.123.123") # IP address bukan domain
    assert not is_valid_domain("domain.123") # TLD tidak boleh angka

# === Test untuk fungsi normalize_subdomain ===

def test_normalize_subdomain():
    """Menguji normalisasi input subdomain."""
    assert normalize_subdomain("*.GOOGLE.com ") == "google.com"
    assert normalize_subdomain("  sub.Domain.ID") == "sub.domain.id"
    assert normalize_subdomain("test.com") == "test.com"
    assert normalize_subdomain("*.test.net") == "test.net"
    assert normalize_subdomain("  *.UPPER.case.com  ") == "upper.case.com"
    assert normalize_subdomain("no-wildcard.org") == "no-wildcard.org"