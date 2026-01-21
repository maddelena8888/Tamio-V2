"""
Detection Scheduler - V4 Architecture

Background job scheduler that runs detection at appropriate intervals:
- Critical rules (payroll_safety, buffer_breach): every 5 minutes
- Routine rules (late_payments, unexpected_expenses): every hour
- Scheduled rules (statutory_deadlines): daily at 6am

Uses APScheduler for job scheduling.
Sends email notifications when alerts are created.
"""

import logging
from datetime import datetime
from typing import Optional, List, Callable, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.data.users.models import User
from app.audit.services import AuditService
from .engine import DetectionEngine
from .models import DetectionType, DetectionAlert

logger = logging.getLogger(__name__)


async def _send_alert_notifications(db: AsyncSession, alerts: List[DetectionAlert]) -> dict:
    """
    Send notifications for newly created alerts via all channels (email + Slack).

    Returns dict with counts for each channel.
    """
    results = {
        "email_sent": 0,
        "slack_sent": 0,
        "total": 0,
    }

    if not alerts:
        return results

    from app.notifications.service import get_notification_service

    notification_service = get_notification_service(db)

    for alert in alerts:
        try:
            # Send to all configured channels
            channel_results = await notification_service.notify_alert_created_all_channels(alert)
            if channel_results.get("email"):
                results["email_sent"] += 1
            if channel_results.get("slack"):
                results["slack_sent"] += 1
            if channel_results.get("email") or channel_results.get("slack"):
                results["total"] += 1
        except Exception as e:
            logger.error(f"Failed to send notification for alert {alert.id}: {e}")

    return results


# Detection type categories for scheduling
CRITICAL_DETECTIONS = [
    DetectionType.PAYROLL_SAFETY,
    DetectionType.BUFFER_BREACH,
]

ROUTINE_DETECTIONS = [
    DetectionType.LATE_PAYMENT,
    DetectionType.UNEXPECTED_EXPENSE,
    DetectionType.UNEXPECTED_REVENUE,
    DetectionType.CLIENT_CHURN,
    DetectionType.REVENUE_VARIANCE,
    DetectionType.PAYMENT_TIMING_CONFLICT,
    DetectionType.VENDOR_TERMS_EXPIRING,
    DetectionType.HEADCOUNT_CHANGE,
]

DAILY_DETECTIONS = [
    DetectionType.STATUTORY_DEADLINE,
    DetectionType.RUNWAY_THRESHOLD,
]


