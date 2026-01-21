"""
Action Queue Routes - V4 Architecture

API endpoints for the Action Queue (Stage 3 Approval).
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.data.users.models import User
from app.detection.models import DetectionAlert, AlertSeverity, DetectionRule
from app.preparation.models import PreparedAction, ActionOption, ActionStatus
from app.preparation.engine import PreparationEngine
from app.execution.service import ExecutionService
from app.execution.models import ExecutionRecord
from app.audit.models import AuditLog
from .schemas import (
    ActionQueueResponse,
    ActionCardResponse,
    ActionOptionResponse,
    EntityLink,
    ApproveActionRequest,
    MarkExecutedRequest,
    SkipActionRequest,
    OverrideActionRequest,
    ExecutionArtifactsResponse,
    RecentActivityResponse,
    AgentActivityResponse,
)

router = APIRouter(prefix="/actions", tags=["actions"])


def _calculate_time_remaining(deadline: Optional[datetime]) -> Optional[str]:
    """Calculate human-readable time remaining."""
    if not deadline:
        return None

    now = datetime.utcnow()
    delta = deadline - now

    if delta.total_seconds() < 0:
        return "Overdue"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''}"
    elif delta.seconds > 3600:
        hours = delta.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''}"
    else:
        minutes = delta.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''}"


def _extract_entity_links(alert: Optional[DetectionAlert]) -> list[EntityLink]:
    """
    Extract entity links from alert context_data.

    Looks for known entity ID patterns and creates navigable links.
    """
    if not alert or not alert.context_data:
        return []

    links = []
    ctx = alert.context_data

    # Client-related entities
    if ctx.get("client_id"):
        links.append(EntityLink(
            entity_type="client",
            entity_id=ctx["client_id"],
            entity_name=ctx.get("client_name", "Client"),
            route="/clients-expenses",
        ))

    # Check for causing_payments array (late payment alerts)
    for payment in ctx.get("causing_payments", []):
        if payment.get("client_name") and payment.get("schedule_id"):
            # Avoid duplicates if client_id was already added
            client_name = payment.get("client_name")
            if not any(l.entity_name == client_name for l in links):
                links.append(EntityLink(
                    entity_type="client",
                    entity_id=payment.get("schedule_id"),
                    entity_name=client_name,
                    route="/clients-expenses",
                ))

    # Expense/vendor-related entities
    if ctx.get("bucket_id") or ctx.get("expense_bucket_id"):
        bucket_id = ctx.get("bucket_id") or ctx.get("expense_bucket_id")
        links.append(EntityLink(
            entity_type="expense",
            entity_id=bucket_id,
            entity_name=ctx.get("bucket_name", ctx.get("vendor_name", "Expense")),
            route="/clients-expenses",
        ))

    if ctx.get("vendor_id") and not ctx.get("bucket_id"):
        links.append(EntityLink(
            entity_type="vendor",
            entity_id=ctx["vendor_id"],
            entity_name=ctx.get("vendor_name", "Vendor"),
            route="/clients-expenses",
        ))

    # Obligation-related entities
    if ctx.get("obligation_id"):
        links.append(EntityLink(
            entity_type="obligation",
            entity_id=ctx["obligation_id"],
            entity_name=ctx.get("obligation_name", "Obligation"),
            route="/clients-expenses",
        ))

    return links


def _action_to_card(action: PreparedAction) -> ActionCardResponse:
    """Convert PreparedAction to ActionCardResponse."""
    # Determine urgency
    urgency = AlertSeverity.UPCOMING
    if action.alert:
        urgency = action.alert.severity
    elif action.deadline:
        days_until = (action.deadline - datetime.utcnow()).days
        if days_until <= 1:
            urgency = AlertSeverity.EMERGENCY
        elif days_until <= 7:
            urgency = AlertSeverity.THIS_WEEK

    # Convert options
    options = [
        ActionOptionResponse(
            id=opt.id,
            title=opt.title,
            description=opt.description,
            risk_level=opt.risk_level,
            is_recommended=bool(opt.is_recommended),
            reasoning=opt.reasoning or [],
            risk_score=opt.risk_score,
            cash_impact=opt.cash_impact,
            impact_description=opt.impact_description,
            prepared_content=opt.prepared_content or {},
            success_probability=opt.success_probability,
            display_order=opt.display_order,
        )
        for opt in sorted(action.options, key=lambda x: x.display_order)
    ]

    # Extract entity links from the alert's context_data
    entity_links = _extract_entity_links(action.alert)

    return ActionCardResponse(
        id=action.id,
        action_type=action.action_type,
        status=action.status,
        urgency=urgency,
        problem_summary=action.problem_summary,
        problem_context=action.problem_context,
        options=options,
        created_at=action.created_at,
        deadline=action.deadline,
        time_remaining=_calculate_time_remaining(action.deadline),
        linked_action_ids=[],  # Would come from LinkedAction table
        entity_links=entity_links,
    )


@router.get("/queue", response_model=ActionQueueResponse)
async def get_action_queue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the action queue organized by urgency.

    Returns all pending actions grouped into:
    - Emergency: Must act today
    - This Week: Needs attention soon
    - Upcoming: Monitoring only
    """
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.user_id == user.id)
        .where(PreparedAction.status == ActionStatus.PENDING_APPROVAL)
        .order_by(PreparedAction.deadline.asc().nullslast())
    )
    actions = result.scalars().all()

    emergency = []
    this_week = []
    upcoming = []

    for action in actions:
        card = _action_to_card(action)

        if card.urgency == AlertSeverity.EMERGENCY:
            emergency.append(card)
        elif card.urgency == AlertSeverity.THIS_WEEK:
            this_week.append(card)
        else:
            upcoming.append(card)

    return ActionQueueResponse(
        emergency=emergency,
        this_week=this_week,
        upcoming=upcoming,
        emergency_count=len(emergency),
        this_week_count=len(this_week),
        upcoming_count=len(upcoming),
        total_count=len(actions),
    )


