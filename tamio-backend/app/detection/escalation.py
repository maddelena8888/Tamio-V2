"""
Detection Escalation - V4 Architecture

Implements escalation logic from the product brief:
- When late invoice affects next payroll → escalate to emergency
- When deadline crosses 3-day threshold → escalate to emergency
- When cash drops below emergency buffer → escalate
- When obligations cluster → escalate to this_week
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DetectionAlert, DetectionType, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class EscalationEngine:
    """
    Handles alert escalation based on time and conditions.

    Escalation rules:
    1. Time-based: Alerts approaching deadline escalate
    2. Condition-based: Late payments affecting payroll escalate
    3. Cascade: Multiple related alerts can trigger escalation
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def run_escalation_check(self) -> List[DetectionAlert]:
        """
        Check all active alerts for escalation.

        Returns list of escalated alerts.
        """
        escalated = []

        # Get all non-emergency active alerts
        result = await self.db.execute(
            select(DetectionAlert)
            .where(DetectionAlert.user_id == self.user_id)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
            .where(DetectionAlert.severity != AlertSeverity.EMERGENCY)
        )
        alerts = result.scalars().all()

        for alert in alerts:
            should_escalate, reason = await self._should_escalate(alert)
            if should_escalate:
                self._escalate_alert(alert, reason)
                escalated.append(alert)

        return escalated

    async def _should_escalate(self, alert: DetectionAlert) -> Tuple[bool, Optional[str]]:
        """
        Determine if an alert should be escalated.

        Returns (should_escalate, reason).
        """
        now = datetime.utcnow()

        # Rule 1: Deadline within 3 days
        if alert.deadline:
            days_until_deadline = (alert.deadline - now).days
            if days_until_deadline <= 3:
                return True, f"Deadline in {days_until_deadline} days"

        # Rule 2: Alert active for 2+ days with no action
        if alert.severity == AlertSeverity.THIS_WEEK:
            days_active = (now - alert.detected_at).days
            if days_active >= 2:
                return True, f"No action for {days_active} days"

        # Rule 3: Late payment affecting payroll
        if alert.detection_type == DetectionType.LATE_PAYMENT:
            if await self._late_payment_affects_payroll(alert):
                return True, "Late payment affects upcoming payroll"

        # Rule 4: Large cash impact
        if alert.cash_impact:
            if abs(alert.cash_impact) > 50000 and alert.severity == AlertSeverity.UPCOMING:
                return True, f"Large cash impact: ${abs(alert.cash_impact):,.0f}"

        # Rule 5: High urgency score that's been ignored
        if alert.urgency_score and alert.urgency_score >= 80:
            days_active = (now - alert.detected_at).days
            if days_active >= 1:
                return True, f"High urgency ({alert.urgency_score}) ignored for {days_active} day(s)"

        # Rule 6: Multiple related alerts (cluster escalation)
        if await self._has_related_alerts(alert):
            return True, "Multiple related alerts detected"

        return False, None

    async def _late_payment_affects_payroll(self, alert: DetectionAlert) -> bool:
        """
        Check if a late payment alert affects upcoming payroll.

        Criteria: If collecting this invoice is needed to cover next payroll.
        """
        if alert.detection_type != DetectionType.LATE_PAYMENT:
            return False

        # Check if there's a payroll safety concern
        result = await self.db.execute(
            select(DetectionAlert)
            .where(DetectionAlert.user_id == self.user_id)
            .where(DetectionAlert.detection_type == DetectionType.PAYROLL_SAFETY)
            .where(DetectionAlert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
        )
        payroll_alert = result.scalar_one_or_none()

        if payroll_alert:
            # Check if this invoice amount would cover the shortfall
            invoice_amount = alert.context_data.get("amount", 0)
            shortfall = payroll_alert.context_data.get("shortfall", 0)

            if invoice_amount >= shortfall * 0.5:  # Covers at least 50% of shortfall
                return True

        return False

    async def _has_related_alerts(self, alert: DetectionAlert) -> bool:
        """
        Check if there are multiple related alerts that should trigger escalation.

        Related alerts include:
        - Same detection type for different entities
        - Different detection types affecting the same entity
        - Alerts that together indicate a systemic issue
        """
        # Check for multiple late payment alerts (cluster of overdue invoices)
        if alert.detection_type == DetectionType.LATE_PAYMENT:
            result = await self.db.execute(
                select(DetectionAlert)
                .where(DetectionAlert.user_id == self.user_id)
                .where(DetectionAlert.detection_type == DetectionType.LATE_PAYMENT)
                .where(DetectionAlert.status == AlertStatus.ACTIVE)
            )
            late_payments = result.scalars().all()
            if len(late_payments) >= 3:
                return True

        # Check for multiple expense spikes (systemic cost increase)
        if alert.detection_type == DetectionType.UNEXPECTED_EXPENSE:
            result = await self.db.execute(
                select(DetectionAlert)
                .where(DetectionAlert.user_id == self.user_id)
                .where(DetectionAlert.detection_type == DetectionType.UNEXPECTED_EXPENSE)
                .where(DetectionAlert.status == AlertStatus.ACTIVE)
            )
            expense_spikes = result.scalars().all()
            if len(expense_spikes) >= 2:
                return True

        # Check for combined revenue + expense issues
        if alert.detection_type in [DetectionType.REVENUE_VARIANCE, DetectionType.CLIENT_CHURN]:
            result = await self.db.execute(
                select(DetectionAlert)
                .where(DetectionAlert.user_id == self.user_id)
                .where(DetectionAlert.detection_type.in_([
                    DetectionType.REVENUE_VARIANCE,
                    DetectionType.CLIENT_CHURN,
                    DetectionType.BUFFER_BREACH,
                ]))
                .where(DetectionAlert.status == AlertStatus.ACTIVE)
            )
            related = result.scalars().all()
            if len(related) >= 2:
                return True

        return False

    def _escalate_alert(self, alert: DetectionAlert, reason: str) -> None:
        """Apply escalation to an alert."""
        previous_severity = alert.severity
        alert.severity = AlertSeverity.EMERGENCY
        alert.escalation_count += 1
        alert.last_escalated_at = datetime.utcnow()

        # Add escalation context
        alert.context_data = {
            **alert.context_data,
            "escalation_reason": reason,
            "escalated_from": previous_severity.value,
            "escalation_time": datetime.utcnow().isoformat(),
        }

        logger.info(f"Alert {alert.id} escalated: {reason}")


async def check_payroll_cascade(db: AsyncSession, user_id: str) -> List[DetectionAlert]:
    """
    Special escalation check: Do late invoices affect payroll?

    This is called when:
    1. A payroll safety alert is created
    2. A late payment alert is created

    If late payments would cover payroll shortfall, escalate them.
    """
    # Get active payroll safety alert
    result = await db.execute(
        select(DetectionAlert)
        .where(DetectionAlert.user_id == user_id)
        .where(DetectionAlert.detection_type == DetectionType.PAYROLL_SAFETY)
        .where(DetectionAlert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]))
    )
    payroll_alert = result.scalar_one_or_none()

    if not payroll_alert:
        return []

    shortfall = payroll_alert.context_data.get("shortfall", 0)
    if shortfall <= 0:
        return []

    # Get late payment alerts
    result = await db.execute(
        select(DetectionAlert)
        .where(DetectionAlert.user_id == user_id)
        .where(DetectionAlert.detection_type == DetectionType.LATE_PAYMENT)
        .where(DetectionAlert.status == AlertStatus.ACTIVE)
        .where(DetectionAlert.severity != AlertSeverity.EMERGENCY)
    )
    late_payments = result.scalars().all()

    escalated = []
    total_late = 0

    for alert in late_payments:
        amount = alert.context_data.get("amount", 0)
        total_late += amount

        # If this invoice alone covers significant portion, escalate it
        if amount >= shortfall * 0.3:
            alert.severity = AlertSeverity.EMERGENCY
            alert.escalation_count += 1
            alert.last_escalated_at = datetime.utcnow()
            alert.context_data = {
                **alert.context_data,
                "escalation_reason": "Needed to cover payroll",
                "payroll_shortfall": shortfall,
            }
            escalated.append(alert)

    # If combined late payments would cover shortfall, escalate all
    if total_late >= shortfall and len(late_payments) > 0:
        for alert in late_payments:
            if alert not in escalated:
                alert.severity = AlertSeverity.EMERGENCY
                alert.escalation_count += 1
                alert.last_escalated_at = datetime.utcnow()
                alert.context_data = {
                    **alert.context_data,
                    "escalation_reason": "Combined with other invoices to cover payroll",
                }
                escalated.append(alert)

    return escalated


