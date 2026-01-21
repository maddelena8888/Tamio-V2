"""
Notification Service - V4 Architecture

Main service for sending notifications when alerts fire.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.data.users.models import User
from app.detection.models import DetectionAlert, AlertSeverity, AlertStatus
from app.preparation.models import PreparedAction, ActionStatus

from .models import (
    NotificationPreference,
    NotificationType,
    NotificationChannel,
    NotificationLog,
)
from .templates import (
    build_alert_email,
    build_escalation_email,
    build_action_ready_email,
    build_daily_digest_email,
)
from .email_provider import (
    EmailProvider,
    EmailMessage,
    get_email_provider,
    SlackProvider,
    SlackMessage,
    get_slack_provider,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending notifications.

    Handles:
    - Alert notifications (emergency, this_week, escalations)
    - Action ready notifications
    - Daily digest emails
    """

    def __init__(
        self,
        db: AsyncSession,
        email_provider: Optional[EmailProvider] = None,
        slack_provider: Optional[SlackProvider] = None,
    ):
        self.db = db
        self.email_provider = email_provider or get_email_provider(
            resend_api_key=getattr(settings, "RESEND_API_KEY", None),
            console_mode=settings.APP_ENV == "development",
        )
        self.slack_provider = slack_provider or get_slack_provider(
            bot_token=getattr(settings, "SLACK_BOT_TOKEN", None),
            default_channel=getattr(settings, "SLACK_DEFAULT_CHANNEL", "#treasury-alerts"),
            console_mode=settings.APP_ENV == "development",
        )

    def _get_dashboard_url(self, user_id: str) -> str:
        """Get dashboard URL for user."""
        return f"{settings.FRONTEND_URL}/dashboard"

    def _get_settings_url(self) -> str:
        """Get notification settings URL."""
        return f"{settings.FRONTEND_URL}/settings"

    async def _get_user_preferences(
        self,
        user_id: str,
        notification_type: NotificationType,
    ) -> Optional[NotificationPreference]:
        """Get user's notification preference for a specific type."""
        result = await self.db.execute(
            select(NotificationPreference)
            .where(NotificationPreference.user_id == user_id)
            .where(NotificationPreference.notification_type == notification_type)
        )
        return result.scalar_one_or_none()

    async def _should_send_email(
        self,
        user_id: str,
        notification_type: NotificationType,
    ) -> bool:
        """Check if email should be sent based on user preferences."""
        pref = await self._get_user_preferences(user_id, notification_type)

        # If no preference exists, use defaults
        if not pref:
            # Emergency alerts always send by default
            if notification_type == NotificationType.ALERT_EMERGENCY:
                return True
            # This-week alerts send by default
            if notification_type == NotificationType.ALERT_THIS_WEEK:
                return True
            # Escalations always send
            if notification_type == NotificationType.ALERT_ESCALATED:
                return True
            # Action ready sends by default
            if notification_type == NotificationType.ACTION_READY:
                return True
            return False

        return pref.email_enabled

    async def _log_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        recipient: str,
        subject: str,
        alert_id: Optional[str] = None,
        action_id: Optional[str] = None,
        delivered: bool = True,
        error_message: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> NotificationLog:
        """Log a sent notification."""
        log = NotificationLog(
            user_id=user_id,
            notification_type=notification_type,
            channel=NotificationChannel.EMAIL,
            recipient=recipient,
            subject=subject,
            alert_id=alert_id,
            action_id=action_id,
            delivered=delivered,
            error_message=error_message,
            external_id=external_id,
        )
        self.db.add(log)
        return log

    async def _check_recent_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        alert_id: Optional[str] = None,
        action_id: Optional[str] = None,
        cooldown_minutes: int = 60,
    ) -> bool:
        """
        Check if a similar notification was sent recently.

        Returns True if notification was sent within cooldown period.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=cooldown_minutes)

        query = (
            select(NotificationLog)
            .where(NotificationLog.user_id == user_id)
            .where(NotificationLog.notification_type == notification_type)
            .where(NotificationLog.sent_at > cutoff)
            .where(NotificationLog.delivered == True)
        )

        if alert_id:
            query = query.where(NotificationLog.alert_id == alert_id)
        if action_id:
            query = query.where(NotificationLog.action_id == action_id)

        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    # =========================================================================
    # ALERT NOTIFICATIONS
    # =========================================================================

    async def notify_alert_created(self, alert: DetectionAlert) -> bool:
        """
        Send notification when a new alert is created.

        Only sends for EMERGENCY and THIS_WEEK severity by default.
        """
        # Determine notification type based on severity
        if alert.severity == AlertSeverity.EMERGENCY:
            notification_type = NotificationType.ALERT_EMERGENCY
        elif alert.severity == AlertSeverity.THIS_WEEK:
            notification_type = NotificationType.ALERT_THIS_WEEK
        else:
            # Don't notify for UPCOMING by default
            return False

        # Check if user wants this notification
        if not await self._should_send_email(alert.user_id, notification_type):
            logger.debug(f"User {alert.user_id} has disabled {notification_type} notifications")
            return False

        # Check for recent similar notification (debounce)
        if await self._check_recent_notification(
            alert.user_id,
            notification_type,
            alert_id=alert.id,
            cooldown_minutes=60,
        ):
            logger.debug(f"Recent notification already sent for alert {alert.id}")
            return False

        # Get user email
        result = await self.db.execute(
            select(User.email).where(User.id == alert.user_id)
        )
        user_email = result.scalar_one_or_none()
        if not user_email:
            logger.error(f"User {alert.user_id} not found")
            return False

        # Build email
        subject, html_body, plain_text = build_alert_email(
            alert_title=alert.title,
            alert_description=alert.description or "",
            severity=alert.severity,
            detection_type=alert.detection_type,
            cash_impact=alert.cash_impact,
            context_data=alert.context_data or {},
            dashboard_url=self._get_dashboard_url(alert.user_id),
            settings_url=self._get_settings_url(),
            deadline=alert.deadline,
        )

        # Send email
        result = await self.email_provider.send(
            EmailMessage(
                to=user_email,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_text,
            )
        )

        # Log the notification
        await self._log_notification(
            user_id=alert.user_id,
            notification_type=notification_type,
            recipient=user_email,
            subject=subject,
            alert_id=alert.id,
            delivered=result.success,
            error_message=result.error,
            external_id=result.message_id,
        )

        if result.success:
            logger.info(f"Sent {notification_type} notification for alert {alert.id}")
        else:
            logger.error(f"Failed to send notification for alert {alert.id}: {result.error}")

        return result.success

    async def notify_alert_created_slack(self, alert: DetectionAlert) -> bool:
        """
        Send Slack notification when a new alert is created.

        Sends for EMERGENCY alerts immediately, batches others.
        """
        # Only send Slack for emergency alerts
        if alert.severity != AlertSeverity.EMERGENCY:
            return False

        # Build Slack message with rich blocks
        blocks = self.slack_provider.build_alert_blocks(
            title=alert.title,
            description=alert.description or "",
            severity=alert.severity.value,
            cash_impact=alert.cash_impact,
            dashboard_url=self._get_dashboard_url(alert.user_id),
        )

        result = await self.slack_provider.send(
            SlackMessage(
                channel=self.slack_provider.default_channel,
                text=f"🔴 EMERGENCY: {alert.title}",
                blocks=blocks,
            )
        )

        if result.success:
            # Log the notification
            await self._log_notification(
                user_id=alert.user_id,
                notification_type=NotificationType.ALERT_EMERGENCY,
                recipient=self.slack_provider.default_channel,
                subject=f"Slack: {alert.title}",
                alert_id=alert.id,
                delivered=True,
                external_id=result.message_ts,
            )
            logger.info(f"Sent Slack notification for emergency alert {alert.id}")
        else:
            logger.error(f"Failed to send Slack notification: {result.error}")

        return result.success

    async def notify_alert_created_all_channels(self, alert: DetectionAlert) -> dict:
        """
        Send alert notification via all configured channels.

        Returns dict with results per channel.
        """
        results = {
            "email": False,
            "slack": False,
        }

        # Send email
        results["email"] = await self.notify_alert_created(alert)

        # Send Slack for emergency alerts
        if alert.severity == AlertSeverity.EMERGENCY:
            results["slack"] = await self.notify_alert_created_slack(alert)

        return results

    async def notify_alert_escalated(
        self,
        alert: DetectionAlert,
        old_severity: AlertSeverity,
        reason: str,
    ) -> bool:
        """Send notification when an alert is escalated."""
        notification_type = NotificationType.ALERT_ESCALATED

        if not await self._should_send_email(alert.user_id, notification_type):
            return False

        # Get user email
        result = await self.db.execute(
            select(User.email).where(User.id == alert.user_id)
        )
        user_email = result.scalar_one_or_none()
        if not user_email:
            return False

        # Build email
        subject, html_body, plain_text = build_escalation_email(
            alert_title=alert.title,
            old_severity=old_severity,
            new_severity=alert.severity,
            reason=reason,
            dashboard_url=self._get_dashboard_url(alert.user_id),
            settings_url=self._get_settings_url(),
        )

        # Send email
        result = await self.email_provider.send(
            EmailMessage(
                to=user_email,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_text,
            )
        )

        # Log
        await self._log_notification(
            user_id=alert.user_id,
            notification_type=notification_type,
            recipient=user_email,
            subject=subject,
            alert_id=alert.id,
            delivered=result.success,
            error_message=result.error,
            external_id=result.message_id,
        )

        return result.success

    # =========================================================================
    # ACTION NOTIFICATIONS
    # =========================================================================

    async def notify_action_ready(self, action: PreparedAction) -> bool:
        """Send notification when an action is prepared and ready for approval."""
        notification_type = NotificationType.ACTION_READY

        if not await self._should_send_email(action.user_id, notification_type):
            return False

        # Check for recent notification
        if await self._check_recent_notification(
            action.user_id,
            notification_type,
            action_id=action.id,
            cooldown_minutes=30,
        ):
            return False

        # Get user email
        result = await self.db.execute(
            select(User.email).where(User.id == action.user_id)
        )
        user_email = result.scalar_one_or_none()
        if not user_email:
            return False

        # Count options
        options_count = len(action.options) if hasattr(action, "options") else 0

        # Build email
        subject, html_body, plain_text = build_action_ready_email(
            action_type=action.action_type.value,
            problem_summary=action.problem_summary,
            options_count=options_count,
            deadline=action.deadline,
            dashboard_url=self._get_dashboard_url(action.user_id),
            settings_url=self._get_settings_url(),
        )

        # Send email
        result = await self.email_provider.send(
            EmailMessage(
                to=user_email,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_text,
            )
        )

        # Log
        await self._log_notification(
            user_id=action.user_id,
            notification_type=notification_type,
            recipient=user_email,
            subject=subject,
            action_id=action.id,
            delivered=result.success,
            error_message=result.error,
            external_id=result.message_id,
        )

        return result.success

    # =========================================================================
    # DAILY DIGEST
    # =========================================================================

    async def send_daily_digest(self, user_id: str) -> bool:
        """Send daily digest email for a user."""
        notification_type = NotificationType.DAILY_DIGEST

        if not await self._should_send_email(user_id, notification_type):
            return False

        # Get user email
        result = await self.db.execute(
            select(User.email).where(User.id == user_id)
        )
        user_email = result.scalar_one_or_none()
        if not user_email:
            return False

        # Count alerts by severity
        emergency_count = await self._count_alerts(user_id, AlertSeverity.EMERGENCY)
        this_week_count = await self._count_alerts(user_id, AlertSeverity.THIS_WEEK)
        upcoming_count = await self._count_alerts(user_id, AlertSeverity.UPCOMING)

        # Count pending actions
        actions_pending = await self._count_pending_actions(user_id)

        # Get recent alerts for summary
        alerts_summary = await self._get_recent_alerts_summary(user_id)

        # Build email
        subject, html_body, plain_text = build_daily_digest_email(
            emergency_count=emergency_count,
            this_week_count=this_week_count,
            upcoming_count=upcoming_count,
            actions_pending=actions_pending,
            alerts_summary=alerts_summary,
            dashboard_url=self._get_dashboard_url(user_id),
            settings_url=self._get_settings_url(),
        )

        # Send email
        result = await self.email_provider.send(
            EmailMessage(
                to=user_email,
                subject=subject,
                html_body=html_body,
                plain_text_body=plain_text,
            )
        )

        # Log
        await self._log_notification(
            user_id=user_id,
            notification_type=notification_type,
            recipient=user_email,
            subject=subject,
            delivered=result.success,
            error_message=result.error,
            external_id=result.message_id,
        )

        return result.success

    async def send_daily_digest_slack(self) -> bool:
        """
        Send daily digest to Slack channel.

        Aggregates across all users for the company channel.
        """
        # Count alerts across all users (company-wide view)
        emergency_result = await self.db.execute(
            select(func.count(DetectionAlert.id))
            .where(DetectionAlert.severity == AlertSeverity.EMERGENCY)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
        )
        emergency_count = emergency_result.scalar() or 0

        this_week_result = await self.db.execute(
            select(func.count(DetectionAlert.id))
            .where(DetectionAlert.severity == AlertSeverity.THIS_WEEK)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
        )
        this_week_count = this_week_result.scalar() or 0

        upcoming_result = await self.db.execute(
            select(func.count(DetectionAlert.id))
            .where(DetectionAlert.severity == AlertSeverity.UPCOMING)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
        )
        upcoming_count = upcoming_result.scalar() or 0

        actions_result = await self.db.execute(
            select(func.count(PreparedAction.id))
            .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
        )
        actions_pending = actions_result.scalar() or 0

        # Build Slack blocks
        blocks = self.slack_provider.build_digest_blocks(
            emergency_count=emergency_count,
            this_week_count=this_week_count,
            upcoming_count=upcoming_count,
            actions_pending=actions_pending,
            dashboard_url=f"{settings.FRONTEND_URL}/dashboard",
        )

        # Determine header text
        if emergency_count > 0:
            text = f"🔴 Daily Digest: {emergency_count} Emergency Alert(s)"
        elif this_week_count > 0:
            text = f"🟡 Daily Digest: {this_week_count} Item(s) Need Attention"
        else:
            text = "✅ Daily Digest: All Clear"

        result = await self.slack_provider.send(
            SlackMessage(
                channel=self.slack_provider.default_channel,
                text=text,
                blocks=blocks,
            )
        )

        if result.success:
            logger.info("Sent daily digest to Slack")
        else:
            logger.error(f"Failed to send Slack digest: {result.error}")

        return result.success

    async def _count_alerts(self, user_id: str, severity: AlertSeverity) -> int:
        """Count active alerts by severity."""
        result = await self.db.execute(
            select(func.count(DetectionAlert.id))
            .where(DetectionAlert.user_id == user_id)
            .where(DetectionAlert.severity == severity)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
        )
        return result.scalar() or 0

    async def _count_pending_actions(self, user_id: str) -> int:
        """Count actions pending approval."""
        result = await self.db.execute(
            select(func.count(PreparedAction.id))
            .where(PreparedAction.user_id == user_id)
            .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
        )
        return result.scalar() or 0

    async def _get_recent_alerts_summary(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[dict]:
        """Get recent alerts for digest summary."""
        result = await self.db.execute(
            select(DetectionAlert)
            .where(DetectionAlert.user_id == user_id)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
            .order_by(
                # Emergency first, then by detection time
                DetectionAlert.severity.asc(),
                DetectionAlert.detected_at.desc(),
            )
            .limit(limit)
        )
        alerts = result.scalars().all()

        return [
            {
                "title": alert.title,
                "description": alert.description,
                "severity": alert.severity.value,
                "detection_type": alert.detection_type.value,
            }
            for alert in alerts
        ]

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    async def send_all_daily_digests(self) -> dict:
        """
        Send daily digest to all users.

        Returns summary of results.
        """
        from app.database import async_session_maker

        summary = {
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        async with async_session_maker() as db:
            # Get all users
            result = await db.execute(select(User.id))
            user_ids = [row[0] for row in result.fetchall()]

            for user_id in user_ids:
                try:
                    service = NotificationService(db)
                    sent = await service.send_daily_digest(user_id)
                    if sent:
                        summary["sent"] += 1
                    else:
                        summary["skipped"] += 1
                except Exception as e:
                    logger.error(f"Failed to send digest to user {user_id}: {e}")
                    summary["failed"] += 1
                    summary["errors"].append({
                        "user_id": user_id,
                        "error": str(e),
                    })

            await db.commit()

        return summary


# Singleton for convenience
notification_service: Optional[NotificationService] = None


def get_notification_service(db: AsyncSession) -> NotificationService:
    """Get a notification service instance."""
    return NotificationService(db)