@router.get("/{action_id}", response_model=ActionCardResponse)
async def get_action(
    action_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single action by ID."""
    result = await db.execute(
        select(PreparedAction)
        .options(selectinload(PreparedAction.options))
        .options(selectinload(PreparedAction.alert))
        .where(PreparedAction.id == action_id)
        .where(PreparedAction.user_id == user.id)
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    return _action_to_card(action)


@router.post("/{action_id}/approve", response_model=ActionCardResponse)
async def approve_action(
    action_id: str,
    request: ApproveActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve an action with the selected option.

    Moves the action to the execution queue.
    """
    service = ExecutionService(db, user.id)

    try:
        action = await service.approve_action(
            action_id=action_id,
            option_id=request.option_id,
            edited_content=request.edited_content,
        )
        await db.commit()

        # Reload with relationships
        await db.refresh(action)
        result = await db.execute(
            select(PreparedAction)
            .options(selectinload(PreparedAction.options))
            .options(selectinload(PreparedAction.alert))
            .where(PreparedAction.id == action_id)
        )
        action = result.scalar_one()

        return _action_to_card(action)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{action_id}/execute")
async def mark_executed(
    action_id: str,
    request: MarkExecutedRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark an approved action as executed.

    Used in V1 manual flow when user has completed the action externally.
    """
    service = ExecutionService(db, user.id)

    try:
        record = await service.mark_executed(
            action_id=action_id,
            external_reference=request.external_reference,
            notes=request.notes,
        )
        await db.commit()

        return {"status": "executed", "execution_id": record.id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{action_id}/skip", response_model=ActionCardResponse)
async def skip_action(
    action_id: str,
    request: SkipActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Skip an action (defer decision).

    Action is archived but can be viewed in history.
    """
    service = ExecutionService(db, user.id)

    try:
        action = await service.skip_action(
            action_id=action_id,
            reason=request.reason,
        )
        await db.commit()

        # Reload with relationships
        result = await db.execute(
            select(PreparedAction)
            .options(selectinload(PreparedAction.options))
            .options(selectinload(PreparedAction.alert))
            .where(PreparedAction.id == action_id)
        )
        action = result.scalar_one()

        return _action_to_card(action)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{action_id}/override", response_model=ActionCardResponse)
async def override_action(
    action_id: str,
    request: OverrideActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Override an action (reject recommendation, handle manually).

    User takes manual control outside Tamio.
    """
    service = ExecutionService(db, user.id)

    try:
        action = await service.override_action(
            action_id=action_id,
            reason=request.reason,
        )
        await db.commit()

        # Reload with relationships
        result = await db.execute(
            select(PreparedAction)
            .options(selectinload(PreparedAction.options))
            .options(selectinload(PreparedAction.alert))
            .where(PreparedAction.id == action_id)
        )
        action = result.scalar_one()

        return _action_to_card(action)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{action_id}/artifacts", response_model=ExecutionArtifactsResponse)
async def get_execution_artifacts(
    action_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get execution artifacts for an approved action.

    Returns ready-to-use content:
    - Email: subject, body, recipient
    - Payment batch: CSV data, instructions
    - Call: talking points
    """
    service = ExecutionService(db, user.id)
    artifacts = await service.get_execution_artifacts(action_id)

    if not artifacts:
        raise HTTPException(status_code=404, detail="No artifacts found")

    return ExecutionArtifactsResponse(**artifacts)


@router.get("/execution/queue")
async def get_execution_queue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all approved actions waiting for execution.
    """
    service = ExecutionService(db, user.id)
    actions = await service.get_execution_queue()

    return [_action_to_card(a) for a in actions]


@router.get("/execution/activity", response_model=list[RecentActivityResponse])
async def get_recent_activity(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get recent execution activity.

    Shows what has been executed recently for the activity log.
    """
    service = ExecutionService(db, user.id)
    records = await service.get_recent_activity(limit=limit)

    return [
        RecentActivityResponse(
            id=r.id,
            action_id=r.action_id,
            action_type=r.action.action_type.value if r.action else "unknown",
            method=r.method.value,
            result=r.result.value,
            executed_at=r.executed_at,
            notes=r.notes,
        )
        for r in records
    ]


@router.get("/agent-activity", response_model=AgentActivityResponse)
async def get_agent_activity(
    hours: int = 24,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get aggregated agent activity statistics for the homepage.

    Returns counts of:
    - Simulations run (forecast calculations)
    - Invoices/payments scanned (sync events)
    - Forecasts updated (execution records)
    - Active agents (enabled detection rules)

    Args:
        hours: Number of hours to look back (default: 24)
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Count forecast calculations from audit logs
    simulations_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.entity_type == "forecast",
                AuditLog.action == "create",
                AuditLog.created_at >= since,
            )
        )
    )
    simulations_run = simulations_result.scalar() or 0

    # Count sync events (invoices/payments scanned)
    scans_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.user_id == user.id,
                AuditLog.action.in_(["sync_pull", "sync_push"]),
                AuditLog.created_at >= since,
            )
        )
    )
    invoices_scanned = scans_result.scalar() or 0

    # Count execution records (actions executed)
    executions_result = await db.execute(
        select(func.count(ExecutionRecord.id)).where(
            and_(
                ExecutionRecord.user_id == user.id,
                ExecutionRecord.executed_at >= since,
            )
        )
    )
    forecasts_updated = executions_result.scalar() or 0

    # Count active detection rules
    active_agents_result = await db.execute(
        select(func.count(DetectionRule.id)).where(
            and_(
                DetectionRule.user_id == user.id,
                DetectionRule.enabled == True,
            )
        )
    )
    active_agents = active_agents_result.scalar() or 0

    return AgentActivityResponse(
        simulations_run=simulations_run,
        invoices_scanned=invoices_scanned,
        forecasts_updated=forecasts_updated,
        active_agents=active_agents,
    )
