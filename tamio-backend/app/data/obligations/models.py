"""Obligation models - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.obligation import ObligationAgreement, ObligationSchedule, PaymentEvent

__all__ = ["ObligationAgreement", "ObligationSchedule", "PaymentEvent"]
