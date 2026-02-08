"""Obligation schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.obligation import (
    ObligationAgreementCreate,
    ObligationAgreementUpdate,
    ObligationAgreementResponse,
    ObligationScheduleCreate,
    ObligationScheduleUpdate,
    ObligationScheduleResponse,
    PaymentEventCreate,
    PaymentEventUpdate,
    PaymentEventResponse,
    ObligationWithSchedules,
    ObligationWithPayments,
    ObligationFull,
)

__all__ = [
    "ObligationAgreementCreate",
    "ObligationAgreementUpdate",
    "ObligationAgreementResponse",
    "ObligationScheduleCreate",
    "ObligationScheduleUpdate",
    "ObligationScheduleResponse",
    "PaymentEventCreate",
    "PaymentEventUpdate",
    "PaymentEventResponse",
    "ObligationWithSchedules",
    "ObligationWithPayments",
    "ObligationFull",
]
