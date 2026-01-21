"""
Detection Engine - V4 Architecture

The core engine that runs detection rules against current data
and generates alerts when thresholds are breached.

This engine implements all 12 detection types:
1. LATE_PAYMENT - Invoices overdue
2. UNEXPECTED_REVENUE - Payment variance
3. UNEXPECTED_EXPENSE - Expense spike
4. CLIENT_CHURN - Revenue at risk
5. REVENUE_VARIANCE - Actual vs expected
6. PAYMENT_TIMING_CONFLICT - Obligation clustering
7. VENDOR_TERMS_EXPIRING - Payment deadline approaching
8. STATUTORY_DEADLINE - Tax/regulatory deadlines
9. BUFFER_BREACH - Cash below threshold
10. RUNWAY_THRESHOLD - Runway warning
11. PAYROLL_SAFETY - Payroll at risk
12. HEADCOUNT_CHANGE - New hire detected
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data.user_config.models import UserConfiguration, SafetyMode
from app.data.user_config.routes import get_or_create_config
from .models import DetectionType, DetectionAlert, DetectionRule, AlertSeverity, AlertStatus

logger = logging.getLogger(__name__)


class DetectionEngine:
    """
    Runs detection rules and generates alerts.

    This engine is called:
    - On a schedule (critical rules every 5 min, routine every hour)
    - After data sync (Xero, bank feeds)
    - On-demand when user opens dashboard
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self._config: Optional[UserConfiguration] = None

    async def get_config(self) -> UserConfiguration:
        """Get user configuration, caching for performance."""
        if self._config is None:
            self._config = await get_or_create_config(self.db, self.user_id)
        return self._config

    async def run_all_detections(self) -> List[DetectionAlert]:
        """Run all enabled detection rules and return new alerts."""
        config = await self.get_config()

        # Get user's enabled rules
        result = await self.db.execute(
            select(DetectionRule)
            .where(DetectionRule.user_id == self.user_id)
            .where(DetectionRule.enabled == True)
        )
        rules = result.scalars().all()

        new_alerts = []
        for rule in rules:
            try:
                alerts = await self._run_detection(rule, config)
                for alert in alerts:
                    self.db.add(alert)
                new_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Detection {rule.detection_type} failed for user {self.user_id}: {e}")
                # Continue with other detections

        return new_alerts

    async def run_detection_type(self, detection_type: DetectionType) -> List[DetectionAlert]:
        """Run a specific detection type."""
        config = await self.get_config()

        result = await self.db.execute(
            select(DetectionRule)
            .where(DetectionRule.user_id == self.user_id)
            .where(DetectionRule.detection_type == detection_type)
            .where(DetectionRule.enabled == True)
        )
        rule = result.scalar_one_or_none()

        if not rule:
            return []

        alerts = await self._run_detection(rule, config)
        for alert in alerts:
            self.db.add(alert)

        return alerts

    async def run_critical_detections(self) -> List[DetectionAlert]:
        """Run only critical detections (payroll_safety, buffer_breach)."""
        config = await self.get_config()
        critical_types = [
            DetectionType.PAYROLL_SAFETY,
            DetectionType.BUFFER_BREACH,
        ]

        result = await self.db.execute(
            select(DetectionRule)
            .where(DetectionRule.user_id == self.user_id)
            .where(DetectionRule.detection_type.in_(critical_types))
            .where(DetectionRule.enabled == True)
        )
        rules = result.scalars().all()

        new_alerts = []
        for rule in rules:
            try:
                alerts = await self._run_detection(rule, config)
                for alert in alerts:
                    self.db.add(alert)
                new_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Critical detection {rule.detection_type} failed: {e}")

        return new_alerts

    async def _run_detection(
        self, rule: DetectionRule, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """Run a single detection rule and return any new alerts."""
        detection_type = rule.detection_type
        thresholds = rule.thresholds

        # Route to appropriate detector
        detector_map = {
            DetectionType.LATE_PAYMENT: self._detect_late_payments,
            DetectionType.UNEXPECTED_REVENUE: self._detect_unexpected_revenue,
            DetectionType.UNEXPECTED_EXPENSE: self._detect_unexpected_expenses,
            DetectionType.CLIENT_CHURN: self._detect_client_churn,
            DetectionType.REVENUE_VARIANCE: self._detect_revenue_variance,
            DetectionType.PAYMENT_TIMING_CONFLICT: self._detect_payment_conflicts,
            DetectionType.VENDOR_TERMS_EXPIRING: self._detect_vendor_terms,
            DetectionType.STATUTORY_DEADLINE: self._detect_statutory_deadlines,
            DetectionType.BUFFER_BREACH: self._detect_buffer_breach,
            DetectionType.RUNWAY_THRESHOLD: self._detect_runway_threshold,
            DetectionType.PAYROLL_SAFETY: self._detect_payroll_safety,
            DetectionType.HEADCOUNT_CHANGE: self._detect_headcount_change,
        }

        detector = detector_map.get(detection_type)
        if not detector:
            logger.warning(f"No detector for type: {detection_type}")
            return []

        return await detector(rule, thresholds, config)

    # ==========================================================================
    # Detection: LATE_PAYMENT
    # ==========================================================================
    async def _detect_late_payments(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect invoices that are overdue and check if they impact obligations.

        OBLIGATION-FOCUSED APPROACH:
        - Only generate alerts if late payment impacts an upcoming obligation
        - Title focuses on the obligation at risk, not the late invoice
        - "Caused by" context links to the late client payment
        - If no obligation impact, don't generate alert (just late invoice monitoring)

        Checks ObligationSchedules (revenue type) against due dates,
        evaluates impact on upcoming expense obligations.
        """
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement
        from app.data.clients.models import Client
        from app.data.expenses.models import ExpenseBucket
        from app.data.balances.models import CashAccount

        # Use config threshold if rule doesn't override
        days_threshold = thresholds.get("days_overdue", config.late_payment_threshold_days)
        min_amount = thresholds.get("min_amount", 0)

        # Apply safety mode multiplier
        multiplier = config.get_threshold_multiplier()
        days_threshold = int(days_threshold * multiplier)

        today = date.today()
        cutoff_date = today - timedelta(days=days_threshold)

        # Find overdue schedules for revenue obligations
        result = await self.db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type == "revenue")
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            .where(ObligationSchedule.due_date <= cutoff_date)
            .where(ObligationSchedule.estimated_amount >= min_amount)
            .options(selectinload(ObligationSchedule.obligation))
        )
        overdue_schedules = result.scalars().all()

        if not overdue_schedules:
            return []

        # Get current cash to evaluate impact
        cash_result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == self.user_id)
        )
        current_cash = float(cash_result.scalar() or 0)

        # Get upcoming obligations (next 14 days) to check if late payments impact them
        upcoming_obligations_result = await self.db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .outerjoin(ExpenseBucket, ObligationAgreement.expense_bucket_id == ExpenseBucket.id)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type != "revenue")
            .where(ObligationSchedule.due_date >= today)
            .where(ObligationSchedule.due_date <= today + timedelta(days=14))
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            .options(selectinload(ObligationSchedule.obligation))
        )
        upcoming_obligations = upcoming_obligations_result.scalars().all()

        # Calculate total upcoming obligations
        total_upcoming = sum(float(ob.estimated_amount) for ob in upcoming_obligations)

        # Calculate total overdue revenue
        total_overdue = sum(float(s.estimated_amount) for s in overdue_schedules)

        # Check if late payments cause obligation shortfall
        projected_cash = current_cash  # Cash if all overdue paid
        projected_cash_without_overdue = current_cash - total_overdue  # Current reality

        alerts = []

        # Group obligations by category (payroll, tax_obligation, fixed costs)
        obligation_categories = {}
        for ob in upcoming_obligations:
            category = "fixed_costs"
            obligation_name = "Fixed costs"

            if ob.obligation and ob.obligation.expense_bucket_id:
                bucket_result = await self.db.execute(
                    select(ExpenseBucket).where(ExpenseBucket.id == ob.obligation.expense_bucket_id)
                )
                bucket = bucket_result.scalar_one_or_none()
                if bucket:
                    if bucket.category == "payroll":
                        category = "payroll"
                        obligation_name = "Payroll"
                    elif bucket.category == "tax_obligation":
                        category = "tax_obligation"
                        obligation_name = "VAT/Tax payment"
                    else:
                        obligation_name = bucket.name or "Fixed costs"

            if category not in obligation_categories:
                obligation_categories[category] = {
                    "name": obligation_name,
                    "total": 0,
                    "due_date": ob.due_date,
                    "schedules": []
                }
            obligation_categories[category]["total"] += float(ob.estimated_amount)
            obligation_categories[category]["schedules"].append(ob)
            # Track earliest due date
            if ob.due_date < obligation_categories[category]["due_date"]:
                obligation_categories[category]["due_date"] = ob.due_date

        # Check each category for shortfall caused by late payments
        cash_after_previous = current_cash
        for category, data in sorted(obligation_categories.items(), key=lambda x: x[1]["due_date"]):
            obligation_amount = data["total"]
            obligation_name = data["name"]
            due_date = data["due_date"]
            days_until_due = (due_date - today).days

            # Check if this obligation is underfunded
            shortfall = obligation_amount - cash_after_previous

            if shortfall > 0:
                # Find which overdue payments are causing this
                causing_payments = []
                causing_total = 0
                for schedule in overdue_schedules:
                    days_overdue = (today - schedule.due_date).days
                    client_name = None
                    if schedule.obligation and schedule.obligation.client_id:
                        client_result = await self.db.execute(
                            select(Client).where(Client.id == schedule.obligation.client_id)
                        )
                        client = client_result.scalar_one_or_none()
                        if client:
                            client_name = client.name

                    causing_payments.append({
                        "schedule_id": str(schedule.id),
                        "client_name": client_name,
                        "amount": float(schedule.estimated_amount),
                        "days_overdue": days_overdue,
                    })
                    causing_total += float(schedule.estimated_amount)

                # Build "caused by" context
                caused_by_text = []
                for cp in causing_payments[:3]:  # Top 3 causes
                    if cp["client_name"]:
                        caused_by_text.append(f"{cp['client_name']} payment {cp['days_overdue']}d overdue (${cp['amount']:,.0f})")
                    else:
                        caused_by_text.append(f"Invoice {cp['days_overdue']}d overdue (${cp['amount']:,.0f})")

                # Check for existing alert
                existing = await self._get_existing_alert(
                    DetectionType.LATE_PAYMENT,
                    {"obligation_category": category, "impact_type": "underfunded"}
                )
                if existing:
                    cash_after_previous -= obligation_amount
                    continue

                # Determine severity based on obligation type and timing
                if category == "payroll":
                    severity = AlertSeverity.EMERGENCY
                elif category == "tax_obligation":
                    severity = AlertSeverity.EMERGENCY if days_until_due <= 7 else AlertSeverity.THIS_WEEK
                elif days_until_due <= 3:
                    severity = AlertSeverity.EMERGENCY
                else:
                    severity = AlertSeverity.THIS_WEEK

                # Format due date context
                if days_until_due == 0:
                    due_text = "due today"
                elif days_until_due == 1:
                    due_text = "due tomorrow"
                elif due_date.weekday() == 4 and days_until_due <= 5:  # Friday
                    due_text = "due Friday"
                else:
                    due_text = f"due {due_date.strftime('%b %d')}"

                # Create OBLIGATION-FOCUSED alert
                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.LATE_PAYMENT,
                    severity=severity,
                    title=f"{obligation_name} underfunded by ${shortfall:,.0f} - {due_text}",
                    description=f"Caused by: {'; '.join(caused_by_text[:2])}" if caused_by_text else None,
                    context_data={
                        "obligation_category": category,
                        "obligation_name": obligation_name,
                        "obligation_amount": obligation_amount,
                        "shortfall": shortfall,
                        "due_date": due_date.isoformat(),
                        "days_until_due": days_until_due,
                        "impact_type": "underfunded",
                        "causing_payments": causing_payments,
                        "caused_by_summary": caused_by_text,
                        "current_cash": current_cash,
                    },
                    cash_impact=-shortfall,
                    urgency_score=min(100, 70 + (14 - days_until_due) * 2),
                    deadline=datetime.combine(due_date, datetime.min.time()),
                )
                alerts.append(alert)

            # Deduct from cash for next iteration
            cash_after_previous -= obligation_amount

        return alerts

    # ==========================================================================
    # Detection: UNEXPECTED_REVENUE
    # ==========================================================================
    async def _detect_unexpected_revenue(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect payment variances vs invoiced amounts.

        Checks PaymentEvents against ObligationSchedules for significant differences.
        """
        from app.data.obligations.models import PaymentEvent, ObligationSchedule

        variance_threshold_pct = thresholds.get("variance_percent", 10)

        # Get recent payments with variance tracking
        result = await self.db.execute(
            select(PaymentEvent)
            .where(PaymentEvent.user_id == self.user_id)
            .where(PaymentEvent.variance_vs_expected != None)
            .where(PaymentEvent.payment_date >= date.today() - timedelta(days=30))
            .order_by(PaymentEvent.payment_date.desc())
        )
        payments = result.scalars().all()

        alerts = []
        for payment in payments:
            if payment.variance_vs_expected is None or payment.schedule_id is None:
                continue

            # Get expected amount from schedule
            schedule_result = await self.db.execute(
                select(ObligationSchedule).where(ObligationSchedule.id == payment.schedule_id)
            )
            schedule = schedule_result.scalar_one_or_none()
            if not schedule:
                continue

            expected = float(schedule.estimated_amount)
            actual = float(payment.amount)
            variance_pct = abs((actual - expected) / expected * 100) if expected > 0 else 0

            if variance_pct >= variance_threshold_pct:
                existing = await self._get_existing_alert(
                    DetectionType.UNEXPECTED_REVENUE,
                    {"payment_id": str(payment.id)}
                )
                if existing:
                    continue

                is_over = actual > expected
                severity = AlertSeverity.THIS_WEEK if is_over else AlertSeverity.UPCOMING

                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.UNEXPECTED_REVENUE,
                    severity=severity,
                    title=f"{'Overpayment' if is_over else 'Underpayment'} of ${abs(actual - expected):,.2f}",
                    description=f"Received ${actual:,.2f} vs expected ${expected:,.2f} ({variance_pct:.1f}% variance)",
                    context_data={
                        "payment_id": str(payment.id),
                        "schedule_id": str(payment.schedule_id),
                        "expected_amount": expected,
                        "actual_amount": actual,
                        "variance_amount": actual - expected,
                        "variance_percent": variance_pct,
                        "payment_date": payment.payment_date.isoformat(),
                    },
                    cash_impact=actual - expected,
                    urgency_score=30 if is_over else 60,
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: UNEXPECTED_EXPENSE
    # ==========================================================================
    async def _detect_unexpected_expenses(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect expense spikes above rolling average.

        Compares recent expenses to 3-month average by category.
        """
        from app.data.obligations.models import PaymentEvent, ObligationAgreement
        from app.data.expenses.models import ExpenseBucket

        variance_pct = thresholds.get("variance_percent", float(config.unexpected_expense_threshold_pct))
        lookback_months = thresholds.get("lookback_months", 3)

        # Apply safety mode
        variance_pct = variance_pct * config.get_threshold_multiplier()

        today = date.today()
        lookback_start = today - timedelta(days=lookback_months * 30)
        recent_start = today - timedelta(days=30)

        # Get expense buckets
        bucket_result = await self.db.execute(
            select(ExpenseBucket).where(ExpenseBucket.user_id == self.user_id)
        )
        buckets = bucket_result.scalars().all()

        alerts = []
        for bucket in buckets:
            # Get historical average payments for this bucket
            hist_result = await self.db.execute(
                select(func.avg(PaymentEvent.amount))
                .join(ObligationAgreement)
                .where(ObligationAgreement.expense_bucket_id == bucket.id)
                .where(PaymentEvent.payment_date >= lookback_start)
                .where(PaymentEvent.payment_date < recent_start)
            )
            hist_avg = hist_result.scalar() or 0

            if float(hist_avg) == 0:
                continue

            # Get recent month total
            recent_result = await self.db.execute(
                select(func.sum(PaymentEvent.amount))
                .join(ObligationAgreement)
                .where(ObligationAgreement.expense_bucket_id == bucket.id)
                .where(PaymentEvent.payment_date >= recent_start)
            )
            recent_total = recent_result.scalar() or 0

            if float(recent_total) == 0:
                continue

            # Calculate variance
            actual_variance_pct = ((float(recent_total) - float(hist_avg)) / float(hist_avg)) * 100

            if actual_variance_pct >= variance_pct:
                existing = await self._get_existing_alert(
                    DetectionType.UNEXPECTED_EXPENSE,
                    {"bucket_id": str(bucket.id), "month": today.strftime("%Y-%m")}
                )
                if existing:
                    continue

                severity = AlertSeverity.EMERGENCY if actual_variance_pct >= 50 else AlertSeverity.THIS_WEEK

                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.UNEXPECTED_EXPENSE,
                    severity=severity,
                    title=f"Expense spike: {bucket.name} (+{actual_variance_pct:.0f}%)",
                    description=f"${float(recent_total):,.2f} this month vs ${float(hist_avg):,.2f} average",
                    context_data={
                        "bucket_id": str(bucket.id),
                        "bucket_name": bucket.name,
                        "category": bucket.category,
                        "month": today.strftime("%Y-%m"),
                        "recent_total": float(recent_total),
                        "historical_avg": float(hist_avg),
                        "variance_percent": actual_variance_pct,
                    },
                    cash_impact=-(float(recent_total) - float(hist_avg)),
                    urgency_score=min(100, 40 + actual_variance_pct),
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: CLIENT_CHURN
    # ==========================================================================
    async def _detect_client_churn(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Flag revenue at risk from client cancellations or payment behavior changes.

        Looks for clients with high churn risk or deteriorating payment patterns.
        """
        from app.data.clients.models import Client

        revenue_at_risk_pct = thresholds.get("revenue_at_risk_percent", 5)

        # Find clients with high churn risk or significantly late payments
        result = await self.db.execute(
            select(Client)
            .where(Client.user_id == self.user_id)
            .where(Client.status == "active")
            .where(
                or_(
                    Client.churn_risk == "high",
                    Client.avg_payment_delay_days > 30,
                    Client.risk_level == "critical"
                )
            )
        )
        risky_clients = result.scalars().all()

        alerts = []
        for client in risky_clients:
            existing = await self._get_existing_alert(
                DetectionType.CLIENT_CHURN,
                {"client_id": str(client.id)}
            )
            if existing:
                continue

            # Calculate revenue at risk
            revenue_pct = float(client.revenue_percent or 0)

            if revenue_pct < revenue_at_risk_pct and client.churn_risk != "high":
                continue

            reasons = []
            if client.churn_risk == "high":
                reasons.append("High churn risk flagged")
            if client.avg_payment_delay_days and client.avg_payment_delay_days > 30:
                reasons.append(f"Payments averaging {client.avg_payment_delay_days} days late")
            if client.risk_level == "critical":
                reasons.append("Critical risk level")

            severity = AlertSeverity.EMERGENCY if revenue_pct >= 15 else AlertSeverity.THIS_WEEK

            alert = DetectionAlert(
                user_id=self.user_id,
                rule_id=rule.id,
                detection_type=DetectionType.CLIENT_CHURN,
                severity=severity,
                title=f"Revenue at risk: {client.name}",
                description=f"{revenue_pct:.1f}% of revenue at risk. {'; '.join(reasons)}",
                context_data={
                    "client_id": str(client.id),
                    "client_name": client.name,
                    "revenue_percent": revenue_pct,
                    "churn_risk": client.churn_risk,
                    "avg_payment_delay_days": client.avg_payment_delay_days,
                    "reasons": reasons,
                },
                cash_impact=None,  # Would calculate from billing_config
                urgency_score=60 + revenue_pct,
            )
            alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: REVENUE_VARIANCE
    # ==========================================================================
    async def _detect_revenue_variance(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Track actual vs expected revenue at aggregate level.

        Compares monthly revenue to forecast.
        """
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement, PaymentEvent

        variance_threshold_pct = thresholds.get("variance_percent", 15)

        today = date.today()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Get expected revenue this month
        expected_result = await self.db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type == "revenue")
            .where(ObligationSchedule.due_date >= month_start)
            .where(ObligationSchedule.due_date <= month_end)
        )
        expected_revenue = float(expected_result.scalar() or 0)

        # Get actual revenue received this month
        actual_result = await self.db.execute(
            select(func.sum(PaymentEvent.amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type == "revenue")
            .where(PaymentEvent.payment_date >= month_start)
            .where(PaymentEvent.payment_date <= today)
        )
        actual_revenue = float(actual_result.scalar() or 0)

        if expected_revenue == 0:
            return []

        variance_pct = ((actual_revenue - expected_revenue) / expected_revenue) * 100

        if abs(variance_pct) < variance_threshold_pct:
            return []

        existing = await self._get_existing_alert(
            DetectionType.REVENUE_VARIANCE,
            {"month": month_start.isoformat()}
        )
        if existing:
            return []

        is_over = variance_pct > 0
        severity = AlertSeverity.UPCOMING if is_over else AlertSeverity.THIS_WEEK

        alert = DetectionAlert(
            user_id=self.user_id,
            rule_id=rule.id,
            detection_type=DetectionType.REVENUE_VARIANCE,
            severity=severity,
            title=f"Revenue {'ahead' if is_over else 'behind'} by {abs(variance_pct):.0f}%",
            description=f"${actual_revenue:,.0f} received vs ${expected_revenue:,.0f} expected this month",
            context_data={
                "month": month_start.isoformat(),
                "expected_revenue": expected_revenue,
                "actual_revenue": actual_revenue,
                "variance_amount": actual_revenue - expected_revenue,
                "variance_percent": variance_pct,
            },
            cash_impact=actual_revenue - expected_revenue,
            urgency_score=40 if is_over else 70,
        )

        return [alert]

    # ==========================================================================
    # Detection: PAYMENT_TIMING_CONFLICT
    # ==========================================================================
    async def _detect_payment_conflicts(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect weeks where obligations cluster and strain cash.

        Flags when more than threshold % of cash is due in a single week.
        """
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement
        from app.data.balances.models import CashAccount

        max_weekly_pct = thresholds.get("max_weekly_percent", float(config.payment_cluster_threshold_pct))

        # Get current cash
        cash_result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == self.user_id)
        )
        total_cash = float(cash_result.scalar() or 0)

        if total_cash <= 0:
            return []

        # Look at next 4 weeks
        today = date.today()
        alerts = []

        for week_offset in range(4):
            week_start = today + timedelta(days=7 * week_offset)
            week_end = week_start + timedelta(days=6)

            # Get obligations due this week (expenses only)
            result = await self.db.execute(
                select(func.sum(ObligationSchedule.estimated_amount))
                .join(ObligationAgreement)
                .where(ObligationAgreement.user_id == self.user_id)
                .where(ObligationAgreement.obligation_type != "revenue")
                .where(ObligationSchedule.due_date >= week_start)
                .where(ObligationSchedule.due_date <= week_end)
                .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            )
            week_total = float(result.scalar() or 0)

            week_pct = (week_total / total_cash) * 100

            if week_pct >= max_weekly_pct:
                week_key = week_start.isocalendar()[:2]  # (year, week_number)
                existing = await self._get_existing_alert(
                    DetectionType.PAYMENT_TIMING_CONFLICT,
                    {"week": f"{week_key[0]}-W{week_key[1]:02d}"}
                )
                if existing:
                    continue

                severity = AlertSeverity.EMERGENCY if week_pct >= 60 else AlertSeverity.THIS_WEEK

                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.PAYMENT_TIMING_CONFLICT,
                    severity=severity,
                    title=f"Payment cluster: {week_pct:.0f}% of cash due week of {week_start.strftime('%b %d')}",
                    description=f"${week_total:,.0f} in obligations due when cash is ${total_cash:,.0f}",
                    context_data={
                        "week": f"{week_key[0]}-W{week_key[1]:02d}",
                        "week_start": week_start.isoformat(),
                        "week_end": week_end.isoformat(),
                        "total_due": week_total,
                        "total_cash": total_cash,
                        "percent_of_cash": week_pct,
                    },
                    cash_impact=-week_total,
                    urgency_score=min(100, 50 + week_pct),
                    deadline=datetime.combine(week_start, datetime.min.time()),
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: VENDOR_TERMS_EXPIRING
    # ==========================================================================
    async def _detect_vendor_terms(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect vendor payment terms about to expire.

        Alerts before payment deadlines to prevent late fees.
        """
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement
        from app.data.expenses.models import ExpenseBucket

        alert_days_before = thresholds.get("alert_days_before", 3)
        today = date.today()
        cutoff = today + timedelta(days=alert_days_before)

        # Find upcoming expense obligations
        result = await self.db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type != "revenue")
            .where(ObligationSchedule.due_date >= today)
            .where(ObligationSchedule.due_date <= cutoff)
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            .options(selectinload(ObligationSchedule.obligation))
        )
        upcoming_schedules = result.scalars().all()

        alerts = []
        for schedule in upcoming_schedules:
            days_until = (schedule.due_date - today).days

            existing = await self._get_existing_alert(
                DetectionType.VENDOR_TERMS_EXPIRING,
                {"schedule_id": str(schedule.id)}
            )
            if existing:
                continue

            # Get vendor info
            vendor_name = "Unknown vendor"
            vendor_id = None
            if schedule.obligation and schedule.obligation.expense_bucket_id:
                bucket_result = await self.db.execute(
                    select(ExpenseBucket)
                    .where(ExpenseBucket.id == schedule.obligation.expense_bucket_id)
                )
                bucket = bucket_result.scalar_one_or_none()
                if bucket:
                    vendor_name = bucket.name
                    vendor_id = bucket.id

            severity = AlertSeverity.EMERGENCY if days_until <= 1 else AlertSeverity.THIS_WEEK

            alert = DetectionAlert(
                user_id=self.user_id,
                rule_id=rule.id,
                detection_type=DetectionType.VENDOR_TERMS_EXPIRING,
                severity=severity,
                title=f"Payment due in {days_until} day{'s' if days_until != 1 else ''}: {vendor_name}",
                description=f"${float(schedule.estimated_amount):,.2f} due on {schedule.due_date.strftime('%b %d')}",
                context_data={
                    "schedule_id": str(schedule.id),
                    "obligation_id": str(schedule.obligation_id),
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "amount": float(schedule.estimated_amount),
                    "due_date": schedule.due_date.isoformat(),
                    "days_until_due": days_until,
                },
                cash_impact=-float(schedule.estimated_amount),
                urgency_score=90 if days_until <= 1 else 70,
                deadline=datetime.combine(schedule.due_date, datetime.min.time()),
            )
            alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: STATUTORY_DEADLINE
    # ==========================================================================
    async def _detect_statutory_deadlines(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect upcoming tax and regulatory deadlines.

        Checks for obligations categorized as tax_obligation or with statutory markers.
        """
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement

        alert_days = thresholds.get("alert_days_before", [14, 7, 3])
        if isinstance(alert_days, int):
            alert_days = [alert_days]

        today = date.today()
        max_days = max(alert_days)
        cutoff = today + timedelta(days=max_days)

        # Find statutory obligations
        result = await self.db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type == "tax_obligation")
            .where(ObligationSchedule.due_date >= today)
            .where(ObligationSchedule.due_date <= cutoff)
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            .options(selectinload(ObligationSchedule.obligation))
        )
        statutory_schedules = result.scalars().all()

        alerts = []
        for schedule in statutory_schedules:
            days_until = (schedule.due_date - today).days

            # Only alert at threshold days
            should_alert = any(days_until <= d and days_until > (d - 2) for d in alert_days)
            if not should_alert and days_until > 3:
                continue

            existing = await self._get_existing_alert(
                DetectionType.STATUTORY_DEADLINE,
                {"schedule_id": str(schedule.id), "days_bucket": str(days_until // 7)}
            )
            if existing:
                continue

            severity = AlertSeverity.EMERGENCY if days_until <= 3 else AlertSeverity.THIS_WEEK

            alert = DetectionAlert(
                user_id=self.user_id,
                rule_id=rule.id,
                detection_type=DetectionType.STATUTORY_DEADLINE,
                severity=severity,
                title=f"Tax deadline in {days_until} days: ${float(schedule.estimated_amount):,.0f}",
                description=f"Statutory payment due {schedule.due_date.strftime('%b %d, %Y')}",
                context_data={
                    "schedule_id": str(schedule.id),
                    "obligation_id": str(schedule.obligation_id),
                    "obligation_name": schedule.obligation.vendor_name if schedule.obligation else None,
                    "amount": float(schedule.estimated_amount),
                    "due_date": schedule.due_date.isoformat(),
                    "days_until_due": days_until,
                    "days_bucket": str(days_until // 7),
                },
                cash_impact=-float(schedule.estimated_amount),
                urgency_score=100 if days_until <= 3 else 80,
                deadline=datetime.combine(schedule.due_date, datetime.min.time()),
            )
            alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: BUFFER_BREACH
    # ==========================================================================
    async def _detect_buffer_breach(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Check if cash buffer is below threshold.

        Compares current cash to target buffer (months of burn).
        """
        from app.data.balances.models import CashAccount
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement

        buffer_months = thresholds.get("buffer_months", config.runway_buffer_months)
        warning_pct = thresholds.get("warning_percent", 80)
        critical_pct = thresholds.get("critical_percent", 50)

        # Get current cash
        result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == self.user_id)
        )
        total_cash = float(result.scalar() or 0)

        # Calculate monthly burn from expense obligations
        today = date.today()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        burn_result = await self.db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type != "revenue")
            .where(ObligationSchedule.due_date >= month_start)
            .where(ObligationSchedule.due_date <= month_end)
        )
        monthly_burn = float(burn_result.scalar() or 50000)  # Default if no data

        target_buffer = monthly_burn * buffer_months
        buffer_percent = (total_cash / target_buffer * 100) if target_buffer > 0 else 100

        # Also check against user's configured buffer amount
        config_buffer = float(config.obligations_buffer_amount)
        if config_buffer > 0 and total_cash < config_buffer:
            buffer_percent = min(buffer_percent, (total_cash / config_buffer) * 100)

        alerts = []

        if buffer_percent < critical_pct:
            existing = await self._get_existing_alert(
                DetectionType.BUFFER_BREACH,
                {"severity": "critical"}
            )
            if not existing:
                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.BUFFER_BREACH,
                    severity=AlertSeverity.EMERGENCY,
                    title="Cash buffer critically low",
                    description=f"Buffer at {buffer_percent:.0f}% of target ({buffer_months} months = ${target_buffer:,.0f})",
                    context_data={
                        "severity": "critical",
                        "current_cash": total_cash,
                        "target_buffer": target_buffer,
                        "buffer_percent": buffer_percent,
                        "monthly_burn": monthly_burn,
                        "buffer_months": buffer_months,
                    },
                    cash_impact=target_buffer - total_cash,
                    urgency_score=95,
                )
                alerts.append(alert)

        elif buffer_percent < warning_pct:
            existing = await self._get_existing_alert(
                DetectionType.BUFFER_BREACH,
                {"severity": "warning"}
            )
            if not existing:
                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.BUFFER_BREACH,
                    severity=AlertSeverity.THIS_WEEK,
                    title="Cash buffer below target",
                    description=f"Buffer at {buffer_percent:.0f}% of target ({buffer_months} months = ${target_buffer:,.0f})",
                    context_data={
                        "severity": "warning",
                        "current_cash": total_cash,
                        "target_buffer": target_buffer,
                        "buffer_percent": buffer_percent,
                        "monthly_burn": monthly_burn,
                        "buffer_months": buffer_months,
                    },
                    cash_impact=target_buffer - total_cash,
                    urgency_score=60,
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: RUNWAY_THRESHOLD
    # ==========================================================================
    async def _detect_runway_threshold(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Track remaining months of runway.

        Alerts when runway drops below warning or critical thresholds.
        """
        from app.data.balances.models import CashAccount
        from app.data.obligations.models import ObligationSchedule, ObligationAgreement

        warning_months = thresholds.get("warning_months", 3)
        critical_months = thresholds.get("critical_months", 1)

        # Get current cash
        result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == self.user_id)
        )
        total_cash = float(result.scalar() or 0)

        # Calculate net monthly burn (expenses - revenue)
        today = date.today()
        lookback_start = today - timedelta(days=90)

        # Average monthly expenses
        expense_result = await self.db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type != "revenue")
            .where(ObligationSchedule.due_date >= lookback_start)
            .where(ObligationSchedule.due_date <= today)
        )
        total_expenses = float(expense_result.scalar() or 0)

        # Average monthly revenue
        revenue_result = await self.db.execute(
            select(func.sum(ObligationSchedule.estimated_amount))
            .join(ObligationAgreement)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ObligationAgreement.obligation_type == "revenue")
            .where(ObligationSchedule.due_date >= lookback_start)
            .where(ObligationSchedule.due_date <= today)
        )
        total_revenue = float(revenue_result.scalar() or 0)

        months = 3  # 90 days
        monthly_expenses = total_expenses / months if months > 0 else 50000
        monthly_revenue = total_revenue / months if months > 0 else 0
        net_burn = monthly_expenses - monthly_revenue

        if net_burn <= 0:
            return []  # Cash flow positive, no runway concern

        runway_months = total_cash / net_burn if net_burn > 0 else float('inf')

        alerts = []

        if runway_months <= critical_months:
            existing = await self._get_existing_alert(
                DetectionType.RUNWAY_THRESHOLD,
                {"severity": "critical"}
            )
            if not existing:
                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.RUNWAY_THRESHOLD,
                    severity=AlertSeverity.EMERGENCY,
                    title=f"Critical: {runway_months:.1f} months runway remaining",
                    description=f"At current burn of ${net_burn:,.0f}/month, cash runs out in {runway_months:.1f} months",
                    context_data={
                        "severity": "critical",
                        "runway_months": runway_months,
                        "current_cash": total_cash,
                        "monthly_burn": net_burn,
                        "monthly_expenses": monthly_expenses,
                        "monthly_revenue": monthly_revenue,
                    },
                    cash_impact=None,
                    urgency_score=100,
                )
                alerts.append(alert)

        elif runway_months <= warning_months:
            existing = await self._get_existing_alert(
                DetectionType.RUNWAY_THRESHOLD,
                {"severity": "warning"}
            )
            if not existing:
                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.RUNWAY_THRESHOLD,
                    severity=AlertSeverity.THIS_WEEK,
                    title=f"Runway at {runway_months:.1f} months",
                    description=f"Below {warning_months} month threshold. Monthly burn: ${net_burn:,.0f}",
                    context_data={
                        "severity": "warning",
                        "runway_months": runway_months,
                        "current_cash": total_cash,
                        "monthly_burn": net_burn,
                        "monthly_expenses": monthly_expenses,
                        "monthly_revenue": monthly_revenue,
                    },
                    cash_impact=None,
                    urgency_score=70,
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: PAYROLL_SAFETY
    # ==========================================================================
    async def _detect_payroll_safety(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Check if upcoming payroll is covered.

        Runs N days before payroll, checks cash after all obligations.
        """
        from app.data.obligations.models import ObligationAgreement, ObligationSchedule
        from app.data.balances.models import CashAccount
        from app.data.expenses.models import ExpenseBucket

        days_before = thresholds.get("days_before_payroll", config.payroll_check_days_before)
        min_buffer_pct = thresholds.get("min_buffer_after", float(config.payroll_buffer_percent) / 100)

        today = date.today()
        check_window = today + timedelta(days=days_before)

        # Find payroll obligations with upcoming schedules
        result = await self.db.execute(
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .join(ExpenseBucket, ObligationAgreement.expense_bucket_id == ExpenseBucket.id)
            .where(ObligationAgreement.user_id == self.user_id)
            .where(ExpenseBucket.category == "payroll")
            .where(ObligationSchedule.due_date >= today)
            .where(ObligationSchedule.due_date <= check_window)
            .where(ObligationSchedule.status.in_(["scheduled", "due"]))
            .options(selectinload(ObligationSchedule.obligation))
        )
        payroll_schedules = result.scalars().all()

        if not payroll_schedules:
            return []

        # Get current cash balance
        cash_result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == self.user_id)
        )
        total_cash = float(cash_result.scalar() or 0)

        alerts = []

        for schedule in payroll_schedules:
            payroll_date = schedule.due_date
            payroll_amount = float(schedule.estimated_amount)

            # Get obligations due before this payroll
            obligations_result = await self.db.execute(
                select(func.sum(ObligationSchedule.estimated_amount))
                .join(ObligationAgreement)
                .where(ObligationAgreement.user_id == self.user_id)
                .where(ObligationSchedule.due_date >= today)
                .where(ObligationSchedule.due_date < payroll_date)
                .where(ObligationSchedule.status.in_(["scheduled", "due"]))
                .where(ObligationSchedule.id != schedule.id)
            )
            obligations_before = float(obligations_result.scalar() or 0)

            # Calculate cash position after payroll
            cash_after_obligations = total_cash - obligations_before
            cash_after_payroll = cash_after_obligations - payroll_amount
            buffer_needed = payroll_amount * min_buffer_pct

            if cash_after_payroll < buffer_needed:
                existing = await self._get_existing_alert(
                    DetectionType.PAYROLL_SAFETY,
                    {"schedule_id": str(schedule.id)}
                )
                if existing:
                    continue

                shortfall = buffer_needed - cash_after_payroll
                severity = AlertSeverity.EMERGENCY if cash_after_payroll < 0 else AlertSeverity.THIS_WEEK

                # Format due date context (obligation-focused)
                days_until = (payroll_date - today).days
                if days_until == 0:
                    due_text = "due today"
                elif days_until == 1:
                    due_text = "due tomorrow"
                elif payroll_date.weekday() == 4 and days_until <= 5:  # Friday
                    due_text = "due Friday"
                else:
                    due_text = f"due {payroll_date.strftime('%b %d')}"

                # OBLIGATION-FOCUSED title (not "Payroll at risk")
                if cash_after_payroll < 0:
                    title = f"Payroll underfunded by ${abs(cash_after_payroll):,.0f} - {due_text}"
                else:
                    title = f"Payroll buffer low (${cash_after_payroll:,.0f} remaining) - {due_text}"

                alert = DetectionAlert(
                    user_id=self.user_id,
                    rule_id=rule.id,
                    detection_type=DetectionType.PAYROLL_SAFETY,
                    severity=severity,
                    title=title,
                    description=f"${payroll_amount:,.0f} payroll scheduled. Cash after other obligations: ${cash_after_obligations:,.0f}",
                    context_data={
                        "schedule_id": str(schedule.id),
                        "payroll_amount": payroll_amount,
                        "payroll_date": payroll_date.isoformat(),
                        "current_cash": total_cash,
                        "obligations_before_payroll": obligations_before,
                        "cash_after_payroll": cash_after_payroll,
                        "buffer_needed": buffer_needed,
                        "shortfall": shortfall,
                    },
                    cash_impact=-shortfall,
                    urgency_score=100 if cash_after_payroll < 0 else 85,
                    deadline=datetime.combine(payroll_date - timedelta(days=2), datetime.min.time()),
                )
                alerts.append(alert)

        return alerts

    # ==========================================================================
    # Detection: HEADCOUNT_CHANGE
    # ==========================================================================
    async def _detect_headcount_change(
        self, rule: DetectionRule, thresholds: dict, config: UserConfiguration
    ) -> List[DetectionAlert]:
        """
        Detect new hires increasing burn.

        Monitors payroll expense buckets for employee count changes.
        """
        from app.data.expenses.models import ExpenseBucket
        from app.audit.models import AuditLog

        # Get payroll buckets
        result = await self.db.execute(
            select(ExpenseBucket)
            .where(ExpenseBucket.user_id == self.user_id)
            .where(ExpenseBucket.category == "payroll")
        )
        payroll_buckets = result.scalars().all()

        alerts = []

        for bucket in payroll_buckets:
            if bucket.employee_count is None:
                continue

            # Check audit log for recent changes to employee_count
            audit_result = await self.db.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "expense_bucket")
                .where(AuditLog.entity_id == bucket.id)
                .where(AuditLog.field_name == "employee_count")
                .where(AuditLog.created_at >= datetime.now() - timedelta(days=30))
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
            recent_change = audit_result.scalar_one_or_none()

            if recent_change:
                old_count = recent_change.old_value or 0
                new_count = recent_change.new_value or 0

                if new_count > old_count:
                    existing = await self._get_existing_alert(
                        DetectionType.HEADCOUNT_CHANGE,
                        {"bucket_id": str(bucket.id), "change_date": recent_change.created_at.date().isoformat()}
                    )
                    if existing:
                        continue

                    added = new_count - old_count
                    monthly_impact = (float(bucket.monthly_amount) / old_count * added) if old_count > 0 else 0

                    alert = DetectionAlert(
                        user_id=self.user_id,
                        rule_id=rule.id,
                        detection_type=DetectionType.HEADCOUNT_CHANGE,
                        severity=AlertSeverity.THIS_WEEK,
                        title=f"Headcount increased: +{added} employee{'s' if added > 1 else ''}",
                        description=f"Payroll bucket '{bucket.name}' now has {new_count} employees (was {old_count})",
                        context_data={
                            "bucket_id": str(bucket.id),
                            "bucket_name": bucket.name,
                            "old_count": old_count,
                            "new_count": new_count,
                            "added": added,
                            "change_date": recent_change.created_at.date().isoformat(),
                            "estimated_monthly_impact": monthly_impact,
                        },
                        cash_impact=-monthly_impact,
                        urgency_score=50,
                    )
                    alerts.append(alert)

        return alerts

    # ==========================================================================
    # Helper Methods
    # ==========================================================================
    async def _get_existing_alert(
        self, detection_type: DetectionType, context_match: dict
    ) -> Optional[DetectionAlert]:
        """Check if an alert already exists for this detection."""
        result = await self.db.execute(
            select(DetectionAlert)
            .where(DetectionAlert.user_id == self.user_id)
            .where(DetectionAlert.detection_type == detection_type)
            .where(DetectionAlert.status.in_([AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.PREPARING]))
        )
        existing_alerts = result.scalars().all()

        # Check if any existing alert matches the context
        for alert in existing_alerts:
            if all(
                alert.context_data.get(key) == value
                for key, value in context_match.items()
            ):
                return alert

        return None

    async def escalate_alerts(self) -> List[DetectionAlert]:
        """
        Check for alerts that need escalation based on time/conditions.

        Escalation rules:
        - Deadline within 3 days → EMERGENCY
        - Active for 2+ days with no action → escalate severity
        - Cash impact affects payroll → EMERGENCY
        """
        result = await self.db.execute(
            select(DetectionAlert)
            .where(DetectionAlert.user_id == self.user_id)
            .where(DetectionAlert.status == AlertStatus.ACTIVE)
            .where(DetectionAlert.severity != AlertSeverity.EMERGENCY)
        )
        alerts = result.scalars().all()

        escalated = []
        now = datetime.utcnow()

        for alert in alerts:
            should_escalate = False
            escalation_reason = None

            # Escalate if deadline is within 3 days
            if alert.deadline and (alert.deadline - now).days <= 3:
                should_escalate = True
                escalation_reason = "Deadline approaching"

            # Escalate if alert has been active for 2+ days with no action
            if (now - alert.detected_at).days >= 2 and alert.severity == AlertSeverity.THIS_WEEK:
                should_escalate = True
                escalation_reason = "No action taken for 2+ days"

            # Escalate if this is a late payment affecting a significant amount
            if (alert.detection_type == DetectionType.LATE_PAYMENT and
                alert.cash_impact and alert.cash_impact > 10000):
                days_overdue = alert.context_data.get("days_overdue", 0)
                if days_overdue >= 14:
                    should_escalate = True
                    escalation_reason = f"Large invoice {days_overdue} days overdue"

            if should_escalate:
                alert.severity = AlertSeverity.EMERGENCY
                alert.escalation_count += 1
                alert.last_escalated_at = now
                if escalation_reason:
                    alert.context_data = {
                        **alert.context_data,
                        "escalation_reason": escalation_reason
                    }
                escalated.append(alert)

        return escalated

    async def resolve_alert(self, alert_id: str, resolution_notes: Optional[str] = None) -> DetectionAlert:
        """Mark an alert as resolved."""
        result = await self.db.execute(
            select(DetectionAlert).where(DetectionAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        if resolution_notes:
            alert.context_data = {
                **alert.context_data,
                "resolution_notes": resolution_notes
            }

        return alert

    async def dismiss_alert(self, alert_id: str, reason: Optional[str] = None) -> DetectionAlert:
        """Dismiss an alert without resolving."""
        result = await self.db.execute(
            select(DetectionAlert).where(DetectionAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise ValueError(f"Alert {alert_id} not found")

        alert.status = AlertStatus.DISMISSED
        if reason:
            alert.context_data = {
                **alert.context_data,
                "dismiss_reason": reason
            }

        return alert
