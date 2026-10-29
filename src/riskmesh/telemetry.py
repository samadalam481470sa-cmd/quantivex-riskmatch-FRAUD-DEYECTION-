"""Low-cardinality, non-PII HTTP counters for defensive monitoring."""
from __future__ import annotations

import threading
from collections import Counter

from fastapi.responses import PlainTextResponse

_lock = threading.Lock()
_counts: Counter[tuple[str, str]] = Counter()
_ALLOWED = {"/health", "/", "/api/v1/score", "/api/v1/batch",
            "/api/v1/decisions", "/api/v1/ml/score",
            "/api/v1/advanced/investigate", "/api/v1/advanced/verify"}


def record(path: str, status: int) -> None:
    # Never include account numbers, tenant IDs, user identities, or arbitrary URLs.
    route = path if path in _ALLOWED else "other"
    group = f"{status // 100}xx"
    with _lock:
        _counts[(route, group)] += 1


def metrics_response() -> PlainTextResponse:
    with _lock:
        counts = sorted(_counts.items())
    lines = ["# TYPE riskmesh_http_requests_total counter"]
    for (route, status), count in counts:
        lines.append(
            f'riskmesh_http_requests_total{{route="{route}",status_class="{status}"}} {count}'
        )
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
