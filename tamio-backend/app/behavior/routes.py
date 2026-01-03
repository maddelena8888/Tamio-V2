"""
Behavior Routes - API endpoints for behavior insights and triggers.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.behavior.engine import calculate_all_behavior_metrics
from app.behavior.triggers import (
    evaluate_triggers,
    get_active_triggers,
    get_pending_triggered_scenarios,
    respond_to_triggered_scenario,
)
from app.behavior.generator import (
    generate_scenarios_from_triggers,
    get_recommended_actions,
    estimate_scenario_impact,
)
from app.behavior.models import BehaviorMetric, BehaviorTrigger, TriggeredScenario
from app.behavior.schemas import (
    BehaviorInsightsResponse,
    BehaviorMetricResponse,
    TriggeredScenarioResponse,
    TriggeredScenarioAction,
)
from sqlalchemy import select

router = APIRouter(prefix="/behavior", tags=["behavior"])


# =============================================================================
# Behavior Insights Endpoints
# =============================================================================

@router.get("/insights", response_model=BehaviorInsightsResponse)
async def get_behavior_insights(
    user_id: str = Query(..., description="User ID"),
    buffer_months: int = Query(3, description="Target buffer months"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete behavior insights for a user.

    This endpoint calculates all behavior metrics and evaluates triggers,
    returning:
    - Client behavior (concentration, reliability, revenue at risk)
    - Expense behavior (volatility, discretionary ratio, commitments)
    - Cash discipline (buffer integrity, burn momentum, decision quality)
    - Triggered scenarios from behavior pattern changes
    """
    # Calculate all metrics
    insights, metrics = await calculate_all_behavior_metrics(
        db, user_id, buffer_months
    )

    # Evaluate triggers and generate scenarios
    triggered = await evaluate_triggers(db, user_id, metrics)

    # Add triggered scenarios to response
    triggered_responses = []
    for ts in triggered:
        triggered_responses.append(TriggeredScenarioResponse(
            id=ts.id,
            trigger_name=ts.scenario_name,
            trigger_description=ts.scenario_description,
            scenario_name=ts.scenario_name,
            scenario_description=ts.scenario_description,
            scenario_type=ts.scenario_type,
            scenario_parameters=ts.scenario_parameters,
            severity=ts.severity,
            estimated_impact=ts.estimated_impact,
            recommended_actions=ts.recommended_actions,
            status=ts.status,
            triggered_at=ts.triggered_at or datetime.utcnow(),
            expires_at=ts.expires_at,
        ))

    # Also include pending scenarios from previous evaluations
    pending = await get_pending_triggered_scenarios(db, user_id)
    for ts in pending:
        if ts.id not in [t.id for t in triggered]:
            triggered_responses.append(TriggeredScenarioResponse(
                id=ts.id,
                trigger_name=ts.scenario_name,
                trigger_description=ts.scenario_description,
                scenario_name=ts.scenario_name,
                scenario_description=ts.scenario_description,
                scenario_type=ts.scenario_type,
                scenario_parameters=ts.scenario_parameters,
                severity=ts.severity,
                estimated_impact=ts.estimated_impact,
                recommended_actions=ts.recommended_actions,
                status=ts.status,
                triggered_at=ts.triggered_at or datetime.utcnow(),
                expires_at=ts.expires_at,
            ))

    insights.triggered_scenarios = triggered_responses
    insights.pending_scenarios_count = len(triggered_responses)

    return insights


