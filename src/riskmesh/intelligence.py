"""Consent-based ingestion of public threat indicator feeds.

Never crawls competitors, authenticated systems, private customer records or
unapproved URLs. The caller configures an explicit HTTPS hostname allowlist.
"""
from __future__ import annotations

import ipaddress
import json
import os
import urllib.parse
import urllib.request


def normalize_indicators(document: dict) -> dict:
    """Accept a small, bounded JSON IOC document with IP and domain indicators."""
    raw = document.get("indicators", [])
    if not isinstance(raw, list) or len(raw) > 5000:
        raise ValueError("Indicator feed exceeds limit")
    ips: set[str] = set()
    domains: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        kind, value = item.get("type"), item.get("value")
        if not isinstance(value, str) or len(value) > 253:
            continue
        if kind == "ip":
            try:
                ips.add(str(ipaddress.ip_address(value)))
            except ValueError:
                continue
        elif kind == "domain":
            value = value.lower().rstrip(".")
            labels = value.split(".")
            if len(labels) >= 2 and all(
                label and len(label) <= 63 and label.replace("-", "").isalnum()
                and not label.startswith("-") and not label.endswith("-")
                for label in labels
            ):
                domains.add(value)
    return {"ips": sorted(ips), "domains": sorted(domains)}


def fetch_public_feed(url: str, *, max_bytes: int = 1_000_000) -> dict:
    """Fetch a preapproved public JSON feed; redirects and proxies are disabled.

    For production, use a hardened egress proxy with DNS rebinding protection.
    """
    allowed = {host.strip().lower() for host in os.getenv("RISK_MESH_FEED_HOSTS", "").split(",") if host.strip()}
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise ValueError("Feed URL is not explicitly approved")
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ValueError("Redirects are disabled for feed ingestion")
    opener = urllib.request.build_opener(
        NoRedirect(),
        urllib.request.ProxyHandler({}),
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "Quantivex-RiskMesh-DefensiveFeed/1.0", "Accept": "application/json"}
    )
    with opener.open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("Feed returned unexpected HTTP status")
        if int(response.headers.get("Content-Length", "0")) > max_bytes:
            raise ValueError("Feed response too large")
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError("Feed response too large")
    return normalize_indicators(json.loads(payload))
