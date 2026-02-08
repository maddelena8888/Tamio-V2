"""Notification models - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.notification import (
    NotificationType,
    NotificationChannel,
    NotificationPreference,
    NotificationLog,
)

__all__ = [
    "NotificationType",
    "NotificationChannel",
    "NotificationPreference",
    "NotificationLog",
]
