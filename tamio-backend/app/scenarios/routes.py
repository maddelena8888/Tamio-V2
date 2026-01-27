"""Scenario Analysis API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.scenarios import models, schemas
from app.scenarios.engine import build_scenario_layer, compute_scenario_forecast
from app.scenarios.rule_engine import evaluate_rules, generate_decision_signals, suggest_scenarios
from app.forecast.engine_v2 import calculate_13_week_forecast
from app.scenarios.pipeline.dependencies import get_suggested_scenarios as get_dependent_suggestions
from app.scenarios.pipeline.types import ScenarioTypeEnum

router = APIRouter()


# ============================================================================
# FINANCIAL RULES ROUTES
# ============================================================================

@router.post("/rules", response_model=schemas.FinancialRuleResponse)
async def create_rule(
    data: schemas.FinancialRuleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new financial safety rule."""
    rule = models.FinancialRule(
        user_id=data.user_id,
        rule_type=data.rule_type,
        name=data.name,
        description=data.description,
        threshold_config=data.threshold_config,
        is_active=data.is_active,
        evaluation_scope=data.evaluation_scope
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.get("/rules", response_model=List[schemas.FinancialRuleResponse])
async def get_rules(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get all financial rules for a user."""
    result = await db.execute(
        select(models.FinancialRule).where(
            models.FinancialRule.user_id == user_id
        )
    )
    return result.scalars().all()


@router.put("/rules/{rule_id}", response_model=schemas.FinancialRuleResponse)
async def update_rule(
    rule_id: str,
    data: schemas.FinancialRuleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a financial rule."""
    result = await db.execute(
        select(models.FinancialRule).where(models.FinancialRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a financial rule."""
    result = await db.execute(
        select(models.FinancialRule).where(models.FinancialRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted successfully"}


# ============================================================================
# SCENARIO ROUTES
# ============================================================================

@router.post("/scenarios", response_model=schemas.ScenarioResponse)
async def create_scenario(
    data: schemas.ScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new scenario."""
    try:
        scenario = models.Scenario(
            user_id=data.user_id,
            name=data.name,
            description=data.description,
            scenario_type=data.scenario_type.value if hasattr(data.scenario_type, 'value') else data.scenario_type,
            entry_path=data.entry_path,
            suggested_reason=data.suggested_reason,
            source_alert_id=data.source_alert_id,
            source_detection_type=data.source_detection_type,
            scope_config=data.scope_config,
            parameters=data.parameters,
            parent_scenario_id=data.parent_scenario_id,
            layer_order=data.layer_order,
            status="draft"
        )
        db.add(scenario)
        await db.commit()
        await db.refresh(scenario)
        return scenario
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create scenario: {str(e)}")


@router.get("/scenarios", response_model=List[schemas.ScenarioResponse])
async def get_scenarios(
    user_id: str = Query(...),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all scenarios for a user, optionally filtered by status."""
    query = select(models.Scenario).where(models.Scenario.user_id == user_id)

    if status:
        query = query.where(models.Scenario.status == status)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/scenarios/suggest")
async def get_suggested_scenarios(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get Tamio-suggested scenarios based on current forecast."""
    # Get base forecast
    base_forecast = await calculate_13_week_forecast(db, user_id)

    # Evaluate rules on base forecast
    evaluations = await evaluate_rules(db, user_id, base_forecast)

    # Generate suggestions
    suggestions = await suggest_scenarios(db, user_id, base_forecast, evaluations)

    return {
        "suggestions": suggestions,
        "based_on": {
            "runway_weeks": base_forecast.get("summary", {}).get("runway_weeks"),
            "has_rule_breaches": any(e.is_breached for e in evaluations)
        }
    }


@router.get("/scenarios/{scenario_id}", response_model=schemas.ScenarioResponse)
async def get_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific scenario."""
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.put("/scenarios/{scenario_id}", response_model=schemas.ScenarioResponse)
async def update_scenario(
    scenario_id: str,
    data: schemas.ScenarioUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a scenario (adjust knobs)."""
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)

    await db.commit()
    await db.refresh(scenario)

    # Rebuild scenario layer with updated parameters
    await _rebuild_scenario_layer(db, scenario)

    return scenario


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete/discard a scenario."""
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Mark as discarded instead of hard delete (for audit trail)
    scenario.status = "discarded"
    await db.commit()

    return {"message": "Scenario discarded"}


@router.post("/scenarios/{scenario_id}/build")
async def build_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Build scenario layer (generate scenario events)."""
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Clear any existing scenario events to ensure fresh build
    await db.execute(
        delete(models.ScenarioEvent).where(
            models.ScenarioEvent.scenario_id == scenario_id
        )
    )

    # Build scenario layer
    scenario_events = await build_scenario_layer(db, scenario)

    # Save scenario events
    for event in scenario_events:
        db.add(event)

    scenario.status = "active"
    await db.commit()

    return {
        "message": "Scenario built successfully",
        "events_generated": len(scenario_events)
    }


@router.post("/scenarios/{scenario_id}/add-layer")
async def add_scenario_layer(
    scenario_id: str,
    layer_data: schemas.ScenarioLayerAdd,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a linked layer to an existing scenario.

    This allows combining multiple related changes (e.g., client loss + contractor reduction)
    into a single scenario for combined impact analysis.
    """
    # Get the parent scenario
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Add the layer to linked_scenarios
    linked_scenarios = scenario.linked_scenarios or []
    layer_entry = {
        "layer_type": layer_data.layer_type,
        "layer_name": layer_data.layer_name or f"{layer_data.layer_type.replace('_', ' ').title()} Layer",
        "parameters": layer_data.parameters,
        "layer_order": len(linked_scenarios) + 1,
        "added_at": datetime.utcnow().isoformat(),
    }
    linked_scenarios.append(layer_entry)
    scenario.linked_scenarios = linked_scenarios

    # Build additional scenario events for this layer
    from app.scenarios.engine import build_scenario_layer_for_type
    layer_events = await build_scenario_layer_for_type(
        db,
        scenario,
        layer_data.layer_type,
        layer_data.parameters,
        layer_attribution=layer_entry["layer_name"]
    )

    # Save additional events
    for event in layer_events:
        db.add(event)

    await db.commit()

    return {
        "message": f"Layer '{layer_entry['layer_name']}' added successfully",
        "events_generated": len(layer_events),
        "total_layers": len(linked_scenarios),
        "linked_scenarios": linked_scenarios
    }


@router.post("/scenarios/{scenario_id}/save")
async def save_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Save scenario for future reference.

    Scenarios are exploratory models and NEVER modify the base forecast.
    They remain as saved explorations that can be viewed and compared.
    """
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Mark scenario as saved (for future viewing/comparison)
    scenario.status = "saved"

    await db.commit()

    return {
        "message": "Scenario saved successfully. It can be viewed under 'Saved Scenarios'.",
        "scenario_id": scenario_id,
        "scenario_name": scenario.name
    }


# ============================================================================
# SCENARIO ANALYSIS ROUTES
# ============================================================================

@router.get("/scenarios/{scenario_id}/forecast", response_model=schemas.ScenarioComparisonResponse)
async def get_scenario_forecast(
    scenario_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get scenario forecast with comparison to base."""
    result = await db.execute(
        select(models.Scenario).where(models.Scenario.id == scenario_id)
    )
    scenario = result.scalar_one_or_none()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Compute scenario forecast
    comparison = await compute_scenario_forecast(db, scenario.user_id, scenario_id)

    # Evaluate rules on scenario forecast
    evaluations = await evaluate_rules(
        db,
        scenario.user_id,
        comparison["scenario_forecast"],
        scenario_id=scenario_id
    )

    # Save evaluations
    for eval in evaluations:
        db.add(eval)
    await db.commit()

    # Generate decision signals
    decision_signals_list = generate_decision_signals(
        evaluations,
        comparison["scenario_forecast"]
    )

    # Get suggested dependent scenarios based on the scenario type
    suggested_scenarios = []
    try:
        scenario_type_enum = ScenarioTypeEnum(scenario.scenario_type)
        suggestions = get_dependent_suggestions(scenario_type_enum)
        suggested_scenarios = [
            {
                "scenario_type": s.scenario_type.value,
                "title": s.title,
                "description": s.description,
                "question": s.question,
                "direction": s.direction.value,
                "typical_lag_weeks": s.typical_lag_weeks,
                "confidence": s.confidence,
                "prefill_params": {
                    **s.prefill_params,
                    "parent_scenario_id": scenario_id,
                }
            }
            for s in suggestions
        ]
    except ValueError:
        # Invalid scenario type, no suggestions
        pass

    return {
        "base_forecast": comparison["base_forecast"],
        "scenario_forecast": comparison["scenario_forecast"],
        "deltas": comparison["deltas"],
        "rule_evaluations": evaluations,
        "decision_signals": {"signals": decision_signals_list},
        "suggested_scenarios": suggested_scenarios
    }


# ============================================================================
# CUSTOM SCENARIO ROUTES (For Transaction Toggle Feature)
# ============================================================================

@router.post("/custom")
async def create_custom_scenario(
    data: schemas.CustomScenarioCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a custom scenario from transaction toggles.

    This endpoint allows users to create scenarios by excluding specific
    transactions from the forecast, simulating what-if analyses without
    those cash flows.

    Args:
        data: CustomScenarioCreate with user_id, name, excluded_transactions, effective_date
        db: Database session

    Returns:
        CustomScenarioResponse with scenario_id and forecast_delta
    """
    try:
        # Create the custom scenario
        scenario = models.Scenario(
            user_id=data.user_id,
            name=data.name or "Custom adjustments",
            description=f"Custom scenario excluding {len(data.excluded_transactions)} transactions",
            scenario_type="custom_exclusion",
            entry_path="toggle_interaction",
            scope_config={
                "excluded_transactions": data.excluded_transactions
            },
            parameters={
                "effective_date": data.effective_date,
                "excluded_count": len(data.excluded_transactions)
            },
            status="active"
        )
        db.add(scenario)
        await db.commit()
        await db.refresh(scenario)

        # Calculate the forecast delta based on excluded transactions
        # For now, we'll compute a simple delta - in production this would
        # use the full forecast engine with exclusions
        forecast_delta = []

        # TODO: Compute actual deltas by re-running forecast with exclusions
        # For MVP, return empty delta list - frontend will handle display

        return {
            "scenario_id": scenario.id,
            "name": scenario.name,
            "forecast_delta": forecast_delta
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create custom scenario: {str(e)}")


# ============================================================================
# RULE EVALUATION ROUTES
# ============================================================================

@router.get("/evaluate/base")
async def evaluate_base_forecast(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Evaluate rules against base forecast."""
    # Get base forecast
    base_forecast = await calculate_13_week_forecast(db, user_id)

    # Evaluate rules
    evaluations = await evaluate_rules(db, user_id, base_forecast)

    # Save evaluations
    for eval in evaluations:
        db.add(eval)
    await db.commit()

    # Generate decision signals
    decision_signals_list = generate_decision_signals(evaluations, base_forecast)

    return {
        "evaluations": evaluations,
        "decision_signals": decision_signals_list
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _rebuild_scenario_layer(
    db: AsyncSession,
    scenario: models.Scenario
):
    """Rebuild scenario layer after parameter changes."""
    # Delete existing scenario events
    await db.execute(
        delete(models.ScenarioEvent).where(
            models.ScenarioEvent.scenario_id == scenario.id
        )
    )

    # Rebuild scenario layer
    scenario_events = await build_scenario_layer(db, scenario)

    # Save new scenario events
    for event in scenario_events:
        db.add(event)

    await db.commit()
