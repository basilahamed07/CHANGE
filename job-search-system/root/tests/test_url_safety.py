"""SSRF guard tests — `app/url_safety.py`.

Deterministic, stdlib-only. No network: literal IPs are checked directly and
the DNS path is exercised with a monkeypatched resolver.
"""

from __future__ import annotations

import pytest

from app import url_safety
from app.url_safety import assert_safe_url, is_safe_public_url


# --------------------------------------------------------------- blocked hosts

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://127.0.0.1:8085/api/health",
    "http://localhost/",                      # resolves to loopback
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://10.0.0.5/",
    "http://172.16.4.4/",
    "http://192.168.1.1/",
    "http://0.0.0.0/",
    "http://100.64.0.1/",                     # carrier-grade NAT / shared space
    "http://[::1]/",                          # IPv6 loopback
    "http://[fe80::1]/",                      # IPv6 link-local
    "http://[::ffff:127.0.0.1]/",             # IPv4-mapped IPv6 loopback
    "http://[fd00::1]/",                      # IPv6 unique-local
])
def test_private_and_special_hosts_are_blocked(url):
    assert is_safe_public_url(url) is False


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/x",
    "javascript:alert(1)",
    "gopher://example.com/",
    "",
    "not a url",
    "http://",                                # no host
])
def test_bad_schemes_and_malformed_urls_are_blocked(url):
    assert is_safe_public_url(url) is False


# ------------------------------------------------------------ allowed targets

def test_public_ip_literal_is_allowed():
    assert is_safe_public_url("http://93.184.216.34/") is True
    assert is_safe_public_url("https://1.1.1.1/dns-query") is True


def test_public_hostname_is_allowed(monkeypatch):
    monkeypatch.setattr(url_safety, "resolve_host", lambda host: ["93.184.216.34"])
    assert is_safe_public_url("https://example.com/careers") is True


def test_hostname_resolving_to_a_private_ip_is_blocked(monkeypatch):
    """DNS that points a nice name at an internal address must still be refused."""
    monkeypatch.setattr(url_safety, "resolve_host", lambda host: ["10.1.2.3"])
    assert is_safe_public_url("https://internal.example.com/") is False


def test_hostname_with_any_private_address_is_blocked(monkeypatch):
    """One bad address among several is enough to refuse."""
    monkeypatch.setattr(url_safety, "resolve_host",
                        lambda host: ["93.184.216.34", "192.168.0.9"])
    assert is_safe_public_url("https://mixed.example.com/") is False


def test_unresolvable_hostname_is_blocked(monkeypatch):
    monkeypatch.setattr(url_safety, "resolve_host", lambda host: [])
    assert is_safe_public_url("https://does-not-resolve.invalid/") is False


def test_assert_safe_url_raises_on_internal_target():
    with pytest.raises(ValueError):
        assert_safe_url("http://169.254.169.254/")
    # A public IP literal — no DNS needed.
    assert assert_safe_url("https://1.1.1.1/") == "https://1.1.1.1/"


# ------------------------------------------------------- redirect-hop guarding

class _Resp:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"location": location} if location else {}


class _FakeClient:
    """Returns queued responses and records the URLs actually fetched."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.fetched: list[str] = []

    async def get(self, url, follow_redirects=False, **kwargs):
        self.fetched.append(url)
        return self._responses.pop(0)


async def test_safe_get_follows_public_redirect():
    client = _FakeClient([_Resp(302, "https://example.com/final"), _Resp(200)])
    resp = await url_safety.safe_get(client, "https://example.com/start")
    assert resp.status_code == 200
    assert client.fetched == ["https://example.com/start", "https://example.com/final"]


async def test_safe_get_refuses_redirect_into_private_network():
    """The classic SSRF bypass: a public URL that 302s to the metadata service."""
    client = _FakeClient([_Resp(302, "http://169.254.169.254/latest/meta-data/")])
    with pytest.raises(ValueError):
        await url_safety.safe_get(client, "https://example.com/innocent")
    assert client.fetched == ["https://example.com/innocent"]  # never followed


async def test_safe_get_rejects_unsafe_initial_url():
    client = _FakeClient([_Resp(200)])
    with pytest.raises(ValueError):
        await url_safety.safe_get(client, "http://127.0.0.1:8085/")
    assert client.fetched == []


async def test_safe_get_stops_after_max_hops():
    loop = [_Resp(302, "https://example.com/next") for _ in range(10)]
    client = _FakeClient(loop)
    with pytest.raises(ValueError):
        await url_safety.safe_get(client, "https://example.com/start", max_hops=3)
