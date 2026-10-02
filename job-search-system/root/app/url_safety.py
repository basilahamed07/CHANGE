"""URL safety guard — block SSRF-shaped fetches.

The server must never fetch a URL the *caller* chose unless it resolves to a
public host. This blocks the classic SSRF targets: cloud metadata
(``169.254.169.254``), loopback, RFC1918 private ranges, link-local and
reserved/multicast space — for IPv4 and IPv6, at the URL and on every redirect
hop.

Golden Rule: deterministic, stdlib-only, no LLM.

Known limit: a guard-then-fetch is a TOCTOU race (DNS rebinding could return a
public IP to us and a private one to the socket). Mitigating that fully needs
connecting to the validated IP directly; the guard here removes the realistic
attack surface (a caller naming an internal URL) and re-checks each redirect.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")
_REDIRECT_CODES = (301, 302, 303, 307, 308)

# Ranges `ipaddress.is_private` does not cover on every Python version.
_EXTRA_BLOCKED_NETS = (
    ipaddress.ip_network("100.64.0.0/10"),   # RFC 6598 carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),    # RFC 6890 IETF protocol assignments
    ipaddress.ip_network("198.18.0.0/15"),   # RFC 2544 benchmarking
)


def _ip_is_public(ip: str) -> bool:
    """False for anything that isn't a routable public unicast address."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    # ::ffff:127.0.0.1 — unwrap IPv4-mapped IPv6 and re-check the IPv4 form.
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        return _ip_is_public(str(mapped))
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        return False
    return not any(addr in net for net in _EXTRA_BLOCKED_NETS if addr.version == net.version)


def resolve_host(hostname: str) -> list[str]:
    """Every IP a hostname resolves to, or [] if resolution fails."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError, OSError):
        return []
    ips: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr and sockaddr[0] not in ips:
            ips.append(sockaddr[0])
    return ips


def is_safe_public_url(url: str) -> bool:
    """True only for an http(s) URL whose host resolves solely to public IPs."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False
    host = parsed.hostname  # lowercased, IPv6 brackets already stripped
    if not host:
        return False
    # A literal IP needs no DNS.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        ips = resolve_host(host)
        if not ips:
            return False
        return all(_ip_is_public(ip) for ip in ips)
    return _ip_is_public(host)


def assert_safe_url(url: str) -> str:
    """Return the url, or raise ValueError if it is not a safe public target."""
    if not is_safe_public_url(url):
        raise ValueError(f"unsafe or unresolvable URL: {url!r}")
    return url


async def safe_get(client, url: str, *, max_hops: int = 3, **kwargs):
    """GET that validates the URL and every redirect hop before fetching.

    Uses ``follow_redirects=False`` on the underlying client and walks the
    Location chain itself, so a public URL cannot 302 the server into the
    private network. Raises ValueError if any hop is unsafe.
    """
    import httpx

    current = url
    for _ in range(max_hops + 1):
        if not is_safe_public_url(current):
            raise ValueError(f"unsafe or unresolvable URL: {current!r}")
        resp = await client.get(current, follow_redirects=False, **kwargs)
        if resp.status_code not in _REDIRECT_CODES:
            return resp
        location = resp.headers.get("location")
        if not location:
            return resp
        current = str(httpx.URL(current).join(location))
    raise ValueError(f"too many redirects (> {max_hops})")
