"""Validated transaction and risk-result schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    timestamp: datetime
    tenant_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    sender_account: str = Field(min_length=1, max_length=120)
    receiver_account: str = Field(min_length=1, max_length=120)
    amount: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    device_id: str = Field(min_length=1, max_length=120)
    source_ip: str = Field(min_length=1, max_length=128)
    country: str = Field(min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    channel: Literal["web", "mobile", "api", "wire", "card"]


class RiskSignal(BaseModel):
    code: str
    weight: float
    explanation: str


class RiskResult(BaseModel):
    transaction_id: str
    risk_score: float
    decision: Literal["allow", "review", "block"]
    signals: list[RiskSignal]
    related_accounts: list[str]
