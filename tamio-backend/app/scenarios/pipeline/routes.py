"""
Scenario Pipeline API Routes.

Implements the multi-step scenario pipeline endpoints:
- POST /pipeline/seed - Initialize a new scenario
- POST /pipeline/{id}/answers - Submit answers to prompts
- GET /pipeline/{id}/status - Get current pipeline state
- POST /pipeline/{id}/commit - Commit scenario to canonical data
- POST /pipeline/{id}/discard - Discard scenario
- POST /pipeline/{id}/iterate - Restart with new parameters
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.scenarios.pipeline import (
    ScenarioPipeline,
    ScenarioDefinition,
    ScenarioDelta,
    PipelineResult,
    PromptRequest,
)
from app.scenarios.pipeline.types import (
    ScenarioTypeEnum,
    EntryPath,
    ScenarioStatusEnum,
    PipelineStage,
)
from app.scenarios.pipeline.dependencies import (
    get_suggested_scenarios,
    format_suggestions_for_ui,
    get_high_priority_suggestions,
    SuggestedScenario,
)


router = APIRouter(prefix="/pipeline", tags=["Scenario Pipeline"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class SeedScenarioRequest(BaseModel):
    """Request to initialize a new scenario."""
    user_id: str
    scenario_type: ScenarioTypeEnum
    entry_path: EntryPath = EntryPath.MANUAL
    name: Optional[str] = None
    suggested_reason: Optional[str] = None


class SubmitAnswersRequest(BaseModel):
    """Request to submit answers to prompts."""
    answers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Map of maps_to path to answer value"
    )


class PipelineStatusResponse(BaseModel):
    """Response with current pipeline status."""
    scenario_id: str
    status: ScenarioStatusEnum
    current_stage: PipelineStage
    completed_stages: List[PipelineStage]
    is_complete: bool

    # Pending prompts
    pending_prompts: List[Dict[str, Any]] = Field(default_factory=list)

    # Suggested dependent scenarios (shown when scenario is complete)
    suggested_scenarios: List[Dict[str, Any]] = Field(default_factory=list)

    # Results (if available)
    delta_summary: Optional[Dict[str, Any]] = None
    base_forecast_summary: Optional[Dict[str, Any]] = None
    scenario_forecast_summary: Optional[Dict[str, Any]] = None
    rule_results: List[Dict[str, Any]] = Field(default_factory=list)

    # Errors/warnings
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class CommitResponse(BaseModel):
    """Response after committing a scenario."""
    success: bool
    scenario_id: str
    events_created: int = 0
    events_updated: int = 0
    events_deleted: int = 0
    message: str


class DiscardResponse(BaseModel):
    """Response after discarding a scenario."""
    success: bool
    scenario_id: str
    message: str


# =============================================================================
# IN-MEMORY SCENARIO STORAGE (for demo - use Redis/DB in production)
# =============================================================================

# Store active scenarios in memory
_active_scenarios: Dict[str, ScenarioDefinition] = {}
_scenario_deltas: Dict[str, ScenarioDelta] = {}


def _store_scenario(definition: ScenarioDefinition):
    """Store scenario definition."""
    _active_scenarios[definition.scenario_id] = definition


def _get_scenario(scenario_id: str) -> Optional[ScenarioDefinition]:
    """Get stored scenario definition."""
    return _active_scenarios.get(scenario_id)


def _store_delta(scenario_id: str, delta: ScenarioDelta):
    """Store scenario delta."""
    _scenario_deltas[scenario_id] = delta


def _get_delta(scenario_id: str) -> Optional[ScenarioDelta]:
    """Get stored delta."""
    return _scenario_deltas.get(scenario_id)


def _remove_scenario(scenario_id: str):
    """Remove scenario from storage."""
    _active_scenarios.pop(scenario_id, None)
    _scenario_deltas.pop(scenario_id, None)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/seed", response_model=PipelineStatusResponse)
async def seed_scenario(
    request: SeedScenarioRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Stage 1: Initialize a new scenario.

    Creates a scenario definition and returns initial prompts for scope/params.
    """
    pipeline = ScenarioPipeline(db)

    # Seed the scenario
    definition = await pipeline.seed_scenario(
        user_id=request.user_id,
        scenario_type=request.scenario_type,
        entry_path=request.entry_path,
        name=request.name,
        suggested_reason=request.suggested_reason,
    )

    # Run pipeline to get initial prompts
    result = await pipeline.run_pipeline(definition)

    # Store for subsequent calls
    _store_scenario(result.scenario_definition)
    if result.delta:
        _store_delta(result.scenario_id, result.delta)

    return _build_status_response(result)


