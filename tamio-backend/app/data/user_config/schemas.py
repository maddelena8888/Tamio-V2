"""UserConfiguration schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.user_config import (
    UserConfigurationBase,
    UserConfigurationCreate,
    UserConfigurationUpdate,
    UserConfigurationResponse,
    UserConfigurationWithDefaults,
)

__all__ = [
    "UserConfigurationBase",
    "UserConfigurationCreate",
    "UserConfigurationUpdate",
    "UserConfigurationResponse",
    "UserConfigurationWithDefaults",
]
