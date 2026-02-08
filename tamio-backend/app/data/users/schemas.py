"""User schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.user import UserCreate, UserResponse

__all__ = ["UserCreate", "UserResponse"]
