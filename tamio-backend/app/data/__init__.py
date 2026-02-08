"""
Data module - handles all data input and storage.

This module provides a unified interface to all data entities through
backward-compatible re-exports from entity-specific subdirectories.
"""
from app.data import models, schemas, routes

# Re-export for convenience
from app.data.models import (
    User,
    CashAccount,
    Client,
    ExpenseBucket,
    ObligationAgreement,
    ObligationSchedule,
    PaymentEvent,
)

__all__ = [
    "models",
    "schemas",
    "routes",
    # Models
    "User",
    "CashAccount",
    "Client",
    "ExpenseBucket",
    "ObligationAgreement",
    "ObligationSchedule",
    "PaymentEvent",
]
