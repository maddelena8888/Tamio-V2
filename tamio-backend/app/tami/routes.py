"""TAMI API Routes.

Endpoints:
- POST /tami/chat - Main chat entrypoint
- POST /tami/chat/stream - Streaming chat entrypoint
- POST /scenario/layer/create_or_update - Create or update scenario layer
- POST /scenario/layer/iterate - Iterate on existing scenario
- POST /scenario/layer/discard - Discard scenario
- GET /scenario/suggestions - Get scenario suggestions
- POST /plan/goal - Build goal scenarios
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
import json

from app.database import get_db
from app.tami import schemas, orchestrator
from app.middleware import limiter
from app.config import settings


router = APIRouter()


# ============================================================================
# CHAT ENDPOINT
# ============================================================================

@router.post("/chat", response_model=schemas.ChatResponse)
@limiter.limit(settings.RATE_LIMIT_TAMI)
async def chat_with_tami(
    request: Request,
    chat_request: schemas.ChatRequest,
    session_id: Optional[str] = Query(None, description="Optional conversation session ID for continuity"),
    db: AsyncSession = Depends(get_db)
):
    """
    Main TAMI chat endpoint.

    Send a message to TAMI and receive a response. TAMI will:
    - Analyze your current financial state
    - Answer questions about your forecast
    - Help you build and iterate on scenarios
    - Use relevant knowledge from its curated knowledge base
    - Never make assumptions or give advice

    The response includes:
    - message_markdown: The response text in markdown
    - mode: Current conversation mode
    - ui_hints: Hints for rendering the UI
    - context_summary: Includes session_id for conversation continuity
    """
    try:
        response = await orchestrator.chat(db, chat_request, session_id=session_id)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing chat request: {str(e)}"
        )


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_TAMI)
async def chat_with_tami_streaming(
    request: Request,
    chat_request: schemas.ChatRequest,
    session_id: Optional[str] = Query(None, description="Optional conversation session ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Streaming TAMI chat endpoint.

    Same as /chat but streams the response for lower perceived latency.
    Returns Server-Sent Events (SSE) with chunks of the response.

    Event types:
    - chunk: A piece of the message text
    - done: Final metadata (mode, ui_hints, context_summary)
    - error: Error occurred
    """
    async def generate_stream():
        try:
            async for event in orchestrator.chat_streaming(db, chat_request, session_id=session_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# SCENARIO LAYER ENDPOINTS
# ============================================================================

@router.post("/scenario/layer/create_or_update", response_model=schemas.ScenarioLayerResponse)
async def create_or_update_scenario_layer(
    request: schemas.ScenarioLayerCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scenario layer or update an existing one.

    This endpoint is used to model what-if situations like:
    - Losing a client
    - Hiring new employees
    - Changing expenses
    - Payment delays

    The response includes the scenario ID and forecast impact.
    """
    try:
        result = await orchestrator.create_scenario_layer(
            db=db,
            user_id=request.user_id,
            scenario_type=request.scenario_type,
            scope=request.scope,
            params=request.params,
            linked_changes=request.linked_changes,
            name=request.name
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to create scenario")
            )

        return schemas.ScenarioLayerResponse(
            scenario_id=result["scenario_id"],
            status=result["status"],
            message=result["message"],
            forecast_impact={
                "impact_week_13": result.get("impact_week_13"),
                "events_generated": result.get("events_generated")
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating scenario: {str(e)}"
        )


@router.post("/scenario/layer/iterate", response_model=schemas.ScenarioLayerResponse)
async def iterate_scenario_layer(
    request: schemas.ScenarioLayerIterate,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Iterate on an existing scenario layer.

    Update the parameters of a scenario to see how changes affect the forecast.
    """
    try:
        result = await orchestrator.iterate_scenario_layer(
            db=db,
            user_id=user_id,
            scenario_id=request.scenario_id,
            patch=request.patch
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to update scenario")
            )

        return schemas.ScenarioLayerResponse(
            scenario_id=result["scenario_id"],
            status="active",
            message=result["message"],
            forecast_impact={
                "impact_week_13": result.get("impact_week_13"),
                "updated_params": result.get("updated_params")
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating scenario: {str(e)}"
        )


@router.post("/scenario/layer/discard", response_model=schemas.ScenarioLayerResponse)
async def discard_scenario_layer(
    request: schemas.ScenarioLayerDiscard,
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Discard a scenario layer.

    Mark a scenario as discarded. This doesn't delete it but removes it
    from active consideration.
    """
    try:
        result = await orchestrator.discard_scenario_layer(
            db=db,
            user_id=user_id,
            scenario_id=request.scenario_id
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to discard scenario")
            )

        return schemas.ScenarioLayerResponse(
            scenario_id=result["scenario_id"],
            status="discarded",
            message=result["message"],
            forecast_impact=None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error discarding scenario: {str(e)}"
        )


# ============================================================================
# SUGGESTIONS ENDPOINT
# ============================================================================

@router.get("/scenario/suggestions")
async def get_scenario_suggestions(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get scenario suggestions based on current forecast state.

    Returns suggestions for scenarios the user might want to explore
    based on their current financial position and any rule breaches.
    """
    try:
        result = await orchestrator.get_scenario_suggestions(db, user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting suggestions: {str(e)}"
        )


# ============================================================================
# GOAL PLANNING ENDPOINT
# ============================================================================

@router.post("/plan/goal", response_model=schemas.GoalPlanResponse)
async def build_goal_plan(
    request: schemas.GoalPlanRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Build scenarios to achieve a financial goal.

    Given a goal description and optional constraints, returns a set
    of scenarios that could help achieve the goal.

    Example goals:
    - "Extend runway to 6 months"
    - "Reduce expenses by 20%"
    - "Prepare for losing Client X"
    """
    try:
        result = await orchestrator.build_goal_scenarios(
            db=db,
            user_id=request.user_id,
            goal=request.goal,
            constraints=request.constraints
        )

        return schemas.GoalPlanResponse(
            goal=result["goal"],
            scenarios=result.get("suggested_scenarios", []),
            analysis=f"Based on your current runway of {result.get('current_state', {}).get('runway_weeks', 'unknown')} weeks, "
                    f"here are scenarios to explore for achieving your goal."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error building goal plan: {str(e)}"
        )


# ============================================================================
# ACTIVITY TRACKING ENDPOINT
# ============================================================================

@router.post("/activity/track")
async def track_user_activity(
    user_id: str = Query(..., description="User ID"),
    activity_type: str = Query(..., description="Type of activity (e.g., view_dashboard, create_scenario)"),
    entity_type: Optional[str] = Query(None, description="Type of entity (e.g., client, scenario)"),
    entity_id: Optional[str] = Query(None, description="ID of the entity"),
    session_id: Optional[str] = Query(None, description="Optional conversation session ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Track a user activity for behavioral context.

    This helps TAMI provide more relevant responses by understanding
    what the user has been doing in the application.

    Activity types include:
    - view_dashboard, view_forecast, view_scenarios, view_clients, view_expenses
    - create_scenario, edit_scenario, confirm_scenario, discard_scenario
    - add_client, edit_client, delete_client
    - add_expense, edit_expense, delete_expense
    - update_cash_balance, add_cash_account
    - xero_connect, xero_sync
    """
    try:
        activity = await orchestrator.track_activity(
            db=db,
            user_id=user_id,
            activity_type=activity_type,
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id
        )
        return {"success": True, "activity_id": activity.id}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error tracking activity: {str(e)}"
        )


# ============================================================================
# CONTEXT ENDPOINT (for debugging)
# ============================================================================

@router.get("/context")
async def get_tami_context(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current context payload that TAMI uses.

    This is primarily for debugging to see what data TAMI has access to.
    """
    try:
        from app.tami.context import build_context, context_to_json
        context = await build_context(db, user_id)
        return context_to_json(context)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error building context: {str(e)}"
        )


# ============================================================================
# BRIEFING ENDPOINT
# ============================================================================

@router.get("/briefing")
async def get_briefing(
    user_id: str = Query(..., description="User ID to generate briefing for"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a prioritized briefing of the top 3 treasury items.

    Returns the same data as the generate_briefing tool but as a direct
    REST endpoint for dashboard widgets and programmatic access.
    """
    try:
        from app.tami.tools import _generate_briefing
        result = await _generate_briefing(db, user_id, {})
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Briefing generation failed")
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating briefing: {str(e)}"
        )