@router.post("/{scenario_id}/answers", response_model=PipelineStatusResponse)
async def submit_answers(
    scenario_id: str,
    request: SubmitAnswersRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit answers to pending prompts and advance the pipeline.

    The pipeline will continue until it either:
    - Needs more answers (returns new prompts)
    - Completes simulation (returns results)
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    pipeline = ScenarioPipeline(db)

    # Run pipeline with answers
    result = await pipeline.run_pipeline(definition, request.answers)

    # Update storage
    _store_scenario(result.scenario_definition)
    if result.delta:
        _store_delta(result.scenario_id, result.delta)

    return _build_status_response(result)


@router.get("/{scenario_id}/status", response_model=PipelineStatusResponse)
async def get_status(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current pipeline status for a scenario.

    Returns current stage, pending prompts, and any computed results.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    delta = _get_delta(scenario_id)

    # Build response from current state
    return PipelineStatusResponse(
        scenario_id=scenario_id,
        status=definition.status,
        current_stage=definition.current_stage,
        completed_stages=definition.completed_stages,
        is_complete=definition.status == ScenarioStatusEnum.SIMULATED,
        pending_prompts=[p.model_dump() for p in definition.pending_prompts],
        delta_summary=_delta_to_dict(delta) if delta else None,
    )


@router.post("/{scenario_id}/commit", response_model=CommitResponse)
async def commit_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Commit the scenario to canonical data.

    This applies all changes (created, updated, deleted events) to the
    canonical database. Only works for SIMULATED scenarios.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    if definition.status != ScenarioStatusEnum.SIMULATED:
        raise HTTPException(
            status_code=400,
            detail=f"Scenario must be SIMULATED to commit. Current status: {definition.status}"
        )

    delta = _get_delta(scenario_id)
    if not delta:
        raise HTTPException(status_code=400, detail="No delta computed for this scenario")

    pipeline = ScenarioPipeline(db)

    try:
        success = await pipeline.commit_scenario(definition, delta)

        if success:
            _store_scenario(definition)  # Update with CONFIRMED status

            return CommitResponse(
                success=True,
                scenario_id=scenario_id,
                events_created=len(delta.created_events),
                events_updated=len(delta.updated_events),
                events_deleted=len(delta.deleted_event_ids),
                message="Scenario committed successfully. Canonical data updated.",
            )
        else:
            return CommitResponse(
                success=False,
                scenario_id=scenario_id,
                message="Failed to commit scenario.",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{scenario_id}/discard", response_model=DiscardResponse)
async def discard_scenario(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Discard the scenario without making any changes.

    The scenario is marked as DISCARDED and can no longer be committed.
    Base forecast remains unchanged.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    if definition.status == ScenarioStatusEnum.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail="Cannot discard a confirmed scenario"
        )

    pipeline = ScenarioPipeline(db)
    await pipeline.discard_scenario(definition)

    _store_scenario(definition)  # Update with DISCARDED status

    return DiscardResponse(
        success=True,
        scenario_id=scenario_id,
        message="Scenario discarded. No changes made to canonical data.",
    )


@router.post("/{scenario_id}/iterate", response_model=PipelineStatusResponse)
async def iterate_scenario(
    scenario_id: str,
    request: SubmitAnswersRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Iterate on a scenario with new parameters.

    Resets the scenario to DRAFT and re-runs the pipeline with new inputs.
    Useful for adjusting "knobs" without starting over.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    if definition.status == ScenarioStatusEnum.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail="Cannot iterate on a confirmed scenario"
        )

    # Reset to draft
    definition.status = ScenarioStatusEnum.DRAFT
    definition.current_stage = PipelineStage.SCOPE
    definition.completed_stages = []
    definition.pending_prompts = []

    # Clear existing delta
    _scenario_deltas.pop(scenario_id, None)

    pipeline = ScenarioPipeline(db)

    # Re-run pipeline with new answers merged with existing
    merged_answers = {**definition.parameters, **request.answers}
    result = await pipeline.run_pipeline(definition, merged_answers)

    _store_scenario(result.scenario_definition)
    if result.delta:
        _store_delta(result.scenario_id, result.delta)

    return _build_status_response(result)


@router.get("/{scenario_id}/forecast", response_model=Dict[str, Any])
async def get_scenario_forecast(
    scenario_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed forecast comparison for a scenario.

    Returns base forecast, scenario forecast, and week-by-week deltas.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    if definition.status not in [ScenarioStatusEnum.SIMULATED, ScenarioStatusEnum.CONFIRMED]:
        raise HTTPException(
            status_code=400,
            detail="Scenario must be SIMULATED or CONFIRMED to view forecast"
        )

    delta = _get_delta(scenario_id)
    if not delta:
        raise HTTPException(status_code=400, detail="No delta computed for this scenario")

    pipeline = ScenarioPipeline(db)

    base_summary, scenario_summary, delta_summary = await pipeline.build_scenario_layer(
        definition, delta
    )

    return {
        "scenario_id": scenario_id,
        "scenario_name": definition.name,
        "scenario_type": definition.scenario_type.value,
        "status": definition.status.value,
        "base_forecast": {
            "starting_cash": str(base_summary.starting_cash),
            "weeks": [
                {
                    "week_number": w.week_number,
                    "week_start": w.week_start.isoformat(),
                    "week_end": w.week_end.isoformat(),
                    "starting_balance": str(w.starting_balance),
                    "cash_in": str(w.cash_in),
                    "cash_out": str(w.cash_out),
                    "net_change": str(w.net_change),
                    "ending_balance": str(w.ending_balance),
                }
                for w in base_summary.weeks
            ],
            "summary": {
                "lowest_cash_week": base_summary.lowest_cash_week,
                "lowest_cash_amount": str(base_summary.lowest_cash_amount),
                "total_cash_in": str(base_summary.total_cash_in),
                "total_cash_out": str(base_summary.total_cash_out),
                "runway_weeks": base_summary.runway_weeks,
            }
        },
        "scenario_forecast": {
            "starting_cash": str(scenario_summary.starting_cash),
            "weeks": [
                {
                    "week_number": w.week_number,
                    "week_start": w.week_start.isoformat(),
                    "week_end": w.week_end.isoformat(),
                    "starting_balance": str(w.starting_balance),
                    "cash_in": str(w.cash_in),
                    "cash_out": str(w.cash_out),
                    "net_change": str(w.net_change),
                    "ending_balance": str(w.ending_balance),
                }
                for w in scenario_summary.weeks
            ],
            "summary": {
                "lowest_cash_week": scenario_summary.lowest_cash_week,
                "lowest_cash_amount": str(scenario_summary.lowest_cash_amount),
                "total_cash_in": str(scenario_summary.total_cash_in),
                "total_cash_out": str(scenario_summary.total_cash_out),
                "runway_weeks": scenario_summary.runway_weeks,
            }
        },
        "delta": {
            "week_deltas": delta_summary.week_deltas,
            "top_changed_weeks": delta_summary.top_changed_weeks,
            "net_cash_in_change": str(delta_summary.net_cash_in_change),
            "net_cash_out_change": str(delta_summary.net_cash_out_change),
            "runway_change": delta_summary.runway_change,
        }
    }


@router.get("/scenarios", response_model=List[Dict[str, Any]])
async def list_active_scenarios(
    user_id: str,
    status: Optional[ScenarioStatusEnum] = None,
):
    """
    List all active scenarios for a user.

    Optionally filter by status.
    """
    scenarios = []

    for scenario_id, definition in _active_scenarios.items():
        if definition.user_id != user_id:
            continue
        if status and definition.status != status:
            continue

        scenarios.append({
            "scenario_id": scenario_id,
            "name": definition.name,
            "scenario_type": definition.scenario_type.value,
            "status": definition.status.value,
            "current_stage": definition.current_stage.value,
            "created_at": definition.created_at.isoformat() if definition.created_at else None,
            "entry_path": definition.entry_path.value,
        })

    return scenarios


# =============================================================================
# DEPENDENT SCENARIO ENDPOINTS
# =============================================================================

@router.get("/suggestions/{scenario_type}", response_model=List[Dict[str, Any]])
async def get_scenario_suggestions(
    scenario_type: ScenarioTypeEnum,
    include_low_confidence: bool = True,
):
    """
    Get suggested dependent scenarios for a given scenario type.

    This endpoint returns what scenarios typically follow or should be
    considered alongside the given scenario type.

    Args:
        scenario_type: The primary scenario type
        include_low_confidence: Whether to include low-confidence suggestions

    Returns:
        List of suggested scenarios with questions to ask the user
    """
    suggestions = get_suggested_scenarios(scenario_type, include_low_confidence)

    return [
        {
            "scenario_type": s.scenario_type.value,
            "title": s.title,
            "description": s.description,
            "question": s.question,
            "direction": s.direction.value,
            "typical_lag_weeks": s.typical_lag_weeks,
            "confidence": s.confidence,
            "prefill_params": s.prefill_params,
        }
        for s in suggestions
    ]


@router.get("/{scenario_id}/suggestions", response_model=List[Dict[str, Any]])
async def get_scenario_specific_suggestions(
    scenario_id: str,
):
    """
    Get suggested dependent scenarios for a specific scenario.

    Returns suggestions based on the scenario type, with pre-filled
    parameters linking back to the parent scenario.
    """
    definition = _get_scenario(scenario_id)
    if not definition:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    return format_suggestions_for_ui(definition.scenario_type, scenario_id)


class CreateLinkedScenarioRequest(BaseModel):
    """Request to create a linked scenario from a suggestion."""
    user_id: str
    parent_scenario_id: str
    suggested_scenario_type: ScenarioTypeEnum
    prefill_params: Dict[str, Any] = Field(default_factory=dict)
    name: Optional[str] = None


@router.post("/linked", response_model=PipelineStatusResponse)
async def create_linked_scenario(
    request: CreateLinkedScenarioRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new scenario linked to a parent scenario.

    This is used when the user accepts a suggested dependent scenario.
    The new scenario is pre-filled with relevant parameters and linked
    to the parent scenario.
    """
    parent = _get_scenario(request.parent_scenario_id)
    if not parent:
        raise HTTPException(
            status_code=404,
            detail=f"Parent scenario {request.parent_scenario_id} not found"
        )

    pipeline = ScenarioPipeline(db)

    # Create the linked scenario with reference to parent
    definition = await pipeline.seed_scenario(
        user_id=request.user_id,
        scenario_type=request.suggested_scenario_type,
        entry_path=EntryPath.TAMIO_SUGGESTED,
        name=request.name or f"Linked: {request.suggested_scenario_type.value}",
        suggested_reason=f"Suggested from {parent.scenario_type.value} scenario",
    )

    # Link to parent and pre-fill parameters
    definition.parent_scenario_id = request.parent_scenario_id
    definition.parameters.update(request.prefill_params)

    # Run pipeline with pre-filled params
    result = await pipeline.run_pipeline(definition, request.prefill_params)

    # Store for subsequent calls
    _store_scenario(result.scenario_definition)
    if result.delta:
        _store_delta(result.scenario_id, result.delta)

    return _build_status_response(result)


@router.get("/{scenario_id}/linked", response_model=List[Dict[str, Any]])
async def get_linked_scenarios(
    scenario_id: str,
):
    """
    Get all scenarios linked to a parent scenario.

    Returns scenarios that were created from suggestions or manually
    linked to the specified parent scenario.
    """
    linked = []

    for sid, definition in _active_scenarios.items():
        if definition.parent_scenario_id == scenario_id:
            linked.append({
                "scenario_id": sid,
                "name": definition.name,
                "scenario_type": definition.scenario_type.value,
                "status": definition.status.value,
                "current_stage": definition.current_stage.value,
                "created_at": definition.created_at.isoformat() if definition.created_at else None,
                "entry_path": definition.entry_path.value,
            })

    return linked


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _build_status_response(result: PipelineResult) -> PipelineStatusResponse:
    """Build status response from pipeline result."""
    # Include suggested dependent scenarios when the scenario is complete
    suggested = []
    if result.is_complete:
        suggested = format_suggestions_for_ui(
            result.scenario_definition.scenario_type,
            result.scenario_id,
        )

    return PipelineStatusResponse(
        scenario_id=result.scenario_id,
        status=result.scenario_definition.status,
        current_stage=result.current_stage,
        completed_stages=result.completed_stages,
        is_complete=result.is_complete,
        pending_prompts=[p.model_dump() for p in result.prompt_requests],
        suggested_scenarios=suggested,
        delta_summary=_delta_to_dict(result.delta) if result.delta else None,
        base_forecast_summary=_forecast_to_dict(result.base_forecast_summary) if result.base_forecast_summary else None,
        scenario_forecast_summary=_forecast_to_dict(result.scenario_forecast_summary) if result.scenario_forecast_summary else None,
        rule_results=[r.model_dump() for r in result.rule_results] if result.rule_results else [],
        errors=result.errors,
        warnings=result.warnings,
    )


def _delta_to_dict(delta: ScenarioDelta) -> Dict[str, Any]:
    """Convert ScenarioDelta to dictionary."""
    return {
        "scenario_id": delta.scenario_id,
        "created_events": len(delta.created_events),
        "updated_events": len(delta.updated_events),
        "deleted_events": len(delta.deleted_event_ids),
        "total_events_affected": delta.total_events_affected,
        "net_cash_impact": str(delta.net_cash_impact),
    }


def _forecast_to_dict(forecast) -> Dict[str, Any]:
    """Convert ForecastSummary to dictionary."""
    if not forecast:
        return None

    return {
        "starting_cash": str(forecast.starting_cash),
        "lowest_cash_week": forecast.lowest_cash_week,
        "lowest_cash_amount": str(forecast.lowest_cash_amount),
        "total_cash_in": str(forecast.total_cash_in),
        "total_cash_out": str(forecast.total_cash_out),
        "runway_weeks": forecast.runway_weeks,
    }
