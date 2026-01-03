"""Onboarding schemas - combined schemas for complete onboarding flow."""
from pydantic import BaseModel
from typing import List

from app.data.users.schemas import UserCreate, UserResponse
from app.data.balances.schemas import CashAccountCreate, CashPositionResponse
from app.data.clients.schemas import ClientCreateForOnboarding, ClientResponse
from app.data.expenses.schemas import ExpenseBucketCreateForOnboarding, ExpenseBucketResponse


class OnboardingCreate(BaseModel):
    """Schema for complete onboarding (all 3 pages)."""
    user: UserCreate
    cash_position: List[CashAccountCreate]
    clients: List[ClientCreateForOnboarding]
    expenses: List[ExpenseBucketCreateForOnboarding]


class OnboardingResponse(BaseModel):
    """Schema for onboarding response."""
    user: UserResponse
    cash_position: CashPositionResponse
    clients: List[ClientResponse]
    expenses: List[ExpenseBucketResponse]
    total_generated_events: int
