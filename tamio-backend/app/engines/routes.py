"""
API Routes for the Detection-Preparation Pipeline.

Provides endpoints to:
- Run the pipeline on-demand
- Check pipeline status
- Get action queue
- Approve/skip actions
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.data.users.models import User

from .pipeline import (
    run_detection_preparation_cycle,
    run_full_pipeline,
    get_pipeline_health,
    PipelineConfig,
    PipelineMode,
    PipelineResult,
)
from app.preparation import PreparationEngine

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class PipelineRunRequest(BaseModel):
    """Request to run the pipeline."""
    mode: str = Field(
        default="full",
        description="Pipeline mode: full, critical, or targeted"
    )
    detection_types: Optional[List[str]] = Field(
        default=None,
        description="For targeted mode: list of detection types to run"
    )
    skip_preparation: bool = Field(
        default=False,
        description="If true, only run detection (no action preparation)"
    )
    max_alerts: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum alerts to process"
    )


class PipelineRunResponse(BaseModel):
    """Response from pipeline run."""
    success: bool
    result: dict
    message: str


class ActionQueueResponse(BaseModel):
    """Response with action queue."""
    pending_count: int
    in_progress_count: int
    actions: List[dict]


class ActionApprovalRequest(BaseModel):
    """Request to approve an action."""
    option_id: Optional[str] = Field(
        default=None,
        description="Specific option to approve (uses recommended if not provided)"
    )


# =============================================================================
# Pipeline Endpoints
# =============================================================================

@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    request: PipelineRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run the detection-preparation pipeline.

    Executes the full detection → preparation cycle and returns results.
    This is the main endpoint for on-demand pipeline runs.
    """
    try:
        # Parse mode
        mode_map = {
            "full": PipelineMode.FULL,
            "critical": PipelineMode.CRITICAL,
            "targeted": PipelineMode.TARGETED,
        }
        mode = mode_map.get(request.mode.lower(), PipelineMode.FULL)

        # Build config
        config = PipelineConfig(
            mode=mode,
            detection_types=request.detection_types,
            skip_preparation=request.skip_preparation,
            max_alerts_to_prepare=request.max_alerts,
        )

        # Run pipeline
        result = await run_detection_preparation_cycle(
            db=db,
            user_id=current_user.id,
            config=config,
        )

        return PipelineRunResponse(
            success=len(result.errors) == 0,
            result=result.to_dict(),
            message=f"Detected {result.alerts_detected} alerts, prepared {result.actions_prepared} actions",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")


@router.post("/run-critical")
async def run_critical_pipeline(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run only critical detections.

    Fast endpoint for checking urgent issues like payroll safety
    and buffer breaches.
    """
    config = PipelineConfig(
        mode=PipelineMode.CRITICAL,
        include_low_severity=False,
    )

    result = await run_detection_preparation_cycle(
        db=db,
        user_id=current_user.id,
        config=config,
    )

    return {
        "success": len(result.errors) == 0,
        "alerts": result.alerts_detected,
        "emergency_count": result.alerts_by_severity.get("emergency", 0),
        "this_week_count": result.alerts_by_severity.get("this_week", 0),
        "actions_prepared": result.actions_prepared,
        "duration_ms": result.total_duration_ms,
    }


@router.get("/health")
async def pipeline_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get pipeline health status.

    Returns information about pipeline status, recent runs,
    and overall health metrics.
    """
    health = await get_pipeline_health(db, current_user.id)
    return health


# =============================================================================
# Action Queue Endpoints
# =============================================================================

@router.get("/actions", response_model=ActionQueueResponse)
async def get_action_queue(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    action_type: Optional[str] = Query(default=None, description="Filter by action type"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the current action queue.

    Returns prepared actions awaiting user approval.
    """
    engine = PreparationEngine(db, current_user.id)
    queue = await engine.get_action_queue(
        status_filter=status,
        action_type_filter=action_type,
        limit=limit,
    )

    # Convert to response format
    actions = []
    pending_count = 0
    in_progress_count = 0

    for action in queue:
        action_dict = {
            "id": action.id,
            "type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
            "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
            "severity": action.severity,
            "context": action.context,
            "recommended_option_id": action.recommended_option_id,
            "options": [],
            "created_at": action.created_at.isoformat() if action.created_at else None,
        }

        # Add options if loaded
        if hasattr(action, 'options') and action.options:
            for opt in action.options:
                action_dict["options"].append({
                    "id": opt.id,
                    "label": opt.label,
                    "description": opt.description,
                    "risk_score": float(opt.risk_score) if opt.risk_score else None,
                    "is_recommended": opt.id == action.recommended_option_id,
                })

        actions.append(action_dict)

        if action.status.value == "pending":
            pending_count += 1
        elif action.status.value == "in_progress":
            in_progress_count += 1

    return ActionQueueResponse(
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        actions=actions,
    )


@router.post("/actions/{action_id}/approve")
async def approve_action(
    action_id: str,
    request: ActionApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve a prepared action.

    Marks the action as approved and ready for execution.
    If option_id is provided, uses that option; otherwise uses recommended.
    """
    engine = PreparationEngine(db, current_user.id)

    try:
        action = await engine.approve_action(action_id, request.option_id)
        return {
            "success": True,
            "action_id": action_id,
            "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
            "selected_option_id": action.selected_option_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/actions/{action_id}/skip")
async def skip_action(
    action_id: str,
    reason: Optional[str] = Query(default=None, description="Reason for skipping"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Skip a prepared action.

    Marks the action as skipped. Provide optional reason for audit.
    """
    engine = PreparationEngine(db, current_user.id)

    try:
        action = await engine.skip_action(action_id, reason)
        return {
            "success": True,
            "action_id": action_id,
            "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/actions/{action_id}")
async def get_action_details(
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information about a specific action.

    Returns full action details including all options,
    linked actions, and drafts.
    """
    engine = PreparationEngine(db, current_user.id)
    queue = await engine.get_action_queue(limit=1000)

    # Find the specific action
    action = next((a for a in queue if a.id == action_id), None)
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    # Build detailed response
    response = {
        "id": action.id,
        "type": action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type),
        "status": action.status.value if hasattr(action.status, 'value') else str(action.status),
        "severity": action.severity,
        "context": action.context,
        "source_alert_id": action.source_alert_id,
        "recommended_option_id": action.recommended_option_id,
        "selected_option_id": action.selected_option_id,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "updated_at": action.updated_at.isoformat() if action.updated_at else None,
        "options": [],
    }

    # Add options with full details
    if hasattr(action, 'options') and action.options:
        for opt in action.options:
            response["options"].append({
                "id": opt.id,
                "label": opt.label,
                "description": opt.description,
                "risk_score": float(opt.risk_score) if opt.risk_score else None,
                "parameters": opt.parameters,
                "draft_content": opt.draft_content,
                "is_recommended": opt.id == action.recommended_option_id,
            })

    return response
