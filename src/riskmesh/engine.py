"""Explainable transaction scoring and bounded graph-risk analytics.

This prototype is for synthetic/demo data and analyst decision support only.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from math import log1p
from statistics import mean, pstdev

from riskmesh.models import RiskResult, RiskSignal, Transaction


def _amount_signal(transaction: Transaction, history: list[Transaction]) -> RiskSignal | None:
    prior = [
        item.amount
        for item in history
        if item.sender_account == transaction.sender_account
        and item.transaction_id != transaction.transaction_id
    ]
    if len(prior) < 3:
        if transaction.amount >= 50_000:
            return RiskSignal(
                code="HIGH_VALUE_NEW_PROFILE",
                weight=24.0,
                explanation="High-value payment with limited sender history",
            )
        return None
    baseline = mean(prior)
    deviation = pstdev(prior) or max(baseline * 0.05, 1.0)
    z_score = (transaction.amount - baseline) / deviation
    if z_score >= 5:
        return RiskSignal(
            code="AMOUNT_OUTLIER",
            weight=min(35.0, 20.0 + 2.5 * z_score),
            explanation=f"Amount is {z_score:.1f} standard deviations above sender history",
        )
    return None


def _velocity_signal(transaction: Transaction, history: list[Transaction]) -> RiskSignal | None:
    recent = [
        item
        for item in history
        if item.sender_account == transaction.sender_account
        and item.transaction_id != transaction.transaction_id
        and 0 <= (transaction.timestamp - item.timestamp).total_seconds() <= 600
    ]
    if len(recent) >= 4:
        return RiskSignal(
            code="HIGH_VELOCITY",
            weight=min(30.0, 12.0 + 3.0 * len(recent)),
            explanation=f"{len(recent)} prior outbound transactions occurred within ten minutes",
        )
    return None


def _device_signal(transaction: Transaction, history: list[Transaction]) -> RiskSignal | None:
    known = {
        item.device_id
        for item in history
        if item.sender_account == transaction.sender_account
        and item.transaction_id != transaction.transaction_id
    }
    if known and transaction.device_id not in known:
        return RiskSignal(
            code="NEW_DEVICE",
            weight=12.0,
            explanation="Sender is using a device not seen in prior transaction history",
        )
    return None


def _country_signal(transaction: Transaction, history: list[Transaction]) -> RiskSignal | None:
    countries = {
        item.country
        for item in history
        if item.sender_account == transaction.sender_account
        and item.transaction_id != transaction.transaction_id
    }
    if countries and transaction.country not in countries:
        return RiskSignal(
            code="COUNTRY_SHIFT",
            weight=15.0,
            explanation="Transaction originates from a country absent from sender history",
        )
    return None


def account_graph(transactions: list[Transaction]) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for transaction in transactions:
        graph[transaction.sender_account].add(transaction.receiver_account)
        graph.setdefault(transaction.receiver_account, set())
    return graph


def graph_signal(transaction: Transaction, history: list[Transaction]) -> tuple[RiskSignal | None, list[str]]:
    graph = account_graph(history)
    start = transaction.receiver_account
    target = transaction.sender_account
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        if len(path) > 5:
            continue
        for neighbor in graph.get(node, set()):
            if neighbor == target:
                cycle = path + [neighbor]
                return (
                    RiskSignal(
                        code="CIRCULAR_MONEY_FLOW",
                        weight=30.0,
                        explanation="Transaction closes a short directed money-flow cycle",
                    ),
                    cycle,
                )
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None, sorted(graph.get(transaction.receiver_account, set()))[:10]


def score_transaction(transaction: Transaction, history: list[Transaction]) -> RiskResult:
    if len(history) > 20_000:
        raise ValueError("History batch exceeds 20,000 transactions")
    signals: list[RiskSignal] = []
    for detector in (_amount_signal, _velocity_signal, _device_signal, _country_signal):
        signal = detector(transaction, history)
        if signal is not None:
            signals.append(signal)
    graph_risk, related = graph_signal(transaction, history)
    if graph_risk is not None:
        signals.append(graph_risk)

    score = min(100.0, round(sum(signal.weight for signal in signals), 2))
    decision = "allow"
    if score >= 70:
        decision = "block"
    elif score >= 35:
        decision = "review"
    return RiskResult(
        transaction_id=transaction.transaction_id,
        risk_score=score,
        decision=decision,
        signals=signals,
        related_accounts=related,
    )


def batch_summary(results: list[RiskResult]) -> dict:
    decisions = Counter(item.decision for item in results)
    scores = [item.risk_score for item in results]
    return {
        "transactions_scored": len(results),
        "allow": decisions["allow"],
        "review": decisions["review"],
        "block": decisions["block"],
        "average_risk": round(mean(scores), 2) if scores else 0.0,
    }


def exposure_score(transactions: list[Transaction], account: str) -> dict:
    outgoing = [item for item in transactions if item.sender_account == account]
    incoming = [item for item in transactions if item.receiver_account == account]
    counterparties = {
        item.receiver_account for item in outgoing
    } | {
        item.sender_account for item in incoming
    }
    volume = sum(item.amount for item in outgoing + incoming)
    score = min(
        100.0,
        round(
            8 * log1p(len(counterparties))
            + 6 * log1p(len(outgoing) + len(incoming))
            + 4 * log1p(volume / 10_000),
            2,
        ),
    )
    return {
        "account": account,
        "counterparties": len(counterparties),
        "transaction_count": len(outgoing) + len(incoming),
        "gross_flow": round(volume, 2),
        "network_exposure_score": score,
    }
