"""
Notification Routes - V4 Architecture

API endpoints for notification preferences and history.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.data.users.models import User

from .models import NotificationPreference, NotificationType, NotificationLog
from .service import get_notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


# =============================================================================
# SCHEMAS
# =============================================================================

class NotificationPreferenceResponse(BaseModel):
    """Response schema for notification preference."""
    notification_type: str
    email_enabled: bool
    batch_into_digest: bool
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None

    class Config:
        from_attributes = True


class NotificationPreferenceUpdate(BaseModel):
    """Request schema for updating notification preference."""
    email_enabled: Optional[bool] = None
    batch_into_digest: Optional[bool] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None


class NotificationLogResponse(BaseModel):
    """Response schema for notification log entry."""
    id: str
    notification_type: str
    channel: str
    subject: Optional[str]
    recipient: str
    sent_at: str
    delivered: bool
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class AllPreferencesResponse(BaseModel):
    """Response with all notification preferences."""
    preferences: List[NotificationPreferenceResponse]


class NotificationHistoryResponse(BaseModel):
    """Response with notification history."""
    logs: List[NotificationLogResponse]
    total: int


class TestNotificationRequest(BaseModel):
    """Request to send a test notification."""
    notification_type: str = "alert_emergency"


class TestNotificationResponse(BaseModel):
    """Response from test notification."""
    success: bool
    message: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/preferences", response_model=AllPreferencesResponse)
async def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all notification preferences for current user.

    Returns preferences for all notification types, with defaults for any not yet configured.
    """
    # Get existing preferences
    result = await db.execute(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == current_user.id)
    )
    existing = {p.notification_type: p for p in result.scalars().all()}

    # Build response with defaults for missing types
    preferences = []
    for notification_type in NotificationType:
        if notification_type in existing:
            pref = existing[notification_type]
            preferences.append(NotificationPreferenceResponse(
                notification_type=notification_type.value,
                email_enabled=pref.email_enabled,
                batch_into_digest=pref.batch_into_digest,
                quiet_hours_start=pref.quiet_hours_start,
                quiet_hours_end=pref.quiet_hours_end,
            ))
        else:
            # Default preferences
            preferences.append(NotificationPreferenceResponse(
                notification_type=notification_type.value,
                email_enabled=notification_type in [
                    NotificationType.ALERT_EMERGENCY,
                    NotificationType.ALERT_THIS_WEEK,
                    NotificationType.ALERT_ESCALATED,
                    NotificationType.ACTION_READY,
                ],
                batch_into_digest=notification_type == NotificationType.DAILY_DIGEST,
                quiet_hours_start=None,
                quiet_hours_end=None,
            ))

    return AllPreferencesResponse(preferences=preferences)


@router.put("/preferences/{notification_type}", response_model=NotificationPreferenceResponse)
async def update_notification_preference(
    notification_type: str,
    update: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update notification preference for a specific type.
    """
    # Validate notification type
    try:
        notif_type = NotificationType(notification_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid notification type: {notification_type}",
        )

    # Get or create preference
    result = await db.execute(
        select(NotificationPreference)
        .where(NotificationPreference.user_id == current_user.id)
        .where(NotificationPreference.notification_type == notif_type)
    )
    pref = result.scalar_one_or_none()

    if not pref:
        pref = NotificationPreference(
            user_id=current_user.id,
            notification_type=notif_type,
        )
        db.add(pref)

    # Update fields
    if update.email_enabled is not None:
        pref.email_enabled = update.email_enabled
    if update.batch_into_digest is not None:
        pref.batch_into_digest = update.batch_into_digest
    if update.quiet_hours_start is not None:
        pref.quiet_hours_start = update.quiet_hours_start
    if update.quiet_hours_end is not None:
        pref.quiet_hours_end = update.quiet_hours_end

    await db.commit()
    await db.refresh(pref)

    return NotificationPreferenceResponse(
        notification_type=pref.notification_type.value,
        email_enabled=pref.email_enabled,
        batch_into_digest=pref.batch_into_digest,
        quiet_hours_start=pref.quiet_hours_start,
        quiet_hours_end=pref.quiet_hours_end,
    )


@router.get("/history", response_model=NotificationHistoryResponse)
async def get_notification_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notification history for current user.
    """
    from sqlalchemy import func

    # Get total count
    count_result = await db.execute(
        select(func.count(NotificationLog.id))
        .where(NotificationLog.user_id == current_user.id)
    )
    total = count_result.scalar() or 0

    # Get logs
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.user_id == current_user.id)
        .order_by(NotificationLog.sent_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = result.scalars().all()

    return NotificationHistoryResponse(
        logs=[
            NotificationLogResponse(
                id=log.id,
                notification_type=log.notification_type.value,
                channel=log.channel.value,
                subject=log.subject,
                recipient=log.recipient,
                sent_at=log.sent_at.isoformat() if log.sent_at else "",
                delivered=log.delivered,
                error_message=log.error_message,
            )
            for log in logs
        ],
        total=total,
    )


@router.post("/test", response_model=TestNotificationResponse)
async def send_test_notification(
    request: TestNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a test notification to verify email delivery.
    """
    from .templates import build_alert_email
    from .email_provider import EmailMessage, get_email_provider
    from app.config import settings
    from app.detection.models import AlertSeverity, DetectionType

    # Build a test email
    subject, html_body, plain_text = build_alert_email(
        alert_title="Test Alert - Everything is Working",
        alert_description="This is a test notification to verify your email settings are configured correctly.",
        severity=AlertSeverity.THIS_WEEK,
        detection_type=DetectionType.LATE_PAYMENT,
        cash_impact=10000,
        context_data={
            "client_name": "Test Client",
            "days_overdue": 7,
            "amount": 10000,
        },
        dashboard_url=f"{settings.FRONTEND_URL}/dashboard",
        settings_url=f"{settings.FRONTEND_URL}/settings",
    )

    # Get provider
    provider = get_email_provider(
        resend_api_key=settings.RESEND_API_KEY,
        console_mode=settings.APP_ENV == "development",
    )

    # Send test email
    result = await provider.send(
        EmailMessage(
            to=current_user.email,
            subject=f"[TEST] {subject}",
            html_body=html_body,
            plain_text_body=plain_text,
        )
    )

    if result.success:
        return TestNotificationResponse(
            success=True,
            message=f"Test notification sent to {current_user.email}",
        )
    else:
        return TestNotificationResponse(
            success=False,
            message=f"Failed to send: {result.error}",
        )
