"""Temporal graph intelligence: detect coordinated fund movement and account layering.

All detections are explainable and deterministic; no external graph DB is required.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from math import exp

from riskmesh.models import Transaction


@dataclass(frozen=True)
class TemporalFinding:
    code: str
    score: float
    accounts: tuple[str, ...]
    transaction_ids: tuple[str, ...]
    explanation: str

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "score": self.score,
            "accounts": list(self.accounts),
            "transaction_ids": list(self.transaction_ids),
            "explanation": self.explanation,
        }


def investigate(
    candidate: Transaction,
    history: list[Transaction],
    *,
    max_hops: int = 5,
    window_minutes: int = 180,
) -> list[TemporalFinding]:
    """Search time-respecting paths and coordinated fan-in/fan-out motifs.

    Only earlier events from the same tenant are eligible. Each hop must occur
    after its predecessor, preventing impossible backward-in-time paths.
    """
    if not 2 <= max_hops <= 6:
        raise ValueError("max_hops must be between 2 and 6")
    if not 1 <= window_minutes <= 1440:
        raise ValueError("window_minutes must be between 1 and 1440")
    if len(history) > 20_000:
        raise ValueError("History limit exceeded")

    start = candidate.timestamp - timedelta(minutes=window_minutes)
    events = sorted(
        (
            tx
            for tx in history
            if tx.tenant_id == candidate.tenant_id
            and tx.transaction_id != candidate.transaction_id
            and start <= tx.timestamp <= candidate.timestamp
        ),
        key=lambda tx: (tx.timestamp, tx.transaction_id),
    )
    by_sender: dict[str, list[Transaction]] = defaultdict(list)
    incoming: dict[str, list[Transaction]] = defaultdict(list)
    for tx in events:
        by_sender[tx.sender_account].append(tx)
        incoming[tx.receiver_account].append(tx)

    findings: list[TemporalFinding] = []
    # The candidate closes a time-respecting cycle if historical funds could
    # flow from its receiver to its sender before the candidate timestamp.
    queue = deque([(candidate.receiver_account, start, (), (candidate.receiver_account,))])
    visited: set[tuple[str, int]] = set()
    while queue:
        node, previous_time, path, accounts = queue.popleft()
        if len(path) >= max_hops:
            continue
        for tx in by_sender.get(node, []):
            if tx.timestamp < previous_time or tx.receiver_account in accounts[:-1]:
                continue
            next_path = path + (tx.transaction_id,)
            next_accounts = accounts + (tx.receiver_account,)
            if tx.receiver_account == candidate.sender_account:
                findings.append(
                    TemporalFinding(
                        code="TEMPORAL_CIRCULAR_FLOW",
                        score=min(45.0, 22.0 + 5.0 * len(next_path)),
                        accounts=next_accounts,
                        transaction_ids=next_path + (candidate.transaction_id,),
                        explanation="Time-ordered transfers form a circular funding path",
                    )
                )
                break
            bucket = (tx.receiver_account, len(next_path))
            if bucket not in visited:
                visited.add(bucket)
                queue.append((tx.receiver_account, tx.timestamp, next_path, next_accounts))
        if findings:
            break

    # Detect potential aggregation: multiple distinct senders paying one
    # account shortly before it transfers onward.
    inbound = [
        tx
        for tx in incoming.get(candidate.sender_account, [])
        if candidate.timestamp - tx.timestamp <= timedelta(minutes=60)
    ]
    unique_sources = {tx.sender_account for tx in inbound}
    if len(unique_sources) >= 3:
        total = sum(tx.amount for tx in inbound)
        ratio = candidate.amount / max(total, 0.01)
        if 0.4 <= ratio <= 1.2:
            findings.append(
                TemporalFinding(
                    code="AGGREGATION_LAYERING",
                    score=min(42.0, 18.0 + 5.0 * len(unique_sources)),
                    accounts=tuple(sorted(unique_sources | {candidate.sender_account, candidate.receiver_account})),
                    transaction_ids=tuple(tx.transaction_id for tx in inbound) + (candidate.transaction_id,),
                    explanation="Multiple sources fund an account shortly before a comparable outbound transfer",
                )
            )

    # Detect rapid dispersal from one sender to many unique destinations.
    outgoing = [
        tx for tx in by_sender.get(candidate.sender_account, [])
        if candidate.timestamp - tx.timestamp <= timedelta(minutes=20)
    ]
    destinations = {tx.receiver_account for tx in outgoing} | {candidate.receiver_account}
    if len(destinations) >= 5:
        findings.append(
            TemporalFinding(
                code="RAPID_DISPERSAL",
                score=min(35.0, 15.0 + 3.0 * len(destinations)),
                accounts=tuple(sorted(destinations | {candidate.sender_account})),
                transaction_ids=tuple(tx.transaction_id for tx in outgoing) + (candidate.transaction_id,),
                explanation="One account rapidly disperses funds to multiple destinations",
            )
        )
    return findings


def combine_risk(base_score: float, findings: list[TemporalFinding]) -> float:
    """Nonlinear bounded fusion prevents unbounded addition of correlated signals."""
    survival = 1.0 - min(max(base_score, 0.0), 100.0) / 100.0
    for finding in findings:
        survival *= exp(-finding.score / 100.0)
    return round(min(100.0, 100.0 * (1.0 - survival)), 2)
