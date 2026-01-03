"""
Integration adapters for accounting software.

This module provides a unified interface for integrating with various
accounting platforms (Xero, QuickBooks, etc.) while maintaining a
single source of truth in Tamio's canonical data model.
"""
from app.integrations.base import IntegrationAdapter, IntegrationType
from app.integrations.confidence import (
    ConfidenceLevel,
    ConfidenceScore,
    calculate_client_confidence,
    calculate_expense_confidence,
)

__all__ = [
    "IntegrationAdapter",
    "IntegrationType",
    "ConfidenceLevel",
    "ConfidenceScore",
    "calculate_client_confidence",
    "calculate_expense_confidence",
]
