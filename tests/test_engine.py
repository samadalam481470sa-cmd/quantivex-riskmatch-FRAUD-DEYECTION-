from datetime import datetime, timedelta, timezone

from riskmesh.engine import exposure_score, score_transaction
from riskmesh.models import Transaction


def tx(identifier, sender="A", receiver="B", amount=100, minute=0, device="d1", country="US"):
    return Transaction(
        transaction_id=identifier,
        timestamp=datetime(2026, 1, 1, 12, tzinfo=timezone.utc) + timedelta(minutes=minute),
        tenant_id="tenantA",
        sender_account=sender,
        receiver_account=receiver,
        amount=amount,
        currency="USD",
        device_id=device,
        source_ip="192.0.2.10",
        country=country,
        channel="web",
    )


def test_amount_velocity_device_and_country_signals():
    history = [
        tx("a1", amount=100, minute=0),
        tx("a2", amount=110, minute=1),
        tx("a3", amount=95, minute=2),
        tx("a4", amount=105, minute=3),
    ]
    current = tx("risk", amount=10000, minute=4, device="new-device", country="GB")
    result = score_transaction(current, history)
    codes = {signal.code for signal in result.signals}
    assert {"AMOUNT_OUTLIER", "HIGH_VELOCITY", "NEW_DEVICE", "COUNTRY_SHIFT"} <= codes
    assert result.decision in {"review", "block"}


def test_short_cycle_detection():
    history = [
        tx("x1", sender="A", receiver="B"),
        tx("x2", sender="B", receiver="C"),
        tx("x3", sender="C", receiver="D"),
    ]
    current = tx("cycle", sender="D", receiver="A")
    result = score_transaction(current, history)
    assert "CIRCULAR_MONEY_FLOW" in {signal.code for signal in result.signals}


def test_network_exposure():
    data = [tx("1", "A", "B", 1000), tx("2", "C", "A", 2000), tx("3", "A", "D", 3000)]
    result = exposure_score(data, "A")
    assert result["counterparties"] == 3
    assert result["gross_flow"] == 6000
