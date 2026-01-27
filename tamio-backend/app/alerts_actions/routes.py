"""
Alerts & Actions Routes - V4 Risk/Controls Architecture

API endpoints for the refactored Alerts & Actions page.
Transforms DetectionAlerts into Risks and PreparedActions into Controls.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.data.users.models import User
from app.detection.models import DetectionAlert, AlertSeverity, AlertStatus
from app.preparation.models import PreparedAction, ActionOption, ActionStatus
from app.data.balances.models import CashAccount
from app.data.user_config.routes import get_or_create_config

from .schemas import (
    RiskSeverity,
    RiskStatus,
    ControlState,
    ActionStepOwner,
    ActionStepStatus,
    ActionStepResponse,
    RejectedSuggestionResponse,
    RiskResponse,
    ControlResponse,
    RisksListResponse,
    ControlsListResponse,
    ControlsForRiskResponse,
    RisksForControlResponse,
    UpdateControlStateRequest,
    ApproveControlRequest,
    RejectControlRequest,
    CompleteControlRequest,
    SuccessResponse,
    ControlUpdateResponse,
)

router = APIRouter(prefix="/alerts-actions", tags=["alerts-actions"])


# ============================================================================
# Category Mappings
# ============================================================================

# Maps category names to their associated detection types
CATEGORY_DETECTION_TYPES = {
    "receivables": [
        "late_payment",
        "unexpected_revenue",
        "client_churn",
        "revenue_variance",
    ],
    "obligations": [
        "payment_timing_conflict",
        "vendor_terms_expiring",
        "statutory_deadline",
        "buffer_breach",
        "payroll_safety",
    ],
}


# ============================================================================
# Utility Functions
# ============================================================================

def _map_severity(backend_severity: str) -> RiskSeverity:
    """Map backend AlertSeverity to frontend RiskSeverity."""
    mapping = {
        "emergency": RiskSeverity.URGENT,
        "this_week": RiskSeverity.HIGH,
        "upcoming": RiskSeverity.NORMAL,
    }
    return mapping.get(backend_severity, RiskSeverity.NORMAL)


def _map_risk_status(backend_status: str) -> RiskStatus:
    """Map backend AlertStatus to frontend RiskStatus."""
    mapping = {
        "active": RiskStatus.ACTIVE,
        "acknowledged": RiskStatus.ACKNOWLEDGED,
        "preparing": RiskStatus.PREPARING,
        "resolved": RiskStatus.RESOLVED,
        "dismissed": RiskStatus.DISMISSED,
    }
    return mapping.get(backend_status, RiskStatus.ACTIVE)


def _map_control_state(backend_status: str) -> ControlState:
    """Map backend ActionStatus to frontend ControlState."""
    mapping = {
        "pending_approval": ControlState.PENDING,
        "approved": ControlState.ACTIVE,
        "edited": ControlState.ACTIVE,
        "executed": ControlState.COMPLETED,
        "overridden": ControlState.NEEDS_REVIEW,
        "skipped": ControlState.NEEDS_REVIEW,
        "expired": ControlState.NEEDS_REVIEW,
    }
    return mapping.get(backend_status, ControlState.PENDING)


def _get_state_label(state: ControlState) -> str:
    """Get display label for control state."""
    labels = {
        ControlState.PENDING: "Pending",
        ControlState.ACTIVE: "In progress",
        ControlState.COMPLETED: "Completed",
        ControlState.NEEDS_REVIEW: "Needs review",
    }
    return labels.get(state, "Unknown")


def _compute_due_horizon_label(deadline: Optional[datetime]) -> str:
    """Compute human-readable due horizon label."""
    if not deadline:
        return "No deadline"

    now = datetime.now(timezone.utc)
    # Make deadline timezone-aware if it isn't already
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - now

    if delta.total_seconds() < 0:
        return "Overdue"
    elif delta.days == 0:
        return "Due today"
    elif delta.days == 1:
        return "Due tomorrow"
    elif delta.days < 7:
        # Show day of week
        day_name = deadline.strftime("%A")
        return f"Due {day_name}"
    elif delta.days < 14:
        return f"In {delta.days} days"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"In {weeks} week{'s' if weeks > 1 else ''}"
    else:
        return deadline.strftime("Due %b %d")


def _compute_days_until(deadline: Optional[datetime]) -> Optional[int]:
    """Compute days until deadline."""
    if not deadline:
        return None
    now = datetime.now(timezone.utc)
    # Make deadline timezone-aware if it isn't already
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    delta = deadline - now
    return max(0, delta.days)


def _extract_primary_driver(context_data: dict) -> str:
    """Extract primary driver from alert context data."""
    # Try various patterns based on detection type
    if context_data.get("causing_payments"):
        payments = context_data["causing_payments"]
        if payments:
            first = payments[0]
            client = first.get("client_name", "Unknown")
            days = first.get("days_overdue", 0)
            return f"{client} payment {days}d overdue"

    if context_data.get("client_name"):
        client = context_data["client_name"]
        if context_data.get("days_overdue"):
            return f"{client} payment {context_data['days_overdue']}d overdue"
        return f"{client} - action needed"

    if context_data.get("bucket_name") or context_data.get("vendor_name"):
        name = context_data.get("bucket_name") or context_data.get("vendor_name")
        return f"{name} - attention required"

    if context_data.get("obligation_category"):
        category = context_data["obligation_category"]
        if context_data.get("shortfall"):
            shortfall = context_data["shortfall"]
            return f"{category.title()} underfunded by ${shortfall:,.0f}"
        return f"{category.title()} - review needed"

    # Fallback
    return "Review required"


def _extract_context_bullets(context_data: dict) -> List[str]:
    """Extract context bullets from alert data."""
    bullets = []

    # Check for explicit context list
    if context_data.get("context_summary"):
        return context_data["context_summary"]

    if context_data.get("caused_by_summary"):
        return context_data["caused_by_summary"]

    # Build from individual fields
    if context_data.get("cash_shortfall"):
        shortfall = context_data["cash_shortfall"]
        bullets.append(f"Cash shortfall: ${shortfall:,.0f}")

    if context_data.get("current_cash"):
        cash = context_data["current_cash"]
        bullets.append(f"Current cash: ${cash:,.0f}")

    if context_data.get("obligation_amount"):
        amount = context_data["obligation_amount"]
        bullets.append(f"Obligation amount: ${amount:,.0f}")

    if context_data.get("causing_payments"):
        for payment in context_data["causing_payments"][:3]:  # Max 3
            client = payment.get("client_name", "Unknown")
            amount = payment.get("amount", 0)
            days = payment.get("days_overdue", 0)
            bullets.append(f"{client}: ${amount:,.0f} ({days}d overdue)")

    return bullets if bullets else ["Review alert details"]


async def _compute_buffer_impact(
    db: AsyncSession, user_id: str, cash_impact: Optional[float]
) -> Optional[float]:
    """Compute buffer impact as percentage."""
    if not cash_impact:
        return None

    # Get current cash
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    current_cash = float(result.scalar() or 0)

    if current_cash <= 0:
        return None

    # Get buffer threshold from user config
    config = await get_or_create_config(db, user_id)
    buffer_amount = float(config.obligations_buffer_amount or 0)

    if buffer_amount <= 0:
        # Use 10% of current cash as default buffer
        buffer_amount = current_cash * 0.1

    # Calculate impact as percentage of buffer
    return round((abs(cash_impact) / buffer_amount) * 100, 1)


def _format_compact_amount(amount: float) -> str:
    """Format amount in compact form (e.g., $53K, $1.2M).

    Uses round-half-up (like JavaScript) for consistency with frontend.
    """
    abs_amount = abs(amount)
    if abs_amount >= 1_000_000:
        return f"${abs_amount / 1_000_000:.1f}M".replace(".0M", "M")
    elif abs_amount >= 1_000:
        # Use floor(x + 0.5) for round-half-up behavior (like JavaScript)
        return f"${math.floor(abs_amount / 1_000 + 0.5)}K"
    else:
        return f"${math.floor(abs_amount + 0.5):,}"


def _get_business_consequence(
    context: dict,
    projected_cash: float,
    buffer_amount: float,
    shortfall: float,
    detection_type: str,
) -> Optional[str]:
    """
    Determine the business consequence of an alert's impact.

    Returns a "which means XYZ" clause explaining the business impact.
    """
    # Check for payroll-related consequences
    payroll_amount = context.get("payroll_amount") or context.get("upcoming_payroll")
    if payroll_amount and projected_cash < payroll_amount:
        return "putting payroll at risk"

    # Check if this affects upcoming obligations
    obligation_amount = context.get("obligation_amount") or context.get("upcoming_obligation")
    obligation_category = context.get("obligation_category", "").lower()

    if obligation_amount and projected_cash < obligation_amount:
        if "tax" in obligation_category:
            return "risking tax payment deadlines and potential penalties"
        elif "payroll" in obligation_category:
            return "putting payroll at risk"
        else:
            return f"putting upcoming {obligation_category} payments at risk"

    # Calculate runway impact if monthly burn is available
    monthly_burn = context.get("monthly_burn")
    if monthly_burn and monthly_burn > 0:
        current_runway_weeks = (projected_cash + shortfall) / (monthly_burn / 4.33)
        new_runway_weeks = projected_cash / (monthly_burn / 4.33)
        weeks_lost = current_runway_weeks - new_runway_weeks

        if new_runway_weeks < 4:
            return f"leaving only {new_runway_weeks:.0f} weeks of runway"
        elif weeks_lost >= 2:
            return f"reducing your runway by {weeks_lost:.0f} weeks"

    # Check severity of buffer breach
    buffer_breach_percent = (shortfall / buffer_amount * 100) if buffer_amount > 0 else 0

    if buffer_breach_percent >= 75:
        return "leaving minimal safety margin for unexpected expenses"
    elif buffer_breach_percent >= 50:
        return "significantly reducing your ability to handle unexpected costs"
    elif buffer_breach_percent >= 25:
        return "limiting flexibility for cash flow fluctuations"

    # Detection-type specific consequences
    if detection_type in ["payment_overdue", "late_payment", "receivable_risk"]:
        if shortfall > 0:
            return "which may require deferring other payments"
        return "reducing your cash buffer"

    elif detection_type in ["expense_spike", "obligation_breach"]:
        return "requiring review of discretionary spending"

    elif detection_type in ["cash_shortfall", "buffer_breach", "negative_balance"]:
        return "requiring immediate cash management action"

    # Default consequence based on shortfall size
    if shortfall > buffer_amount * 0.5:
        return "requiring immediate attention"

    return None


def _generate_impact_statement(
    alert: DetectionAlert,
    current_cash: float,
    buffer_amount: float,
) -> Optional[str]:
    """
    Generate a quantified impact statement for a risk with business consequences.

    Examples:
    - "If unpaid, cash drops to $142K in Week 3 — $58K below buffer, putting payroll at risk"
    - "Missing this payment reduces buffer by 45% ($52K), reducing your runway by 3 weeks"
    - "Delays payroll coverage — creates $30K shortfall by Feb 14, requiring immediate cash management action"
    """
    cash_impact = alert.cash_impact
    if not cash_impact:
        return None

    context = alert.context_data or {}
    detection_type = alert.detection_type or ""

    # Calculate projected position after impact
    projected_cash = current_cash - abs(cash_impact)
    shortfall = max(0, buffer_amount - projected_cash)

    # Get week info from context
    week_number = context.get("week_number") or context.get("impact_week")

    # Get business consequence
    consequence = _get_business_consequence(
        context=context,
        projected_cash=projected_cash,
        buffer_amount=buffer_amount,
        shortfall=shortfall,
        detection_type=detection_type,
    )

    # Helper to append consequence
    def with_consequence(statement: str) -> str:
        if consequence:
            return f"{statement}, {consequence}"
        return statement

    # Generate statement based on detection type
    if detection_type in ["payment_overdue", "late_payment", "receivable_risk"]:
        if projected_cash < buffer_amount:
            if week_number:
                base = f"If unpaid, cash drops to {_format_compact_amount(projected_cash)} in Week {week_number} — {_format_compact_amount(shortfall)} below buffer"
            else:
                base = f"If unpaid, cash drops to {_format_compact_amount(projected_cash)} — {_format_compact_amount(shortfall)} below buffer"
            return with_consequence(base)
        else:
            buffer_impact_pct = round((abs(cash_impact) / buffer_amount) * 100)
            base = f"Missing this payment reduces buffer by {buffer_impact_pct}% ({_format_compact_amount(abs(cash_impact))})"
            return with_consequence(base)

    elif detection_type in ["cash_shortfall", "buffer_breach", "negative_balance"]:
        if week_number:
            base = f"Cash position drops to {_format_compact_amount(projected_cash)} in Week {week_number} — {_format_compact_amount(shortfall)} below safe threshold"
        else:
            base = f"Cash position drops to {_format_compact_amount(projected_cash)} — {_format_compact_amount(shortfall)} below safe threshold"
        return with_consequence(base)

    elif detection_type in ["payroll_risk", "payroll_shortfall"]:
        if week_number:
            base = f"Payroll at risk — creates {_format_compact_amount(shortfall)} shortfall by Week {week_number}"
        else:
            base = f"Payroll coverage at risk — {_format_compact_amount(abs(cash_impact))} shortfall projected"
        return with_consequence(base)

    elif detection_type in ["expense_spike", "obligation_breach"]:
        base = f"Creates {_format_compact_amount(shortfall)} funding gap — buffer drops to {_format_compact_amount(projected_cash)}"
        return with_consequence(base)

    # Generic fallback with numbers
    if projected_cash < buffer_amount:
        base = f"Impact: cash drops to {_format_compact_amount(projected_cash)} — {_format_compact_amount(shortfall)} below buffer"
        return with_consequence(base)
    else:
        base = f"Impact: {_format_compact_amount(abs(cash_impact))} reduction in available cash"
        return with_consequence(base)


def _generate_why_explanation(action: PreparedAction) -> str:
    """Generate explanation for why a control exists."""
    # Use problem_context if available (this is the action description)
    if action.problem_context:
        return action.problem_context

    # Fallback to generating from alert
    if action.alert:
        return f"Mitigates: {action.alert.title}"

    return action.problem_summary


def _extract_responsibility_split(action: PreparedAction) -> tuple[List[str], List[str]]:
    """Extract what Tamio handles vs what user handles."""
    tamio_handles = []
    user_handles = []

    # Check options for action steps
    if action.options:
        for option in action.options:
            content = option.prepared_content or {}

            # Infer from action type and content
            if action.action_type in ["invoice_follow_up", "payment_reminder", "vendor_delay"]:
                tamio_handles.extend([
                    "Draft email content",
                    "Calculate optimal timing",
                ])
                user_handles.extend([
                    "Review and personalize email",
                    "Send via your email client",
                ])

            elif action.action_type == "payment_batch":
                tamio_handles.extend([
                    "Identify payments due",
                    "Generate payment file",
                ])
                user_handles.extend([
                    "Review payment batch",
                    "Upload to bank portal",
                ])

            elif action.action_type in ["payroll_contingency", "payroll_confirmation"]:
                tamio_handles.extend([
                    "Monitor cash position",
                    "Alert if issues detected",
                ])
                user_handles.extend([
                    "Confirm payroll processing",
                    "Verify employee payments",
                ])

            else:
                tamio_handles.extend(["Prepare action details"])
                user_handles.extend(["Execute action"])

            break  # Only process first option

    # Deduplicate
    tamio_handles = list(dict.fromkeys(tamio_handles))
    user_handles = list(dict.fromkeys(user_handles))

    return tamio_handles, user_handles


def _build_action_steps(action: PreparedAction) -> List[ActionStepResponse]:
    """Build action steps from prepared action."""
    steps = []

    # Check if options have explicit steps (not in current model, but future-proof)
    # For now, infer from action type
    if action.action_type in ["invoice_follow_up", "payment_reminder", "vendor_delay"]:
        steps = [
            ActionStepResponse(
                id=f"{action.id}-step-1",
                title="Draft email content",
                owner=ActionStepOwner.TAMIO,
                status=ActionStepStatus.COMPLETED if action.status != "pending_approval" else ActionStepStatus.PENDING,
                order=1,
            ),
            ActionStepResponse(
                id=f"{action.id}-step-2",
                title="Review and send email",
                owner=ActionStepOwner.USER,
                status=ActionStepStatus.COMPLETED if action.status == "executed" else ActionStepStatus.PENDING,
                order=2,
            ),
            ActionStepResponse(
                id=f"{action.id}-step-3",
                title="Log communication",
                owner=ActionStepOwner.TAMIO,
                status=ActionStepStatus.COMPLETED if action.status == "executed" else ActionStepStatus.PENDING,
                order=3,
            ),
        ]

    elif action.action_type == "payment_batch":
        steps = [
            ActionStepResponse(
                id=f"{action.id}-step-1",
                title="Generate payment batch",
                owner=ActionStepOwner.TAMIO,
                status=ActionStepStatus.COMPLETED,
                order=1,
            ),
            ActionStepResponse(
                id=f"{action.id}-step-2",
                title="Review batch details",
                owner=ActionStepOwner.USER,
                status=ActionStepStatus.COMPLETED if action.status in ["approved", "executed"] else ActionStepStatus.PENDING,
                order=2,
            ),
            ActionStepResponse(
                id=f"{action.id}-step-3",
                title="Upload to bank",
                owner=ActionStepOwner.USER,
                status=ActionStepStatus.COMPLETED if action.status == "executed" else ActionStepStatus.PENDING,
                order=3,
            ),
        ]

    else:
        steps = [
            ActionStepResponse(
                id=f"{action.id}-step-1",
                title="Prepare action",
                owner=ActionStepOwner.TAMIO,
                status=ActionStepStatus.COMPLETED,
                order=1,
            ),
            ActionStepResponse(
                id=f"{action.id}-step-2",
                title="Complete action",
                owner=ActionStepOwner.USER,
                status=ActionStepStatus.COMPLETED if action.status == "executed" else ActionStepStatus.PENDING,
                order=2,
            ),
        ]

    return steps


async def _alert_to_risk(db: AsyncSession, alert: DetectionAlert) -> RiskResponse:
    """Transform DetectionAlert to RiskResponse."""
    # Get linked control IDs
    linked_control_ids = [a.id for a in (alert.prepared_actions or [])]

    # Get current cash position
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == alert.user_id)
    )
    current_cash = float(result.scalar() or 0)

    # Get buffer threshold from user config
    config = await get_or_create_config(db, alert.user_id)
    buffer_amount = float(config.obligations_buffer_amount or 0)
    if buffer_amount <= 0:
        buffer_amount = current_cash * 0.2  # Default to 20% of current cash

    # Compute buffer impact percentage
    buffer_impact = None
    if alert.cash_impact and buffer_amount > 0:
        buffer_impact = round((abs(alert.cash_impact) / buffer_amount) * 100, 1)

    # Generate quantified impact statement
    impact_statement = _generate_impact_statement(alert, current_cash, buffer_amount)

    return RiskResponse(
        id=alert.id,
        title=alert.title,
        severity=_map_severity(alert.severity),
        detected_at=alert.detected_at,
        deadline=alert.deadline,
        days_until_deadline=_compute_days_until(alert.deadline),
        due_horizon_label=_compute_due_horizon_label(alert.deadline),
        cash_impact=alert.cash_impact,
        buffer_impact_percent=buffer_impact,
        impact_statement=impact_statement,
        primary_driver=_extract_primary_driver(alert.context_data or {}),
        detection_type=alert.detection_type,
        context_bullets=_extract_context_bullets(alert.context_data or {}),
        context_data=alert.context_data or {},
        linked_control_ids=linked_control_ids,
        status=_map_risk_status(alert.status),
    )


def _action_to_control(action: PreparedAction) -> ControlResponse:
    """Transform PreparedAction to ControlResponse."""
    state = _map_control_state(action.status)
    tamio_handles, user_handles = _extract_responsibility_split(action)

    # Get linked risk IDs
    linked_risk_ids = [action.alert_id] if action.alert_id else []

    # Get draft content from first option
    draft_content = {}
    impact_amount = None
    if action.options:
        first_option = sorted(action.options, key=lambda x: x.display_order)[0]
        draft_content = first_option.prepared_content or {}
        impact_amount = first_option.cash_impact

    return ControlResponse(
        id=action.id,
        name=action.problem_summary,
        state=state,
        state_label=_get_state_label(state),
        linked_risk_ids=linked_risk_ids,
        action_type=action.action_type,
        why_it_exists=_generate_why_explanation(action),
        tamio_handles=tamio_handles,
        user_handles=user_handles,
        action_steps=_build_action_steps(action),
        deadline=action.deadline,
        created_at=action.created_at,
        approved_at=action.approved_at,
        completed_at=action.executed_at,
        draft_content=draft_content,
        impact_amount=impact_amount,
        rejected_suggestions=[],  # TODO: Track rejected options
    )


# ============================================================================
# Risk Endpoints
# ============================================================================

@router.get("/risks", response_model=RisksListResponse)
async def get_risks(
    severity: Optional[str] = Query(None, description="Filter by severity: urgent, high, normal"),
    timing: Optional[str] = Query(None, description="Filter by timing: today, this_week, next_two_weeks"),
    status: Optional[str] = Query(None, description="Filter by status: active, acknowledged, etc."),
    category: Optional[str] = Query(None, description="Filter by category: obligations, receivables"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all active risks with computed labels.

    Returns risks ordered by severity and deadline.
    """
    query = (
        select(DetectionAlert)
        .options(selectinload(DetectionAlert.prepared_actions))
        .where(DetectionAlert.user_id == user.id)
    )

    # Apply severity filter
    if severity:
        severity_map = {
            "urgent": "emergency",
            "high": "this_week",
            "normal": "upcoming",
        }
        backend_severity = severity_map.get(severity, severity)
        query = query.where(DetectionAlert.severity == backend_severity)

    # Apply category filter
    if category and category in CATEGORY_DETECTION_TYPES:
        detection_types = CATEGORY_DETECTION_TYPES[category]
        query = query.where(DetectionAlert.detection_type.in_(detection_types))

    # Apply status filter (default to active)
    if status:
        query = query.where(DetectionAlert.status == status)
    else:
        # By default, show active and acknowledged alerts
        query = query.where(DetectionAlert.status.in_(["active", "acknowledged", "preparing"]))

    # Apply timing filter
    if timing:
        now = datetime.utcnow()
        if timing == "today":
            end_of_today = now.replace(hour=23, minute=59, second=59)
            query = query.where(
                or_(
                    DetectionAlert.deadline <= end_of_today,
                    DetectionAlert.deadline.is_(None)
                )
            )
        elif timing == "this_week":
            end_of_week = now + timedelta(days=(7 - now.weekday()))
            query = query.where(
                or_(
                    DetectionAlert.deadline <= end_of_week,
                    DetectionAlert.deadline.is_(None)
                )
            )
        elif timing == "next_two_weeks":
            two_weeks = now + timedelta(days=14)
            query = query.where(
                or_(
                    DetectionAlert.deadline <= two_weeks,
                    DetectionAlert.deadline.is_(None)
                )
            )

    # Order by severity (emergency first) then deadline
    query = query.order_by(
        # Custom ordering for severity
        DetectionAlert.severity.asc(),  # 'emergency' < 'this_week' < 'upcoming'
        DetectionAlert.deadline.asc().nullslast(),
    )

    result = await db.execute(query)
    alerts = result.scalars().all()

    risks = [await _alert_to_risk(db, alert) for alert in alerts]

    return RisksListResponse(
        risks=risks,
        total_count=len(risks),
    )