@router.get("/metrics")
async def get_behavior_metrics(
    user_id: str = Query(..., description="User ID"),
    metric_type: Optional[str] = Query(None, description="Filter by metric type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    db: AsyncSession = Depends(get_db)
) -> List[BehaviorMetricResponse]:
    """
    Get stored behavior metrics for a user.
    """
    query = select(BehaviorMetric).where(BehaviorMetric.user_id == user_id)

    if metric_type:
        query = query.where(BehaviorMetric.metric_type == metric_type)
    if entity_type:
        query = query.where(BehaviorMetric.entity_type == entity_type)

    query = query.order_by(BehaviorMetric.computed_at.desc())

    result = await db.execute(query)
    metrics = list(result.scalars().all())

    return [
        BehaviorMetricResponse(
            id=m.id,
            user_id=m.user_id,
            metric_type=m.metric_type,
            entity_type=m.entity_type,
            entity_id=m.entity_id,
            current_value=m.current_value,
            previous_value=m.previous_value,
            mean=m.mean,
            variance=m.variance,
            std_dev=m.std_dev,
            trend=m.trend,
            trend_velocity=m.trend_velocity,
            trend_confidence=m.trend_confidence,
            threshold_warning=m.threshold_warning,
            threshold_critical=m.threshold_critical,
            is_higher_better=m.is_higher_better,
            is_breached=m.is_breached(),
            is_warning=m.is_warning(),
            data_confidence=m.data_confidence,
            context_data=m.context_data,
            computed_at=m.computed_at,
        )
        for m in metrics
    ]


# =============================================================================
# Trigger Endpoints
# =============================================================================

@router.get("/triggers")
async def get_triggers(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    Get all active triggers for a user.
    """
    triggers = await get_active_triggers(db, user_id)

    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "conditions": t.conditions,
            "scenario_template": t.scenario_template,
            "recommended_actions": t.recommended_actions,
            "severity": t.severity,
            "priority": t.priority,
            "is_active": t.is_active,
            "cooldown_hours": t.cooldown_hours,
            "last_triggered_at": t.last_triggered_at,
        }
        for t in triggers
    ]


@router.post("/triggers/{trigger_id}/toggle")
async def toggle_trigger(
    trigger_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Toggle a trigger's active state.
    """
    result = await db.execute(
        select(BehaviorTrigger).where(BehaviorTrigger.id == trigger_id)
    )
    trigger = result.scalar_one_or_none()

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    trigger.is_active = not trigger.is_active
    await db.commit()

    return {"id": trigger.id, "is_active": trigger.is_active}


# =============================================================================
# Triggered Scenario Endpoints
# =============================================================================

@router.get("/triggered-scenarios")
async def get_triggered_scenarios(
    user_id: str = Query(..., description="User ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db)
) -> List[TriggeredScenarioResponse]:
    """
    Get triggered scenarios for a user.
    """
    query = select(TriggeredScenario).where(TriggeredScenario.user_id == user_id)

    if status:
        query = query.where(TriggeredScenario.status == status)

    query = query.order_by(TriggeredScenario.triggered_at.desc())

    result = await db.execute(query)
    scenarios = list(result.scalars().all())

    return [
        TriggeredScenarioResponse(
            id=ts.id,
            trigger_name=ts.scenario_name,
            trigger_description=ts.scenario_description,
            scenario_name=ts.scenario_name,
            scenario_description=ts.scenario_description,
            scenario_type=ts.scenario_type,
            scenario_parameters=ts.scenario_parameters,
            severity=ts.severity,
            estimated_impact=ts.estimated_impact,
            recommended_actions=ts.recommended_actions,
            status=ts.status,
            triggered_at=ts.triggered_at or datetime.utcnow(),
            expires_at=ts.expires_at,
        )
        for ts in scenarios
    ]


@router.post("/triggered-scenarios/{scenario_id}/respond")
async def respond_to_scenario(
    scenario_id: str,
    action: TriggeredScenarioAction,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Respond to a triggered scenario.

    Actions:
    - run_scenario: Create and run the suggested scenario
    - dismiss: Dismiss the triggered scenario
    - defer: Defer the scenario for later review
    """
    try:
        ts = await respond_to_triggered_scenario(
            db,
            scenario_id,
            action.action,
            action.notes,
        )

        return {
            "id": ts.id,
            "status": ts.status,
            "user_response": ts.user_response,
            "responded_at": ts.responded_at,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/triggered-scenarios/{scenario_id}/actions")
async def get_scenario_actions(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """
    Get detailed recommended actions for a triggered scenario.
    """
    result = await db.execute(
        select(TriggeredScenario).where(TriggeredScenario.id == scenario_id)
    )
    ts = result.scalar_one_or_none()

    if not ts:
        raise HTTPException(status_code=404, detail="Triggered scenario not found")

    actions = get_recommended_actions(ts, ts.trigger_context)
    return actions


@router.get("/triggered-scenarios/{scenario_id}/impact")
async def get_scenario_impact(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get estimated impact for a triggered scenario.
    """
    result = await db.execute(
        select(TriggeredScenario).where(TriggeredScenario.id == scenario_id)
    )
    ts = result.scalar_one_or_none()

    if not ts:
        raise HTTPException(status_code=404, detail="Triggered scenario not found")

    # Get current metrics for impact calculation
    metrics_result = await db.execute(
        select(BehaviorMetric)
        .where(BehaviorMetric.user_id == ts.user_id)
        .where(BehaviorMetric.metric_type == "buffer_integrity")
        .order_by(BehaviorMetric.computed_at.desc())
        .limit(1)
    )
    buffer_metric = metrics_result.scalar_one_or_none()

    current_metrics = {
        "buffer": buffer_metric.current_value if buffer_metric else 50000,
    }

    impact = estimate_scenario_impact(ts, current_metrics)
    return impact


@router.post("/triggered-scenarios/{scenario_id}/generate")
async def generate_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Generate a full scenario from a triggered scenario.

    This creates a Scenario that can be run through the forecast engine.
    """
    result = await db.execute(
        select(TriggeredScenario).where(TriggeredScenario.id == scenario_id)
    )
    ts = result.scalar_one_or_none()

    if not ts:
        raise HTTPException(status_code=404, detail="Triggered scenario not found")

    generated = await generate_scenarios_from_triggers(
        db, ts.user_id, [ts], auto_create=True
    )

    if generated:
        return generated[0]
    else:
        raise HTTPException(status_code=500, detail="Failed to generate scenario")
