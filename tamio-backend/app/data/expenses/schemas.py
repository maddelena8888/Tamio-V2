"""Expense schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.treasury import (
    ExpenseBucketCreate,
    ExpenseBucketResponse,
    ExpenseBucketUpdate,
    ExpenseBucketCreateForOnboarding,
    ExpenseBucketWithEventsResponse,
)

__all__ = [
    "ExpenseBucketCreate",
    "ExpenseBucketResponse",
    "ExpenseBucketUpdate",
    "ExpenseBucketCreateForOnboarding",
    "ExpenseBucketWithEventsResponse",
]
