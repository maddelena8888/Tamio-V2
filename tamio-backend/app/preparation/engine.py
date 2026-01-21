"""
Preparation Engine - V4 Architecture

The Work Preparation Engine turns detected problems into actionable solutions.
When a detection triggers, this engine:
1. Gathers context (client, vendor, cash position)
2. Assesses severity and calculates risk
3. Generates options with prepared content
4. Ranks options by composite risk score
5. Detects linked actions
6. Queues for user approval

Agent workflows for each action type:
- Invoice Follow-up Agent
- Vendor Delay Agent
- Payroll Safety Agent
- Payment Batch Agent
- Buffer Response Agent
- Statutory Payment Agent
- And more...
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.detection.models import DetectionAlert, DetectionType, AlertSeverity, AlertStatus
from .models import (
    PreparedAction, ActionOption, ActionType, ActionStatus, RiskLevel, LinkedAction
)
from .context import (
    get_client_context,
    get_vendor_context,
    get_cash_context,
    get_payroll_context,
)
from .risk_scoring import (
    score_action_option,
    calculate_composite_risk,
    RiskScore,
)
from .message_drafting import (
    draft_collection_email,
    draft_escalation_email,
    draft_vendor_delay_message,
    draft_early_payment_request,
    generate_call_talking_points,
    generate_action_summary,
)

logger = logging.getLogger(__name__)


class PreparationEngine:
    """
    Prepares actions for user approval.

    Uses a 3-step hybrid approach:
    1. Rule-based triggers activate workflows (deterministic)
    2. Context-aware agents prepare optimal actions (intelligent)
    3. Priority queue sequences actions for user (smart ordering)
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self._cash_context: Optional[Dict[str, Any]] = None

    async def get_cash_context(self) -> Dict[str, Any]:
        """Get cash context, caching for performance."""
        if self._cash_context is None:
            self._cash_context = await get_cash_context(self.db, self.user_id)
        return self._cash_context

    async def prepare_from_alert(self, alert: DetectionAlert) -> PreparedAction:
        """
        Create a PreparedAction from a DetectionAlert.

        Routes to appropriate agent based on detection type.
        """
        # Update alert status
        alert.status = AlertStatus.PREPARING

        handler_map = {
            DetectionType.LATE_PAYMENT: self._invoice_followup_agent,
            DetectionType.PAYROLL_SAFETY: self._payroll_safety_agent,
            DetectionType.BUFFER_BREACH: self._buffer_response_agent,
            DetectionType.VENDOR_TERMS_EXPIRING: self._vendor_payment_agent,
            DetectionType.PAYMENT_TIMING_CONFLICT: self._payment_batch_agent,
            DetectionType.STATUTORY_DEADLINE: self._statutory_payment_agent,
            DetectionType.CLIENT_CHURN: self._client_retention_agent,
            DetectionType.UNEXPECTED_EXPENSE: self._expense_review_agent,
            DetectionType.UNEXPECTED_REVENUE: self._revenue_variance_agent,
            DetectionType.REVENUE_VARIANCE: self._revenue_variance_agent,
            DetectionType.RUNWAY_THRESHOLD: self._runway_response_agent,
            DetectionType.HEADCOUNT_CHANGE: self._headcount_review_agent,
        }

        handler = handler_map.get(alert.detection_type)
        if not handler:
            return await self._generic_agent(alert)

        try:
            action = await handler(alert)
            self.db.add(action)

            # Check for linked actions
            await self._detect_linked_actions(action)

            return action
        except Exception as e:
            logger.error(f"Preparation agent failed for alert {alert.id}: {e}")
            return await self._generic_agent(alert)

    # =========================================================================
    # Agent: Invoice Follow-up
    # =========================================================================
    async def _invoice_followup_agent(self, alert: DetectionAlert) -> PreparedAction:
        """
        Prepare invoice follow-up action for late payment.

        Gathers client context, determines appropriate tone,
        generates email drafts with risk-scored options.

        NOTE: This agent now receives OBLIGATION-FOCUSED alerts from the detection engine.
        The alert title contains the obligation impact (e.g., "Payroll underfunded by $8K")
        and context_data contains causing_payments with client details.
        """
        context = alert.context_data
        days_overdue = context.get("days_overdue", 7)
        amount = context.get("amount", 0)
        client_id = context.get("client_id")

        # Gather context
        client_context = {}
        if client_id:
            client_context = await get_client_context(self.db, client_id)

        cash_context = await self.get_cash_context()

        # Determine base tone
        suggested_tone = client_context.get("suggested_tone", "professional")
        if days_overdue > 14 and suggested_tone != "soft":
            suggested_tone = "firm"
        elif days_overdue > 7 and suggested_tone == "soft":
            suggested_tone = "professional"

        client_name = client_context.get("name", context.get("client_name", "there"))
        invoice_number = context.get("invoice_number", "pending")
        due_date = context.get("due_date", "unknown")

        # OBLIGATION-FOCUSED: Use the alert's obligation-focused title if available
        # The detection engine now generates titles like "Payroll underfunded by $8K - due Friday"
        # and includes obligation details in context_data
        obligation_name = context.get("obligation_name")
        shortfall = context.get("shortfall", 0)
        obligation_due = context.get("obligation_due_date")
        causing_payments = context.get("causing_payments", [])

        # Build obligation-focused problem summary
        if obligation_name and shortfall > 0:
            # Format: "Payroll underfunded by $8K - due Friday (caused by RetailCo delay)"
            problem_summary = alert.title  # Use the obligation-focused alert title

            # Build problem context with "Caused by" details
            caused_by_details = []
            for payment in causing_payments[:3]:  # Limit to top 3
                payment_client = payment.get("client_name", "Unknown")
                payment_amount = payment.get("amount", 0)
                payment_days = payment.get("days_overdue", 0)
                caused_by_details.append(f"{payment_client}: ${payment_amount:,.0f} ({payment_days}d overdue)")

            problem_context = f"Shortfall of ${shortfall:,.0f} for {obligation_name}"
            if caused_by_details:
                problem_context += f". Caused by: {'; '.join(caused_by_details)}"
        else:
            # Fallback to client-focused format if no obligation data
            problem_summary = f"Collect ${amount:,.0f} from {client_name} ({days_overdue}d overdue)"
            problem_context = generate_action_summary("INVOICE_FOLLOW_UP", {
                "amount": amount,
                "client_name": client_name,
                "days_overdue": days_overdue,
            })

        # Create the action
        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.INVOICE_FOLLOW_UP,
            problem_summary=problem_summary,
            problem_context=problem_context,
            deadline=datetime.utcnow() + timedelta(days=2),
        )

        # Generate options with risk scoring
        options = []

        # Option 1: Send email (tone-appropriate)
        email_content = draft_collection_email(
            client_name=client_name,
            invoice_number=invoice_number,
            amount=amount,
            due_date=due_date,
            days_overdue=days_overdue,
            tone=suggested_tone,
            relationship_type=client_context.get("relationship_type", "transactional"),
            revenue_percent=client_context.get("revenue_percent", 0),
        )

        risk_score = score_action_option(
            action_type="INVOICE_FOLLOW_UP",
            entity_type="client",
            entity_context=client_context,
            cash_context=cash_context,
        )

        options.append(ActionOption(
            title=f"Send {email_content['tone']} reminder email",
            description=f"Send a {email_content['tone']} email to collect ${amount:,.0f}",
            risk_level=RiskLevel.LOW,
            is_recommended=1,
            reasoning=[
                f"Invoice is {days_overdue} days overdue",
                f"${amount:,.0f} impacts cash position",
                f"{email_content['tone'].capitalize()} tone based on relationship",
            ],
            risk_score=risk_score.composite_risk,
            relationship_risk=risk_score.relationship_risk,
            operational_risk=risk_score.operational_risk,
            financial_cost=risk_score.financial_cost,
            cash_impact=amount,
            impact_description=f"Collecting adds ${amount:,.0f} to cash",
            prepared_content={
                "type": "email",
                **email_content,
                "recipient_email": context.get("client_email", ""),
            },
            success_probability=0.7 if days_overdue <= 7 else 0.5,
            display_order=0,
        ))

        # Option 2: Phone call
        talking_points = generate_call_talking_points("client", client_name, {
            "invoice_number": invoice_number,
            "amount": amount,
            "days_overdue": days_overdue,
            "relationship_type": client_context.get("relationship_type"),
        })

        options.append(ActionOption(
            title="Make a phone call",
            description="Call the client directly to discuss payment",
            risk_level=RiskLevel.LOW,
            reasoning=[
                "Personal touch may accelerate payment",
                "Can uncover any issues or disputes",
                "Higher success rate for large amounts",
            ],
            risk_score=risk_score.composite_risk * 0.9,
            relationship_risk=risk_score.relationship_risk * 0.8,
            cash_impact=amount,
            impact_description="Higher success rate than email",
            prepared_content={
                "type": "call",
                "talking_points": talking_points,
            },
            success_probability=0.8,
            display_order=1,
        ))

        # Option 3: Escalate (for very overdue)
        if days_overdue >= 14:
            escalation_content = draft_escalation_email(
                client_name=client_name,
                invoice_number=invoice_number,
                amount=amount,
                days_overdue=days_overdue,
            )

            escalation_risk = score_action_option(
                action_type="COLLECTION_ESCALATION",
                entity_type="client",
                entity_context=client_context,
                cash_context=cash_context,
            )

            options.append(ActionOption(
                title="Escalate collection",
                description="Send formal demand letter",
                risk_level=RiskLevel.MEDIUM,
                reasoning=[
                    f"Invoice is significantly overdue ({days_overdue} days)",
                    "Formal escalation may prompt action",
                    "Use cautiously with strategic clients",
                ],
                risk_score=escalation_risk.composite_risk,
                relationship_risk=escalation_risk.relationship_risk,
                cash_impact=amount,
                prepared_content={
                    "type": "email",
                    **escalation_content,
                },
                display_order=2,
            ))

        action.options = options
        return action

    # =========================================================================
    # Agent: Payroll Safety
    # =========================================================================
    async def _payroll_safety_agent(self, alert: DetectionAlert) -> PreparedAction:
        """
        Prepare contingency options when payroll is at risk.

        Generates options:
        1. Delay vendor payment (if flexible vendors available)
        2. Chase early payment from client
        3. Draw credit line
        """
        context = alert.context_data
        shortfall = context.get("shortfall", 0)
        payroll_amount = context.get("payroll_amount", 0)
        payroll_date = context.get("payroll_date", "")

        payroll_context = await get_payroll_context(self.db, self.user_id)
        cash_context = await self.get_cash_context()

        # OBLIGATION-FOCUSED: Use alert title which is already obligation-focused
        # Detection engine generates: "Payroll underfunded by $X - due Friday"
        problem_summary = alert.title if alert.title else f"Payroll underfunded by ${shortfall:,.0f}"

        # Build caused-by context if late payments are contributing
        causing_payments = context.get("causing_payments", [])
        caused_by_text = ""
        if causing_payments:
            caused_by_details = []
            for payment in causing_payments[:2]:
                client_name = payment.get("client_name", "Unknown")
                amount = payment.get("amount", 0)
                caused_by_details.append(f"{client_name} (${amount:,.0f})")
            caused_by_text = f" Caused by late payments: {', '.join(caused_by_details)}."

        problem_context = f"${shortfall:,.0f} shortfall projected. Need to secure funds before {payroll_date or 'payroll date'}.{caused_by_text}"

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.PAYROLL_CONTINGENCY,
            problem_summary=problem_summary,
            problem_context=problem_context,
            deadline=datetime.utcnow() + timedelta(days=2),
        )

        options = []

        # Option 1: Find delayable vendor
        from app.data.expenses.models import ExpenseBucket

        delayable_result = await self.db.execute(
            select(ExpenseBucket)
            .where(ExpenseBucket.user_id == self.user_id)
            .where(ExpenseBucket.flexibility_level.in_(["can_delay", "negotiable"]))
            .where(ExpenseBucket.category != "payroll")
        )
        delayable_vendors = delayable_result.scalars().all()

        for vendor in delayable_vendors[:2]:
            vendor_context = await get_vendor_context(self.db, vendor.id)
            risk_score = score_action_option(
                action_type="VENDOR_DELAY",
                entity_type="vendor",
                entity_context=vendor_context,
                cash_context=cash_context,
                option_specific={"amount": float(vendor.monthly_amount)},
            )

            options.append(ActionOption(
                title=f"Delay payment to {vendor.name}",
                description=f"Request 7-day extension on ${float(vendor.monthly_amount):,.0f}",
                risk_level=RiskLevel.LOW if vendor_context.get("can_delay_score", 0) > 0.6 else RiskLevel.MEDIUM,
                is_recommended=1 if len(options) == 0 else 0,
                reasoning=[
                    f"Vendor marked as {vendor.flexibility_level}",
                    "Maintains payroll as sacred obligation",
                    f"Criticality: {vendor.criticality or 'unknown'}",
                ],
                risk_score=risk_score.composite_risk,
                relationship_risk=risk_score.relationship_risk,
                operational_risk=risk_score.operational_risk,
                cash_impact=float(vendor.monthly_amount),
                prepared_content={
                    "type": "vendor_delay",
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.name,
                    "amount": float(vendor.monthly_amount),
                },
                display_order=len(options),
            ))

        # Option 2: Request early payment from top client
        from app.data.clients.models import Client

        client_result = await self.db.execute(
            select(Client)
            .where(Client.user_id == self.user_id)
            .where(Client.status == "active")
            .where(Client.payment_behavior != "delayed")
            .order_by(Client.revenue_percent.desc().nullslast())
            .limit(1)
        )
        top_client = client_result.scalar_one_or_none()

        if top_client:
            client_context = await get_client_context(self.db, top_client.id)
            early_payment_content = draft_early_payment_request(
                client_name=top_client.name,
                invoice_number="outstanding",
                amount=shortfall,
                original_due_date="upcoming",
                requested_date=(datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d"),
                relationship_type=top_client.relationship_type or "transactional",
            )

            risk_score = score_action_option(
                action_type="INVOICE_FOLLOW_UP",
                entity_type="client",
                entity_context=client_context,
                cash_context=cash_context,
            )

            options.append(ActionOption(
                title=f"Request early payment from {top_client.name}",
                description="Ask client to pay outstanding invoice early",
                risk_level=RiskLevel.MEDIUM,
                reasoning=[
                    "May accelerate expected revenue",
                    f"Client relationship: {client_context.get('relationship_type', 'unknown')}",
                    "Success depends on client cash position",
                ],
                risk_score=risk_score.composite_risk,
                relationship_risk=risk_score.relationship_risk,
                success_probability=0.4,
                cash_impact=shortfall,
                prepared_content={
                    "type": "email",
                    **early_payment_content,
                },
                display_order=len(options),
            ))

        # Option 3: Draw credit line
        interest_cost = shortfall * 0.08 / 12

        options.append(ActionOption(
            title="Draw from credit line",
            description=f"Draw ${shortfall:,.0f} from available credit",
            risk_level=RiskLevel.LOW,
            reasoning=[
                "Immediate solution",
                "No relationship risk",
                f"Interest cost: ~${interest_cost:,.0f}/month",
            ],
            risk_score=20,
            relationship_risk=0,
            operational_risk=0.1,
            financial_cost=interest_cost,
            impact_description=f"Immediate ${shortfall:,.0f}, ~${interest_cost:,.0f} interest",
            prepared_content={
                "type": "credit_draw",
                "amount": shortfall,
                "estimated_interest_monthly": interest_cost,
            },
            display_order=len(options),
        ))

        action.options = options
        return action

    # =========================================================================
    # Agent: Buffer Response
    # =========================================================================
    async def _buffer_response_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Prepare response options for buffer breach."""
        context = alert.context_data
        buffer_percent = context.get("buffer_percent", 0)
        target_buffer = context.get("target_buffer", 0)
        current_cash = context.get("current_cash", 0)
        shortfall = target_buffer - current_cash

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.EXCESS_CASH_ALLOCATION,
            problem_summary=f"Cash buffer at {buffer_percent:.0f}% of target",
            problem_context=f"Need ${shortfall:,.0f} to reach target buffer of ${target_buffer:,.0f}",
            deadline=datetime.utcnow() + timedelta(days=7),
        )

        options = [
            ActionOption(
                title="Review discretionary expenses",
                description="Identify expenses that can be deferred or reduced",
                risk_level=RiskLevel.LOW,
                reasoning=["No external relationship impact", "May find quick wins"],
                risk_score=15,
                operational_risk=0.2,
                prepared_content={"type": "expense_review", "action": "identify_deferrable"},
                display_order=0,
            ),
            ActionOption(
                title="Accelerate outstanding collections",
                description="Prioritize follow-up on all outstanding invoices",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=["Brings in committed revenue faster", "Low relationship risk"],
                risk_score=20,
                relationship_risk=0.1,
                prepared_content={"type": "collection_campaign", "action": "accelerate_all"},
                display_order=1,
            ),
        ]

        if shortfall > 0:
            interest_cost = shortfall * 0.08 / 12
            options.append(ActionOption(
                title=f"Draw ${shortfall:,.0f} from credit line",
                description="Rebuild buffer with credit facility",
                risk_level=RiskLevel.LOW,
                reasoning=["Immediate buffer restoration", f"~${interest_cost:,.0f}/month interest"],
                risk_score=25,
                financial_cost=interest_cost,
                prepared_content={"type": "credit_draw", "amount": shortfall},
                display_order=2,
            ))

        action.options = options
        return action

    # =========================================================================
    # Agent: Vendor Payment
    # =========================================================================
    async def _vendor_payment_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Prepare vendor payment before terms expire."""
        context = alert.context_data
        amount = context.get("amount", 0)
        vendor_name = context.get("vendor_name", "Vendor")
        vendor_id = context.get("vendor_id")
        due_date = context.get("due_date", "")
        days_until = context.get("days_until_due", 0)

        vendor_context = {}
        if vendor_id:
            vendor_context = await get_vendor_context(self.db, vendor_id)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.PAYMENT_BATCH,
            problem_summary=f"Payment due in {days_until} days: {vendor_name}",
            problem_context=f"${amount:,.0f} due on {due_date}",
            deadline=alert.deadline,
        )

        options = [
            ActionOption(
                title=f"Process payment to {vendor_name}",
                description=f"Pay ${amount:,.0f} due {due_date}",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=[f"Payment due in {days_until} days", "Maintains vendor relationship"],
                risk_score=10,
                cash_impact=-amount,
                prepared_content={"type": "payment", "vendor_id": vendor_id, "amount": amount, "due_date": due_date},
                display_order=0,
            ),
        ]

        if vendor_context.get("can_delay_score", 0) > 0.4:
            options.append(ActionOption(
                title="Request payment delay",
                description="Ask vendor for brief extension",
                risk_level=RiskLevel.MEDIUM,
                reasoning=[f"Vendor flexibility: {vendor_context.get('flexibility_level', 'unknown')}"],
                risk_score=40,
                relationship_risk=0.2,
                cash_impact=amount,
                prepared_content={"type": "delay_request", "vendor_id": vendor_id},
                display_order=1,
            ))

        action.options = options
        return action

    # =========================================================================
    # Agent: Payment Batch
    # =========================================================================
    async def _payment_batch_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Prepare payment resequencing for clustered obligations."""
        context = alert.context_data
        week_total = context.get("total_due", 0)
        week_start = context.get("week_start", "")

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.PAYMENT_PRIORITIZATION,
            problem_summary=f"${week_total:,.0f} in payments clustered week of {week_start}",
            problem_context=f"Multiple payments due, representing {context.get('percent_of_cash', 0):.0f}% of cash",
            deadline=datetime.utcnow() + timedelta(days=3),
        )

        options = [
            ActionOption(
                title="Review payment priorities",
                description="Analyze which payments can be safely delayed",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=["Spreads cash outflow more evenly", "Identifies flexible vs. critical payments"],
                risk_score=25,
                prepared_content={"type": "payment_review", "week_start": week_start, "total_amount": week_total},
                display_order=0,
            ),
            ActionOption(
                title="Process all payments as scheduled",
                description="Pay everything on original dates",
                risk_level=RiskLevel.LOW,
                reasoning=["Maintains all relationships", "No negotiation needed"],
                risk_score=15,
                cash_impact=-week_total,
                prepared_content={"type": "batch_payment", "process_all": True},
                display_order=1,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Statutory Payment
    # =========================================================================
    async def _statutory_payment_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Prepare statutory/tax payment."""
        context = alert.context_data
        amount = context.get("amount", 0)
        due_date = context.get("due_date", "")
        days_until = context.get("days_until_due", 0)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.STATUTORY_PAYMENT,
            problem_summary=f"Tax deadline in {days_until} days: ${amount:,.0f}",
            problem_context=f"Statutory payment due {due_date}. Cannot be delayed.",
            deadline=datetime.strptime(due_date, "%Y-%m-%d") if due_date else datetime.utcnow() + timedelta(days=days_until),
        )

        options = [
            ActionOption(
                title="Process statutory payment",
                description=f"Pay ${amount:,.0f} before deadline",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=["Statutory deadlines cannot be negotiated", f"Due in {days_until} days"],
                risk_score=5,
                operational_risk=0.9 if days_until <= 3 else 0.5,
                cash_impact=-amount,
                prepared_content={"type": "statutory_payment", "amount": amount, "due_date": due_date},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Client Retention
    # =========================================================================
    async def _client_retention_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Handle client churn risk."""
        context = alert.context_data
        client_name = context.get("client_name", "Client")
        revenue_percent = context.get("revenue_percent", 0)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.INVOICE_FOLLOW_UP,
            problem_summary=f"Revenue at risk: {client_name}",
            problem_context=f"{revenue_percent:.1f}% of revenue potentially at risk",
            deadline=datetime.utcnow() + timedelta(days=7),
        )

        options = [
            ActionOption(
                title="Schedule client check-in",
                description="Proactive outreach to understand concerns",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=["Early intervention prevents churn", "Shows proactive relationship management"],
                risk_score=15,
                prepared_content={"type": "client_outreach", "client_id": context.get("client_id"), "action": "schedule_meeting"},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Expense Review
    # =========================================================================
    async def _expense_review_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Handle unexpected expense spike."""
        context = alert.context_data
        bucket_name = context.get("bucket_name", "Unknown")
        variance_pct = context.get("variance_percent", 0)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.PAYMENT_PRIORITIZATION,
            problem_summary=f"Expense spike: {bucket_name} (+{variance_pct:.0f}%)",
            problem_context="Review expense increase and determine if action needed",
            deadline=datetime.utcnow() + timedelta(days=7),
        )

        options = [
            ActionOption(
                title="Review expense details",
                description="Analyze what caused the increase",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=[f"{variance_pct:.0f}% above average", "May be legitimate business growth"],
                risk_score=20,
                prepared_content={"type": "expense_analysis", "bucket_id": context.get("bucket_id")},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Revenue Variance
    # =========================================================================
    async def _revenue_variance_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Handle revenue variance (over or under)."""
        context = alert.context_data
        variance_pct = context.get("variance_percent", 0)
        is_over = variance_pct > 0

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.INVOICE_FOLLOW_UP,
            problem_summary=f"Revenue {'ahead' if is_over else 'behind'} by {abs(variance_pct):.0f}%",
            problem_context="Review revenue variance and update forecast if needed",
            deadline=datetime.utcnow() + timedelta(days=7),
        )

        options = [
            ActionOption(
                title="Review revenue variance",
                description="Analyze what's driving the variance",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=[f"{'Positive' if is_over else 'Negative'} variance of {abs(variance_pct):.0f}%", "Update forecast accordingly"],
                risk_score=15 if is_over else 35,
                prepared_content={"type": "revenue_analysis", "variance_percent": variance_pct},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Runway Response
    # =========================================================================
    async def _runway_response_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Handle runway threshold warning."""
        context = alert.context_data
        runway_months = context.get("runway_months", 0)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.EXCESS_CASH_ALLOCATION,
            problem_summary=f"Runway at {runway_months:.1f} months",
            problem_context="Take action to extend runway",
            deadline=datetime.utcnow() + timedelta(days=14),
        )

        options = [
            ActionOption(
                title="Review burn rate reduction options",
                description="Identify ways to reduce monthly expenses",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=[f"Runway: {runway_months:.1f} months", "Reducing burn extends runway"],
                risk_score=30,
                prepared_content={"type": "runway_analysis", "current_runway": runway_months},
                display_order=0,
            ),
            ActionOption(
                title="Accelerate revenue",
                description="Focus on closing pending deals faster",
                risk_level=RiskLevel.LOW,
                reasoning=["Revenue increase improves runway", "May require sales team focus"],
                risk_score=25,
                prepared_content={"type": "revenue_acceleration"},
                display_order=1,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Headcount Review
    # =========================================================================
    async def _headcount_review_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Handle headcount change detection."""
        context = alert.context_data
        added = context.get("added", 0)
        monthly_impact = context.get("estimated_monthly_impact", 0)

        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.PAYMENT_PRIORITIZATION,
            problem_summary=f"Headcount increased: +{added} employee{'s' if added > 1 else ''}",
            problem_context=f"Estimated monthly impact: ${monthly_impact:,.0f}",
            deadline=datetime.utcnow() + timedelta(days=7),
        )

        options = [
            ActionOption(
                title="Review headcount change",
                description="Confirm the change is expected and budgeted",
                risk_level=RiskLevel.LOW,
                is_recommended=1,
                reasoning=[f"+{added} employees added", f"~${monthly_impact:,.0f}/month impact", "Update forecast accordingly"],
                risk_score=20,
                prepared_content={"type": "headcount_review", "bucket_id": context.get("bucket_id")},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Agent: Generic (Fallback)
    # =========================================================================
    async def _generic_agent(self, alert: DetectionAlert) -> PreparedAction:
        """Fallback handler for unimplemented detection types."""
        action = PreparedAction(
            user_id=self.user_id,
            alert_id=alert.id,
            action_type=ActionType.INVOICE_FOLLOW_UP,
            problem_summary=alert.title,
            problem_context=alert.description,
            deadline=alert.deadline or (datetime.utcnow() + timedelta(days=7)),
        )

        options = [
            ActionOption(
                title="Review and take action",
                description="Manually review this alert and decide next steps",
                risk_level=RiskLevel.LOW,
                reasoning=["Alert requires manual review"],
                risk_score=50,
                prepared_content={"type": "manual_review", "alert_type": alert.detection_type.value if alert.detection_type else "unknown"},
                display_order=0,
            ),
        ]

        action.options = options
        return action

    # =========================================================================
    # Linked Actions Detection
    # =========================================================================
    async def _detect_linked_actions(self, action: PreparedAction) -> List[LinkedAction]:
        """
        Detect and create links between related actions.

        Link types:
        - "resolves": Completing action_id resolves linked_action_id
        - "conflicts": Cannot do both actions
        - "sequence": linked_action_id should come after action_id
        - "depends_on": action_id depends on linked_action_id being done first
        - "cascades_to": Completing action_id affects linked_action_id
        """
        links = []

        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.user_id == self.user_id)
            .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
            .where(PreparedAction.id != action.id)
        )
        other_actions = result.scalars().all()

        for other in other_actions:
            detected_links = await self._check_all_link_types(action, other)
            for link in detected_links:
                links.append(link)
                self.db.add(link)

        return links

    async def _check_all_link_types(
        self, action: PreparedAction, other: PreparedAction
    ) -> List[LinkedAction]:
        """Check all possible link types between two actions."""
        links = []

        # Check each link type
        link_checks = [
            self._check_resolves_link,
            self._check_conflicts_link,
            self._check_sequence_link,
            self._check_depends_on_link,
            self._check_cascades_to_link,
            self._check_same_entity_link,
        ]

        for check in link_checks:
            link = await check(action, other)
            if link:
                links.append(link)

        return links

    async def _check_resolves_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if completing one action resolves another.

        Examples:
        - Collecting invoice resolves payroll shortfall
        - Collecting invoice resolves buffer breach
        - Early client payment resolves vendor delay need
        """
        # Invoice collection resolves payroll contingency
        if (action.action_type == ActionType.INVOICE_FOLLOW_UP and
            other.action_type == ActionType.PAYROLL_CONTINGENCY):
            # Check if invoice amount would help
            invoice_amount = self._get_action_cash_impact(action)
            if invoice_amount > 0:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="resolves",
                    link_reason=f"Collecting ${invoice_amount:,.0f} could help cover payroll shortfall",
                )

        # Invoice collection resolves buffer breach
        if (action.action_type == ActionType.INVOICE_FOLLOW_UP and
            other.action_type == ActionType.EXCESS_CASH_ALLOCATION):
            invoice_amount = self._get_action_cash_impact(action)
            if invoice_amount > 0:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="resolves",
                    link_reason=f"Collecting ${invoice_amount:,.0f} helps restore cash buffer",
                )

        # Credit line draw resolves payroll contingency
        if (action.action_type == ActionType.CREDIT_LINE_DRAW and
            other.action_type == ActionType.PAYROLL_CONTINGENCY):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="resolves",
                link_reason="Credit draw provides immediate funds for payroll",
            )

        return None

    async def _check_conflicts_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if two actions conflict (cannot do both).

        Examples:
        - Delaying payment to same vendor twice
        - Multiple draws from credit line exceeding limit
        - Conflicting payment priorities
        """
        # Same vendor delay requested twice
        if (action.action_type == ActionType.VENDOR_DELAY and
            other.action_type == ActionType.VENDOR_DELAY):
            action_vendor = self._get_vendor_id_from_action(action)
            other_vendor = self._get_vendor_id_from_action(other)
            if action_vendor and action_vendor == other_vendor:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="conflicts",
                    link_reason="Cannot delay payments to same vendor twice",
                )

        # Payment batch conflicts with vendor delay for same vendor
        if (action.action_type == ActionType.PAYMENT_BATCH and
            other.action_type == ActionType.VENDOR_DELAY):
            # Check if the payment batch includes the vendor being delayed
            payment_vendors = self._get_vendor_ids_from_batch(action)
            delay_vendor = self._get_vendor_id_from_action(other)
            if delay_vendor and delay_vendor in payment_vendors:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="conflicts",
                    link_reason="Payment batch includes vendor marked for delay",
                )

        # Multiple credit draws that exceed available credit
        if (action.action_type == ActionType.CREDIT_LINE_DRAW and
            other.action_type == ActionType.CREDIT_LINE_DRAW):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="conflicts",
                link_reason="Review combined credit draws against available limit",
            )

        return None

    async def _check_sequence_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if actions should be sequenced (order matters).

        Examples:
        - Payment batches in same week
        - Multiple invoices to same client
        """
        # Payment batches in same week
        if (action.action_type in [ActionType.PAYMENT_BATCH, ActionType.PAYMENT_PRIORITIZATION] and
            other.action_type in [ActionType.PAYMENT_BATCH, ActionType.PAYMENT_PRIORITIZATION]):
            if action.deadline and other.deadline:
                days_apart = abs((action.deadline - other.deadline).days)
                if days_apart <= 7:
                    return LinkedAction(
                        action_id=action.id,
                        linked_action_id=other.id,
                        link_type="sequence",
                        link_reason="Both payment actions due within same week - consider sequencing",
                    )

        # Multiple invoice follow-ups to same client
        if (action.action_type == ActionType.INVOICE_FOLLOW_UP and
            other.action_type == ActionType.INVOICE_FOLLOW_UP):
            action_client = self._get_client_id_from_action(action)
            other_client = self._get_client_id_from_action(other)
            if action_client and action_client == other_client:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="sequence",
                    link_reason="Multiple invoices for same client - consider single communication",
                )

        return None

    async def _check_depends_on_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if one action depends on another being completed first.

        Examples:
        - Payroll confirmation depends on payroll contingency resolution
        - Invoice escalation depends on initial follow-up
        """
        # Payroll confirmation depends on contingency being resolved
        if (action.action_type == ActionType.PAYROLL_CONFIRMATION and
            other.action_type == ActionType.PAYROLL_CONTINGENCY):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="depends_on",
                link_reason="Resolve payroll funding before confirming payroll",
            )

        # Collection escalation depends on initial follow-up attempt
        if (action.action_type == ActionType.COLLECTION_ESCALATION and
            other.action_type == ActionType.INVOICE_FOLLOW_UP):
            action_client = self._get_client_id_from_action(action)
            other_client = self._get_client_id_from_action(other)
            if action_client and action_client == other_client:
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="depends_on",
                    link_reason="Try standard follow-up before escalation",
                )

        return None

    async def _check_cascades_to_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if completing one action cascades/affects another.

        Examples:
        - Vendor delay affects payment batch timing
        - Large collection affects runway calculation
        """
        # Vendor delay cascades to payment batch
        if (action.action_type == ActionType.VENDOR_DELAY and
            other.action_type == ActionType.PAYMENT_BATCH):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="cascades_to",
                link_reason="Vendor delay will affect payment batch timing",
            )

        # Large invoice collection cascades to runway response
        if (action.action_type == ActionType.INVOICE_FOLLOW_UP and
            other.action_type == ActionType.EXCESS_CASH_ALLOCATION):
            invoice_amount = self._get_action_cash_impact(action)
            if invoice_amount > 10000:  # Significant amount
                return LinkedAction(
                    action_id=action.id,
                    linked_action_id=other.id,
                    link_type="cascades_to",
                    link_reason=f"Collecting ${invoice_amount:,.0f} may change cash allocation needs",
                )

        return None

    async def _check_same_entity_link(
        self, action: PreparedAction, other: PreparedAction
    ) -> Optional[LinkedAction]:
        """
        Check if actions involve the same entity (client/vendor).

        This creates awareness links for related communications.
        """
        # Skip if other link types already detected
        # (this is a catch-all for entity relationship awareness)

        action_client = self._get_client_id_from_action(action)
        other_client = self._get_client_id_from_action(other)

        # Same client, different action types
        if (action_client and action_client == other_client and
            action.action_type != other.action_type):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="sequence",
                link_reason="Both actions involve same client - coordinate communications",
            )

        action_vendor = self._get_vendor_id_from_action(action)
        other_vendor = self._get_vendor_id_from_action(other)

        # Same vendor, different action types
        if (action_vendor and action_vendor == other_vendor and
            action.action_type != other.action_type):
            return LinkedAction(
                action_id=action.id,
                linked_action_id=other.id,
                link_type="sequence",
                link_reason="Both actions involve same vendor - coordinate approach",
            )

        return None

    def _get_action_cash_impact(self, action: PreparedAction) -> float:
        """Get the positive cash impact from an action's options."""
        if not action.options:
            return 0
        for option in action.options:
            if option.cash_impact and option.cash_impact > 0:
                return option.cash_impact
        return 0

    def _get_client_id_from_action(self, action: PreparedAction) -> Optional[str]:
        """Extract client ID from action's prepared content."""
        if not action.options:
            return None
        for option in action.options:
            content = option.prepared_content or {}
            if "client_id" in content:
                return content["client_id"]
        return None

    def _get_vendor_id_from_action(self, action: PreparedAction) -> Optional[str]:
        """Extract vendor ID from action's prepared content."""
        if not action.options:
            return None
        for option in action.options:
            content = option.prepared_content or {}
            if "vendor_id" in content:
                return content["vendor_id"]
            if "bucket_id" in content:
                return content["bucket_id"]
        return None

    def _get_vendor_ids_from_batch(self, action: PreparedAction) -> List[str]:
        """Extract all vendor IDs from a payment batch action."""
        vendor_ids = []
        if not action.options:
            return vendor_ids
        for option in action.options:
            content = option.prepared_content or {}
            if "payments" in content and isinstance(content["payments"], list):
                for payment in content["payments"]:
                    if "vendor_id" in payment:
                        vendor_ids.append(payment["vendor_id"])
        return vendor_ids

    # =========================================================================
    # Action Queue Management
    # =========================================================================
    async def get_action_queue(self) -> Dict[str, list]:
        """Get all pending actions organized by urgency."""
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.user_id == self.user_id)
            .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
            .options(selectinload(PreparedAction.alert))
            .options(selectinload(PreparedAction.options))
        )
        actions = result.scalars().all()

        queue = {"emergency": [], "this_week": [], "upcoming": []}
        now = datetime.utcnow()

        for action in actions:
            if action.alert and action.alert.severity == AlertSeverity.EMERGENCY:
                queue["emergency"].append(action)
            elif action.deadline and (action.deadline - now).days <= 3:
                queue["emergency"].append(action)
            elif action.deadline and (action.deadline - now).days <= 7:
                queue["this_week"].append(action)
            else:
                queue["upcoming"].append(action)

        return queue

    async def approve_action(self, action_id: str, selected_option_id: Optional[str] = None, user_notes: Optional[str] = None) -> PreparedAction:
        """Approve an action and optionally select an option."""
        result = await self.db.execute(select(PreparedAction).where(PreparedAction.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError(f"Action {action_id} not found")

        action.status = ActionStatus.APPROVED
        action.approved_at = datetime.utcnow()
        action.selected_option_id = selected_option_id
        if user_notes:
            action.user_notes = user_notes

        if action.alert_id:
            alert_result = await self.db.execute(select(DetectionAlert).where(DetectionAlert.id == action.alert_id))
            alert = alert_result.scalar_one_or_none()
            if alert:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = datetime.utcnow()

        return action

    async def skip_action(self, action_id: str, reason: str) -> PreparedAction:
        """Skip an action with a reason."""
        result = await self.db.execute(select(PreparedAction).where(PreparedAction.id == action_id))
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError(f"Action {action_id} not found")

        action.status = ActionStatus.SKIPPED
        action.user_notes = reason
        return action

    async def link_actions(self, action: PreparedAction, linked_action: PreparedAction, link_type: str, reason: str) -> LinkedAction:
        """Create a link between related actions."""
        link = LinkedAction(action_id=action.id, linked_action_id=linked_action.id, link_type=link_type, link_reason=reason)
        self.db.add(link)
        return link
