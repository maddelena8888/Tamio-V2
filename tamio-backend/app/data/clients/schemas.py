"""Client schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.treasury import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    ClientCreateForOnboarding,
    ClientWithEventsResponse,
)

__all__ = [
    "ClientCreate",
    "ClientResponse",
    "ClientUpdate",
    "ClientCreateForOnboarding",
    "ClientWithEventsResponse",
]
