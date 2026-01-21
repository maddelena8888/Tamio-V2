"""
Notifications Module - V4 Architecture

Handles email and Slack notifications for detection alerts and action updates.
"""

from .service import NotificationService, notification_service, get_notification_service
from .models import NotificationPreference, NotificationType
from .email_provider import (
    EmailProvider,
    EmailMessage,
    get_email_provider,
    SlackProvider,
    SlackMessage,
    get_slack_provider,
)

__all__ = [
    "NotificationService",
    "notification_service",
    "get_notification_service",
    "NotificationPreference",
    "NotificationType",
    "EmailProvider",
    "EmailMessage",
    "get_email_provider",
    "SlackProvider",
    "SlackMessage",
    "get_slack_provider",
]
