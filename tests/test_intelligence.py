import pytest

from riskmesh.intelligence import fetch_public_feed, normalize_indicators


def test_indicator_normalization():
    result = normalize_indicators({"indicators": [
        {"type": "ip", "value": "203.0.113.10"},
        {"type": "domain", "value": "EXAMPLE.org."},
        {"type": "ip", "value": "not-an-ip"},
    ]})
    assert result == {"ips": ["203.0.113.10"], "domains": ["example.org"]}


def test_unapproved_urls_never_fetched(monkeypatch):
    monkeypatch.setenv("RISK_MESH_FEED_HOSTS", "feeds.example.org")
    for url in (
        "http://feeds.example.org/data",
        "https://127.0.0.1/data",
        "https://feeds.example.org.evil.test/data",
        "https://user:pass@feeds.example.org/data",
    ):
        with pytest.raises(ValueError):
            fetch_public_feed(url)
