from datetime import datetime, timedelta, timezone

from riskmesh.models import Transaction
from riskmesh.temporal import combine_risk, investigate


BASE = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)


def tx(id, sender, receiver, minute, amount=1000, tenant="alpha"):
    return Transaction(
        transaction_id=id, timestamp=BASE + timedelta(minutes=minute),
        tenant_id=tenant, sender_account=sender, receiver_account=receiver,
        amount=amount, currency="USD", device_id="d1",
        source_ip="192.0.2.1", country="US", channel="api",
    )


def test_time_respecting_cycle():
    history = [tx("a", "A", "B", 0), tx("b", "B", "C", 2)]
    findings = investigate(tx("c", "C", "A", 3), history)
    assert findings[0].code == "TEMPORAL_CIRCULAR_FLOW"
    assert findings[0].transaction_ids == ("a", "b", "c")


def test_reversed_timestamps_do_not_form_cycle():
    history = [tx("a", "A", "B", 2), tx("b", "B", "C", 1)]
    assert not any(
        item.code == "TEMPORAL_CIRCULAR_FLOW"
        for item in investigate(tx("c", "C", "A", 3), history)
    )


def test_tenant_isolation():
    history = [tx("a", "A", "B", 0, tenant="beta"), tx("b", "B", "C", 1)]
    assert investigate(tx("c", "C", "A", 2), history) == []


def test_aggregation_layering():
    history = [
        tx("a", "A", "X", 0, 100),
        tx("b", "B", "X", 1, 100),
        tx("c", "C", "X", 2, 100),
    ]
    findings = investigate(tx("d", "X", "Z", 3, 280), history)
    assert "AGGREGATION_LAYERING" in {item.code for item in findings}


def test_risk_fusion_is_bounded():
    assert combine_risk(100, []) == 100
    assert combine_risk(0, []) == 0
