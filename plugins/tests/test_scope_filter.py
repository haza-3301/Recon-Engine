"""Tests for in-scope subdomain filtering."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.scope_filter import filter_in_scope, scope_regex


ROOT = "padang.go.id"


def test_scope_accepts_valid_subdomains():
    hosts = [
        "api.padang.go.id",
        "www.padang.go.id",
        "antrian.dpmptsp.padang.go.id",
    ]
    result = filter_in_scope(hosts, ROOT)
    assert result == sorted(hosts)


def test_scope_rejects_out_of_scope():
    hosts = [
        "arsip.anonim.id",
        "evil.com",
        "padang.go.id.evil.com",
    ]
    assert filter_in_scope(hosts, ROOT) == []


def test_scope_rejects_long_digit_runs():
    hosts = ["host123456.padang.go.id", "ok.padang.go.id"]
    assert filter_in_scope(hosts, ROOT) == ["ok.padang.go.id"]


def test_scope_rejects_long_hostnames():
    long_host = ("a" * 50) + ".padang.go.id"
    assert filter_in_scope([long_host], ROOT, max_length=60) == []


def test_scope_dedup_and_sort():
    hosts = ["b.padang.go.id", "a.padang.go.id", "b.padang.go.id"]
    assert filter_in_scope(hosts, ROOT) == ["a.padang.go.id", "b.padang.go.id"]


def test_scope_regex_matches_manual_grep_pattern():
    pattern = scope_regex("example.co.id")
    assert pattern.match("sub.example.co.id")
    assert not pattern.match("-bad.example.co.id")
