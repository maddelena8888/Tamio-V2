"""Xero schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.xero import (
    XeroConnectionStatus,
    XeroAuthUrl,
    XeroCallbackRequest,
    XeroTokenResponse,
    XeroSyncRequest,
    XeroSyncResult,
    XeroInvoiceSummary,
    XeroContactSummary,
    XeroBankTransactionSummary,
    XeroOrganisation,
)

__all__ = [
    "XeroConnectionStatus",
    "XeroAuthUrl",
    "XeroCallbackRequest",
    "XeroTokenResponse",
    "XeroSyncRequest",
    "XeroSyncResult",
    "XeroInvoiceSummary",
    "XeroContactSummary",
    "XeroBankTransactionSummary",
    "XeroOrganisation",
]
