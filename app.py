"""Vercel FastAPI entrypoint for the read-only synthetic public showcase.

Protected endpoints require configured credentials and must not be operated
on Vercel's ephemeral filesystem as a financial transaction service.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from riskmesh.api import app  # noqa: E402, F401
