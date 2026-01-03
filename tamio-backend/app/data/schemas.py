"""
Pydantic schemas for data validation - Re-exports from entity-specific modules.

This file provides backward compatibility by re-exporting all schemas
from their new locations in entity-specific subdirectories.
"""
# User schemas
from app.data.users.schemas import UserCreate, UserResponse

# Balance/Cash Account schemas
from app.data.balances.schemas import (
    CashAccountCreate,
    CashAccountResponse,
    CashPositionCreate,
    CashAccountsUpdate,
    CashPositionResponse,
)

# Client schemas
from app.data.clients.schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    ClientCreateForOnboarding,
    ClientWithEventsResponse,
)

# Expense schemas
from app.data.expenses.schemas import (
    ExpenseBucketCreate,
    ExpenseBucketResponse,
    ExpenseBucketUpdate,
    ExpenseBucketCreateForOnboarding,
    ExpenseBucketWithEventsResponse,
)

# Event schemas
from app.data.events.schemas import CashEventResponse

# Onboarding schemas
from app.data.onboarding import OnboardingCreate, OnboardingResponse

__all__ = [
    # User
    "UserCreate",
    "UserResponse",
    # Balance
    "CashAccountCreate",
    "CashAccountResponse",
    "CashPositionCreate",
    "CashAccountsUpdate",
    "CashPositionResponse",
    # Client
    "ClientCreate",
    "ClientResponse",
    "ClientUpdate",
    "ClientCreateForOnboarding",
    "ClientWithEventsResponse",
    # Expense
    "ExpenseBucketCreate",
    "ExpenseBucketResponse",
    "ExpenseBucketUpdate",
    "ExpenseBucketCreateForOnboarding",
    "ExpenseBucketWithEventsResponse",
    # Event
    "CashEventResponse",
    # Onboarding
    "OnboardingCreate",
    "OnboardingResponse",
]