async def check_deadline_cascade(db: AsyncSession, user_id: str) -> List[DetectionAlert]:
    """
    Special escalation check: Are deadlines clustering?

    Escalates alerts when multiple deadlines fall in the same week,
    creating a "payment timing conflict" situation.
    """
    now = datetime.utcnow()
    week_ahead = now + timedelta(days=7)

    # Get alerts with deadlines in the next week
    result = await db.execute(
        select(DetectionAlert)
        .where(DetectionAlert.user_id == user_id)
        .where(DetectionAlert.status == AlertStatus.ACTIVE)
        .where(DetectionAlert.deadline != None)
        .where(DetectionAlert.deadline <= week_ahead)
        .where(DetectionAlert.severity != AlertSeverity.EMERGENCY)
    )
    upcoming_deadlines = result.scalars().all()

    if len(upcoming_deadlines) < 3:
        return []

    # Calculate total cash impact
    total_impact = sum(
        abs(a.cash_impact) for a in upcoming_deadlines
        if a.cash_impact is not None
    )

    escalated = []

    # If significant cash impact from clustered deadlines, escalate all
    if total_impact > 10000 or len(upcoming_deadlines) >= 5:
        for alert in upcoming_deadlines:
            alert.severity = AlertSeverity.EMERGENCY
            alert.escalation_count += 1
            alert.last_escalated_at = now
            alert.context_data = {
                **alert.context_data,
                "escalation_reason": f"Clustered with {len(upcoming_deadlines)} other deadlines this week",
                "cluster_total_impact": total_impact,
            }
            escalated.append(alert)

    return escalated
