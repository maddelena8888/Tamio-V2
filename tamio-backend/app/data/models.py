"""
Database models for Tamio - Re-exports from entity-specific modules.

This file provides backward compatibility by re-exporting all models
from their new locations in entity-specific subdirectories.
"""
# Re-export all models from their new locations
from app.data.base import generate_id
from app.data.users.models import User
from app.data.balances.models import CashAccount
from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import ObligationAgreement, ObligationSchedule, PaymentEvent

__all__ = [
    "generate_id",
    "User",
    "CashAccount",
    "Client",
    "ExpenseBucket",
    "ObligationAgreement",
    "ObligationSchedule",
    "PaymentEvent",
]
