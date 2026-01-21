"""
Escalation Rules Engine - V4 Architecture

Implements priority sequencing and escalation rules for prepared actions.
Actions can escalate from lower urgency tiers to higher tiers based on:
1. Late invoice affects next payroll
2. Deadline crosses 3-day threshold
3. Cash drops below emergency buffer
4. Multiple obligations cluster (>40% of cash)

Urgency Tiers:
- EMERGENCY (Red): Must act today to prevent failure
- THIS_WEEK (Yellow): Needs attention soon, not urgent
- UPCOMING (Green): Scheduled for future, monitoring only
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.detection.models import AlertSeverity, DetectionAlert
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.expenses.models import ExpenseBucket
from app.data.balances.models import CashAccount
from .models import PreparedAction, ActionStatus, ActionType
from .context import get_cash_context, get_payroll_context

logger = logging.getLogger(__name__)


class EscalationReason(str, Enum):
    """Reasons for urgency escalation."""
    INVOICE_AFFECTS_PAYROLL = "invoice_affects_payroll"
    DEADLINE_WITHIN_3_DAYS = "deadline_within_3_days"
    CASH_BELOW_EMERGENCY_BUFFER = "cash_below_emergency_buffer"
    OBLIGATIONS_CLUSTER = "obligations_cluster"
    TIME_BASED_ESCALATION = "time_based_escalation"


@dataclass
class EscalationResult:
    """Result of an escalation check."""
    should_escalate: bool
    from_severity: AlertSeverity
    to_severity: AlertSeverity
    reason: Optional[EscalationReason] = None
    reason_detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "escalated": self.should_escalate,
            "from": self.from_severity.value,
            "to": self.to_severity.value,
            "reason": self.reason.value if self.reason else None,
            "detail": self.reason_detail,
        }


class EscalationEngine:
    """
    Escalation Rules Engine.

    Checks actions against escalation rules and updates urgency
    when conditions are met.
    """

    # Buffer thresholds
    EMERGENCY_BUFFER_MULTIPLIER = 1.1  # 10% above next obligation
    CLUSTER_THRESHOLD_PERCENT = 0.40   # 40% of available cash
    DAYS_THRESHOLD_EMERGENCY = 3       # Escalate when deadline within 3 days
    PAYROLL_DAYS_THRESHOLD = 7         # Payroll within 7 days triggers escalation

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self._cash_context: Optional[Dict[str, Any]] = None
        self._payroll_context: Optional[Dict[str, Any]] = None

    async def get_cash_context(self) -> Dict[str, Any]:
        """Get cached cash context."""
        if self._cash_context is None:
            self._cash_context = await get_cash_context(self.db, self.user_id)
        return self._cash_context

    async def get_payroll_context(self) -> Dict[str, Any]:
        """Get cached payroll context."""
        if self._payroll_context is None:
            self._payroll_context = await get_payroll_context(self.db, self.user_id)
        return self._payroll_context

    async def check_all_escalations(
        self,
        action: PreparedAction,
        current_severity: AlertSeverity,
    ) -> EscalationResult:
        """
        Check all escalation rules for an action.

        Returns the highest priority escalation if any apply.
        """
        # Already at emergency level, no escalation needed
        if current_severity == AlertSeverity.EMERGENCY:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        # Check rules in priority order (highest impact first)
        escalation_checks = [
            self._check_payroll_impact,
            self._check_cash_below_emergency_buffer,
            self._check_deadline_threshold,
            self._check_obligations_cluster,
        ]

        for check in escalation_checks:
            result = await check(action, current_severity)
            if result.should_escalate:
                return result

        # No escalation needed
        return EscalationResult(
            should_escalate=False,
            from_severity=current_severity,
            to_severity=current_severity,
        )

    async def _check_payroll_impact(
        self,
        action: PreparedAction,
        current_severity: AlertSeverity,
    ) -> EscalationResult:
        """
        Rule 1: Late invoice affects next payroll.

        IF Invoice.Amount affects Payroll_Safety AND Payroll.Date <= 7 days
        THEN escalate from This Week -> Emergency
        """
        # Only applies to invoice-related actions
        if action.action_type not in [
            ActionType.INVOICE_FOLLOW_UP,
            ActionType.PAYMENT_REMINDER,
            ActionType.COLLECTION_ESCALATION,
        ]:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        payroll_context = await self.get_payroll_context()

        # Check if payroll exists and is within threshold
        if not payroll_context.get("has_payroll"):
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        next_payroll = payroll_context.get("next_payroll")
        if not next_payroll:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        days_until_payroll = next_payroll.get("days_until", 999)

        # Only escalate if payroll is within 7 days
        if days_until_payroll > self.PAYROLL_DAYS_THRESHOLD:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        # Check if this invoice amount would help cover payroll
        buffer_status = payroll_context.get("buffer_status", "safe")
        shortfall = payroll_context.get("shortfall", 0)

        # Get invoice amount from action options
        invoice_amount = 0
        if action.options:
            for option in action.options:
                cash_impact = option.cash_impact or 0
                if cash_impact > 0:  # Positive impact = money coming in
                    invoice_amount = max(invoice_amount, cash_impact)

        # Escalate if:
        # 1. Payroll is at risk or has shortfall
        # 2. This invoice would materially help (covers at least 20% of shortfall)
        if buffer_status in ["at_risk", "shortfall"]:
            if shortfall > 0 and invoice_amount >= shortfall * 0.2:
                return EscalationResult(
                    should_escalate=True,
                    from_severity=current_severity,
                    to_severity=AlertSeverity.EMERGENCY,
                    reason=EscalationReason.INVOICE_AFFECTS_PAYROLL,
                    reason_detail=f"Collecting ${invoice_amount:,.0f} helps cover ${shortfall:,.0f} payroll shortfall due in {days_until_payroll} days",
                )

        return EscalationResult(
            should_escalate=False,
            from_severity=current_severity,
            to_severity=current_severity,
        )

    async def _check_deadline_threshold(
        self,
        action: PreparedAction,
        current_severity: AlertSeverity,
    ) -> EscalationResult:
        """
        Rule 2: Deadline crosses 3-day threshold.

        IF Obligation.Due_Date - Current_Date <= 3
        THEN escalate from This Week -> Emergency
        """
        if not action.deadline:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        now = datetime.utcnow()
        days_until_deadline = (action.deadline - now).days

        if days_until_deadline <= self.DAYS_THRESHOLD_EMERGENCY:
            return EscalationResult(
                should_escalate=True,
                from_severity=current_severity,
                to_severity=AlertSeverity.EMERGENCY,
                reason=EscalationReason.DEADLINE_WITHIN_3_DAYS,
                reason_detail=f"Deadline in {days_until_deadline} days (threshold: {self.DAYS_THRESHOLD_EMERGENCY})",
            )

        return EscalationResult(
            should_escalate=False,
            from_severity=current_severity,
            to_severity=current_severity,
        )

    async def _check_cash_below_emergency_buffer(
        self,
        action: PreparedAction,
        current_severity: AlertSeverity,
    ) -> EscalationResult:
        """
        Rule 3: Cash drops below emergency buffer.

        IF Cash < (Next_Obligation + Emergency_Buffer)
        THEN escalate from This Week -> Emergency
        """
        cash_context = await self.get_cash_context()
        total_cash = cash_context.get("total_cash", 0)

        # Get next obligation amount (within 7 days)
        obligations_7d = cash_context.get("obligations_7d", 0)

        if obligations_7d <= 0:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        # Emergency buffer = next obligation + 10%
        emergency_threshold = obligations_7d * self.EMERGENCY_BUFFER_MULTIPLIER

        if total_cash < emergency_threshold:
            shortfall = emergency_threshold - total_cash
            return EscalationResult(
                should_escalate=True,
                from_severity=current_severity,
                to_severity=AlertSeverity.EMERGENCY,
                reason=EscalationReason.CASH_BELOW_EMERGENCY_BUFFER,
                reason_detail=f"Cash ${total_cash:,.0f} is ${shortfall:,.0f} below emergency buffer (${emergency_threshold:,.0f})",
            )

        return EscalationResult(
            should_escalate=False,
            from_severity=current_severity,
            to_severity=current_severity,
        )

    async def _check_obligations_cluster(
        self,
        action: PreparedAction,
        current_severity: AlertSeverity,
    ) -> EscalationResult:
        """
        Rule 4: Multiple obligations cluster.

        IF Weekly_Obligations > 40% of Available_Cash
        THEN escalate from Upcoming -> This Week

        Note: This only escalates to THIS_WEEK, not EMERGENCY.
        """
        # Only applies to UPCOMING severity
        if current_severity != AlertSeverity.UPCOMING:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        cash_context = await self.get_cash_context()
        total_cash = cash_context.get("total_cash", 0)
        obligations_7d = cash_context.get("obligations_7d", 0)

        if total_cash <= 0:
            return EscalationResult(
                should_escalate=False,
                from_severity=current_severity,
                to_severity=current_severity,
            )

        cluster_percent = obligations_7d / total_cash

        if cluster_percent > self.CLUSTER_THRESHOLD_PERCENT:
            return EscalationResult(
                should_escalate=True,
                from_severity=current_severity,
                to_severity=AlertSeverity.THIS_WEEK,
                reason=EscalationReason.OBLIGATIONS_CLUSTER,
                reason_detail=f"Weekly obligations ${obligations_7d:,.0f} are {cluster_percent*100:.0f}% of cash (threshold: {self.CLUSTER_THRESHOLD_PERCENT*100:.0f}%)",
            )

        return EscalationResult(
            should_escalate=False,
            from_severity=current_severity,
            to_severity=current_severity,
        )

    async def apply_escalation(
        self,
        action: PreparedAction,
        escalation: EscalationResult,
    ) -> PreparedAction:
        """
        Apply escalation to an action.

        Updates the action's deadline and alert severity if applicable.
        Records escalation in the action's context.
        """
        if not escalation.should_escalate:
            return action

        # Update the associated alert's severity
        if action.alert_id:
            result = await self.db.execute(
                select(DetectionAlert).where(DetectionAlert.id == action.alert_id)
            )
            alert = result.scalar_one_or_none()

            if alert:
                alert.severity = escalation.to_severity
                alert.escalation_count = (alert.escalation_count or 0) + 1
                alert.last_escalated_at = datetime.utcnow()

                # Add escalation to context_data
                context = alert.context_data or {}
                escalation_history = context.get("escalation_history", [])
                escalation_history.append({
                    "from": escalation.from_severity.value,
                    "to": escalation.to_severity.value,
                    "reason": escalation.reason.value if escalation.reason else None,
                    "detail": escalation.reason_detail,
                    "escalated_at": datetime.utcnow().isoformat(),
                })
                context["escalation_history"] = escalation_history
                alert.context_data = context

        # Adjust deadline for emergency escalations
        if escalation.to_severity == AlertSeverity.EMERGENCY:
            # Emergency actions should be addressed within 8 hours
            action.deadline = datetime.utcnow() + timedelta(hours=8)

        logger.info(
            f"Escalated action {action.id} from {escalation.from_severity.value} "
            f"to {escalation.to_severity.value}: {escalation.reason_detail}"
        )

        return action

    async def run_escalation_check(
        self,
        actions: Optional[List[PreparedAction]] = None,
    ) -> Dict[str, Any]:
        """
        Run escalation checks on all pending actions or provided list.

        Returns summary of escalations applied.
        """
        if actions is None:
            # Get all pending actions
            result = await self.db.execute(
                select(PreparedAction)
                .where(PreparedAction.user_id == self.user_id)
                .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
            )
            actions = result.scalars().all()

        escalations_applied = []

        for action in actions:
            # Get current severity from alert
            current_severity = AlertSeverity.THIS_WEEK  # Default

            if action.alert_id:
                alert_result = await self.db.execute(
                    select(DetectionAlert).where(DetectionAlert.id == action.alert_id)
                )
                alert = alert_result.scalar_one_or_none()
                if alert:
                    current_severity = alert.severity

            # Check for escalation
            escalation = await self.check_all_escalations(action, current_severity)

            if escalation.should_escalate:
                await self.apply_escalation(action, escalation)
                escalations_applied.append({
                    "action_id": action.id,
                    "action_type": action.action_type.value,
                    **escalation.to_dict(),
                })

        return {
            "actions_checked": len(actions),
            "escalations_applied": len(escalations_applied),
            "escalations": escalations_applied,
        }


async def run_escalation_sweep(
    db: AsyncSession,
    user_id: str,
) -> Dict[str, Any]:
    """
    Run a complete escalation sweep for a user.

    This should be called periodically (e.g., hourly) to catch
    actions that need escalation due to time passing.
    """
    engine = EscalationEngine(db, user_id)
    return await engine.run_escalation_check()