@router.get("/risks/{risk_id}", response_model=RiskResponse)
async def get_risk(
    risk_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single risk by ID with full details."""
    result = await db.execute(
        select(DetectionAlert)
        .options(selectinload(DetectionAlert.prepared_actions))
        .where(DetectionAlert.id == risk_id)
        .where(DetectionAlert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Risk not found")

    return await _alert_to_risk(db, alert)


@router.post("/risks/{risk_id}/dismiss", response_model=SuccessResponse)
async def dismiss_risk(
    risk_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a risk."""
    result = await db.execute(
        select(DetectionAlert)
        .where(DetectionAlert.id == risk_id)
        .where(DetectionAlert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Risk not found")

    alert.status = "dismissed"
    alert.resolved_at = datetime.utcnow()
    await db.commit()

    return SuccessResponse(success=True)


@router.post("/risks/{risk_id}/acknowledge", response_model=SuccessResponse)
async def acknowledge_risk(
    risk_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a risk (mark as seen)."""
    result = await db.execute(
        select(DetectionAlert)
        .where(DetectionAlert.id == risk_id)
        .where(DetectionAlert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Risk not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    await db.commit()

    return SuccessResponse(success=True)


@router.get("/risks/{risk_id}/controls", response_model=ControlsForRiskResponse)
async def get_controls_for_risk(
    risk_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get controls linked to a specific risk."""
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .where(PreparedAction.alert_id == risk_id)
        .where(PreparedAction.user_id == user.id)
    )
    actions = result.scalars().all()

    controls = [_action_to_control(action) for action in actions]

    return ControlsForRiskResponse(controls=controls)


# ============================================================================
# Control Endpoints
# ============================================================================

@router.get("/controls", response_model=ControlsListResponse)
async def get_controls(
    state: Optional[str] = Query(None, description="Filter by state: pending, active, completed, needs_review"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all active controls with state information.
    """
    query = (
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.user_id == user.id)
    )

    # Apply state filter
    if state:
        state_to_status = {
            "pending": ["pending_approval"],
            "active": ["approved", "edited"],
            "completed": ["executed"],
            "needs_review": ["overridden", "skipped", "expired"],
        }
        statuses = state_to_status.get(state, [])
        if statuses:
            query = query.where(PreparedAction.status.in_(statuses))
    else:
        # By default, exclude old completed/skipped
        query = query.where(
            PreparedAction.status.in_(["pending_approval", "approved", "edited", "executed", "overridden"])
        )

    query = query.order_by(
        PreparedAction.deadline.asc().nullslast(),
        PreparedAction.created_at.desc(),
    )

    result = await db.execute(query)
    actions = result.scalars().all()

    controls = [_action_to_control(action) for action in actions]

    return ControlsListResponse(
        controls=controls,
        total_count=len(controls),
    )


@router.get("/controls/{control_id}", response_model=ControlResponse)
async def get_control(
    control_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single control by ID with full details."""
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    return _action_to_control(action)


@router.patch("/controls/{control_id}/state", response_model=ControlUpdateResponse)
async def update_control_state(
    control_id: str,
    request: UpdateControlStateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a control's state.

    Allows transitions including Completed -> Active (bug fix for accidental completions).
    """
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    current_state = _map_control_state(action.status)

    # Define valid transitions
    valid_transitions = {
        ControlState.PENDING: [ControlState.ACTIVE, ControlState.NEEDS_REVIEW],
        ControlState.ACTIVE: [ControlState.COMPLETED, ControlState.NEEDS_REVIEW],
        ControlState.COMPLETED: [ControlState.ACTIVE],  # BUG FIX: Allow reverting
        ControlState.NEEDS_REVIEW: [ControlState.PENDING, ControlState.ACTIVE],
    }

    allowed = valid_transitions.get(current_state, [])
    if request.state not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition from {current_state} to {request.state}"
        )

    # Map frontend state to backend status
    state_to_status = {
        ControlState.PENDING: "pending_approval",
        ControlState.ACTIVE: "approved",
        ControlState.COMPLETED: "executed",
        ControlState.NEEDS_REVIEW: "skipped",
    }

    action.status = state_to_status[request.state]

    if request.state == ControlState.ACTIVE:
        action.approved_at = datetime.utcnow()
        action.executed_at = None  # Clear if reverting from completed
    elif request.state == ControlState.COMPLETED:
        action.executed_at = datetime.utcnow()

    if request.notes:
        action.user_notes = request.notes

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == control_id)
    )
    action = result.scalar_one()

    return ControlUpdateResponse(
        success=True,
        control=_action_to_control(action),
    )


@router.post("/controls/{control_id}/approve", response_model=ControlUpdateResponse)
async def approve_control(
    control_id: str,
    request: ApproveControlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a suggested control."""
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    if action.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Control is not pending approval")

    action.status = "approved"
    action.approved_at = datetime.utcnow()

    if request.option_id:
        action.selected_option_id = request.option_id

    await db.commit()

    # Reload
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == control_id)
    )
    action = result.scalar_one()

    return ControlUpdateResponse(
        success=True,
        control=_action_to_control(action),
    )


@router.post("/controls/{control_id}/reject", response_model=SuccessResponse)
async def reject_control(
    control_id: str,
    request: RejectControlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a suggested control."""
    result = await db.execute(
        select(PreparedAction)
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    action.status = "overridden"
    if request.reason:
        action.user_notes = request.reason

    await db.commit()

    return SuccessResponse(success=True)


@router.post("/controls/{control_id}/complete", response_model=SuccessResponse)
async def complete_control(
    control_id: str,
    request: CompleteControlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a control as completed."""
    result = await db.execute(
        select(PreparedAction)
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    action.status = "executed"
    action.executed_at = datetime.utcnow()

    if request.notes:
        action.user_notes = request.notes

    await db.commit()

    return SuccessResponse(success=True)


@router.get("/controls/{control_id}/risks", response_model=RisksForControlResponse)
async def get_risks_for_control(
    control_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get risks linked to a specific control."""
    # First get the control to find its alert_id
    result = await db.execute(
        select(PreparedAction)
        .where(PreparedAction.id == control_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Control not found")

    if not action.alert_id:
        return RisksForControlResponse(risks=[])

    # Get the linked alert
    result = await db.execute(
        select(DetectionAlert)
        .options(selectinload(DetectionAlert.prepared_actions))
        .where(DetectionAlert.id == action.alert_id)
        .where(DetectionAlert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return RisksForControlResponse(risks=[])

    risk = await _alert_to_risk(db, alert)
    return RisksForControlResponse(risks=[risk])