class DetectionScheduler:
    """
    Manages scheduled detection runs.

    This class can be used with APScheduler or any other job scheduler.
    It provides methods that can be called on schedule.
    """

    def __init__(self):
        self._running = False
        self._last_critical_run: Optional[datetime] = None
        self._last_routine_run: Optional[datetime] = None
        self._last_daily_run: Optional[datetime] = None

    async def run_critical_detections(self) -> dict:
        """
        Run critical detections for all users.

        Should be scheduled every 5 minutes.
        Critical detections: payroll_safety, buffer_breach

        Returns summary of alerts created.
        """
        logger.info("Starting critical detection run")
        self._last_critical_run = datetime.utcnow()

        summary = {
            "run_type": "critical",
            "started_at": self._last_critical_run.isoformat(),
            "users_processed": 0,
            "alerts_created": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        async with async_session_maker() as db:
            try:
                # Get all active users
                result = await db.execute(select(User.id))
                user_ids = [row[0] for row in result.fetchall()]

                for user_id in user_ids:
                    try:
                        engine = DetectionEngine(db, user_id)
                        alerts = await engine.run_critical_detections()
                        summary["alerts_created"] += len(alerts)
                        summary["users_processed"] += 1

                        # Send notifications for new alerts
                        if alerts:
                            await db.commit()  # Commit alerts first so they have IDs
                            notif_results = await _send_alert_notifications(db, alerts)
                            summary["notifications_sent"] += notif_results["total"]

                    except Exception as e:
                        logger.error(f"Critical detection failed for user {user_id}: {e}")
                        summary["errors"].append({
                            "user_id": user_id,
                            "error": str(e),
                        })

                await db.commit()

                # Log to audit
                audit = AuditService(db, user_id=None, source="system")
                await audit.log(
                    entity_type="detection_scheduler",
                    entity_id="critical",
                    action="run",
                    metadata=summary,
                )
                await db.commit()

            except Exception as e:
                logger.error(f"Critical detection run failed: {e}")
                summary["errors"].append({"error": str(e)})

        summary["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Critical detection run completed: {summary['alerts_created']} alerts, {summary['notifications_sent']} notifications")
        return summary

    async def run_routine_detections(self) -> dict:
        """
        Run routine detections for all users.

        Should be scheduled every hour.
        Routine detections: late_payments, unexpected_expenses, etc.

        Returns summary of alerts created.
        """
        logger.info("Starting routine detection run")
        self._last_routine_run = datetime.utcnow()

        summary = {
            "run_type": "routine",
            "started_at": self._last_routine_run.isoformat(),
            "users_processed": 0,
            "alerts_created": 0,
            "escalations": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        async with async_session_maker() as db:
            try:
                # Get all active users
                result = await db.execute(select(User.id))
                user_ids = [row[0] for row in result.fetchall()]

                for user_id in user_ids:
                    try:
                        engine = DetectionEngine(db, user_id)
                        all_alerts = []

                        # Run each routine detection type
                        for detection_type in ROUTINE_DETECTIONS:
                            try:
                                alerts = await engine.run_detection_type(detection_type)
                                all_alerts.extend(alerts)
                                summary["alerts_created"] += len(alerts)
                            except Exception as e:
                                logger.error(f"Detection {detection_type} failed for user {user_id}: {e}")

                        # Also run escalation check
                        escalated = await engine.escalate_alerts()
                        summary["escalations"] += len(escalated)

                        summary["users_processed"] += 1

                        # Send notifications for new alerts
                        if all_alerts:
                            await db.commit()  # Commit alerts first so they have IDs
                            notif_results = await _send_alert_notifications(db, all_alerts)
                            summary["notifications_sent"] += notif_results["total"]

                    except Exception as e:
                        logger.error(f"Routine detection failed for user {user_id}: {e}")
                        summary["errors"].append({
                            "user_id": user_id,
                            "error": str(e),
                        })

                await db.commit()

            except Exception as e:
                logger.error(f"Routine detection run failed: {e}")
                summary["errors"].append({"error": str(e)})

        summary["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Routine detection run completed: {summary['alerts_created']} alerts, {summary['escalations']} escalations, {summary['notifications_sent']} notifications")
        return summary

    async def run_daily_detections(self) -> dict:
        """
        Run daily detections for all users.

        Should be scheduled daily at 6am.
        Daily detections: statutory_deadlines, runway_threshold

        Returns summary of alerts created.
        """
        logger.info("Starting daily detection run")
        self._last_daily_run = datetime.utcnow()

        summary = {
            "run_type": "daily",
            "started_at": self._last_daily_run.isoformat(),
            "users_processed": 0,
            "alerts_created": 0,
            "notifications_sent": 0,
            "digests_sent": 0,
            "errors": [],
        }

        async with async_session_maker() as db:
            try:
                # Get all active users
                result = await db.execute(select(User.id))
                user_ids = [row[0] for row in result.fetchall()]

                for user_id in user_ids:
                    try:
                        engine = DetectionEngine(db, user_id)
                        all_alerts = []

                        # Run each daily detection type
                        for detection_type in DAILY_DETECTIONS:
                            try:
                                alerts = await engine.run_detection_type(detection_type)
                                all_alerts.extend(alerts)
                                summary["alerts_created"] += len(alerts)
                            except Exception as e:
                                logger.error(f"Detection {detection_type} failed for user {user_id}: {e}")

                        summary["users_processed"] += 1

                        # Commit alerts first
                        await db.commit()

                        # Send notifications for new alerts
                        if all_alerts:
                            notif_results = await _send_alert_notifications(db, all_alerts)
                            summary["notifications_sent"] += notif_results["total"]

                        # Send daily digest (per-user email)
                        try:
                            from app.notifications.service import get_notification_service
                            notification_service = get_notification_service(db)
                            digest_sent = await notification_service.send_daily_digest(user_id)
                            if digest_sent:
                                summary["digests_sent"] += 1
                        except Exception as e:
                            logger.error(f"Daily digest failed for user {user_id}: {e}")

                    except Exception as e:
                        logger.error(f"Daily detection failed for user {user_id}: {e}")
                        summary["errors"].append({
                            "user_id": user_id,
                            "error": str(e),
                        })

                await db.commit()

                # Send Slack daily digest (company-wide, once per day)
                try:
                    from app.notifications.service import get_notification_service
                    notification_service = get_notification_service(db)
                    await notification_service.send_daily_digest_slack()
                    summary["slack_digest_sent"] = True
                except Exception as e:
                    logger.error(f"Slack daily digest failed: {e}")
                    summary["slack_digest_sent"] = False

            except Exception as e:
                logger.error(f"Daily detection run failed: {e}")
                summary["errors"].append({"error": str(e)})

        summary["completed_at"] = datetime.utcnow().isoformat()
        logger.info(f"Daily detection run completed: {summary['alerts_created']} alerts, {summary['digests_sent']} digests sent")
        return summary

    async def run_all_detections_for_user(self, user_id: str) -> dict:
        """
        Run all detections for a single user.

        Called on-demand when user opens dashboard or after data sync.

        Returns summary of alerts created.
        """
        logger.info(f"Running all detections for user {user_id}")

        summary = {
            "run_type": "on_demand",
            "user_id": user_id,
            "started_at": datetime.utcnow().isoformat(),
            "alerts_created": 0,
            "escalations": 0,
            "notifications_sent": 0,
            "errors": [],
        }

        async with async_session_maker() as db:
            try:
                engine = DetectionEngine(db, user_id)

                # Run all detections
                alerts = await engine.run_all_detections()
                summary["alerts_created"] = len(alerts)

                # Run escalation check
                escalated = await engine.escalate_alerts()
                summary["escalations"] = len(escalated)

                await db.commit()

                # Send notifications for new alerts
                if alerts:
                    notif_results = await _send_alert_notifications(db, alerts)
                    summary["notifications_sent"] = notif_results["total"]
                    await db.commit()

            except Exception as e:
                logger.error(f"On-demand detection failed for user {user_id}: {e}")
                summary["errors"].append({"error": str(e)})

        summary["completed_at"] = datetime.utcnow().isoformat()
        return summary

    def get_status(self) -> dict:
        """Get scheduler status including last run times."""
        return {
            "running": self._running,
            "last_critical_run": self._last_critical_run.isoformat() if self._last_critical_run else None,
            "last_routine_run": self._last_routine_run.isoformat() if self._last_routine_run else None,
            "last_daily_run": self._last_daily_run.isoformat() if self._last_daily_run else None,
        }


# Singleton instance for use across the application
detection_scheduler = DetectionScheduler()


def setup_apscheduler(scheduler):
    """
    Configure APScheduler with detection jobs.

    Usage:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        scheduler = AsyncIOScheduler()
        setup_apscheduler(scheduler)
        scheduler.start()

    Args:
        scheduler: APScheduler instance (AsyncIOScheduler)
    """
    # Critical detections every 5 minutes
    scheduler.add_job(
        detection_scheduler.run_critical_detections,
        'interval',
        minutes=5,
        id='critical_detections',
        name='Critical Detection Run',
        replace_existing=True,
    )

    # Routine detections every hour
    scheduler.add_job(
        detection_scheduler.run_routine_detections,
        'interval',
        hours=1,
        id='routine_detections',
        name='Routine Detection Run',
        replace_existing=True,
    )

    # Daily detections at 6am
    scheduler.add_job(
        detection_scheduler.run_daily_detections,
        'cron',
        hour=6,
        minute=0,
        id='daily_detections',
        name='Daily Detection Run',
        replace_existing=True,
    )

    logger.info("Detection scheduler jobs configured")


async def run_detections_after_sync(user_id: str, sync_type: str = "xero") -> dict:
    """
    Trigger detection run after a data sync completes.

    Called by Xero/QuickBooks sync handlers after successful sync.

    Args:
        user_id: User whose data was synced
        sync_type: Type of sync ("xero", "quickbooks", "bank_feed")

    Returns:
        Detection summary
    """
    logger.info(f"Running post-sync detections for user {user_id} after {sync_type} sync")
    return await detection_scheduler.run_all_detections_for_user(user_id)
