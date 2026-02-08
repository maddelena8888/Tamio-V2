"""UserConfiguration model - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.user_config import UserConfiguration, SafetyMode

__all__ = ["UserConfiguration", "SafetyMode"]
