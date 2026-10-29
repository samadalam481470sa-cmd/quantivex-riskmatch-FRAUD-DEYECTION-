"""Tenant-scoped SQLite transaction and decision persistence for local development."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from riskmesh.models import RiskResult, Transaction


@contextmanager
def connection():
    path = os.getenv("RISK_MESH_DB_PATH", "/tmp/riskmesh.db")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS transactions(
          tenant TEXT NOT NULL,
          transaction_id TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          body TEXT NOT NULL,
          PRIMARY KEY(tenant,transaction_id));
        CREATE TABLE IF NOT EXISTS risk_decisions(
          tenant TEXT NOT NULL,
          transaction_id TEXT NOT NULL,
          risk_score REAL NOT NULL,
          decision TEXT NOT NULL,
          body TEXT NOT NULL,
          PRIMARY KEY(tenant,transaction_id));
        CREATE INDEX IF NOT EXISTS tx_tenant_time
          ON transactions(tenant,timestamp);
        """)
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def save(transaction: Transaction, result: RiskResult) -> None:
    with connection() as db:
        existing = db.execute(
            "SELECT body FROM transactions WHERE tenant=? AND transaction_id=?",
            (transaction.tenant_id, transaction.transaction_id),
        ).fetchone()
        if existing is not None:
            if existing["body"] != transaction.model_dump_json():
                raise HTTPException(status_code=409, detail="Transaction ID already used for different data")
            return
        db.execute(
            "INSERT INTO transactions VALUES (?,?,?,?)",
            (
                transaction.tenant_id,
                transaction.transaction_id,
                transaction.timestamp.isoformat(),
                transaction.model_dump_json(),
            ),
        )
        db.execute(
            "INSERT INTO risk_decisions VALUES (?,?,?,?,?)",
            (
                transaction.tenant_id,
                transaction.transaction_id,
                result.risk_score,
                result.decision,
                result.model_dump_json(),
            ),
        )


def history(tenant: str, limit: int = 5000) -> list[Transaction]:
    with connection() as db:
        rows = db.execute(
            "SELECT body FROM transactions WHERE tenant=? "
            "ORDER BY timestamp ASC LIMIT ?",
            (tenant, limit),
        ).fetchall()
    return [Transaction.model_validate_json(row["body"]) for row in rows]


def decisions(tenant: str, limit: int = 100) -> list[dict]:
    with connection() as db:
        rows = db.execute(
            "SELECT transaction_id,risk_score,decision,body "
            "FROM risk_decisions WHERE tenant=? "
            "ORDER BY rowid DESC LIMIT ?",
            (tenant, limit),
        ).fetchall()
    return [
        {
            "transaction_id": row["transaction_id"],
            "risk_score": row["risk_score"],
            "decision": row["decision"],
            "signals": json.loads(row["body"])["signals"],
        }
        for row in rows
    ]
