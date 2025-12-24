"""TAMI Orchestrator - Coordinates Agent1 and Agent2.

The orchestrator:
1. Builds context payload from database
2. Runs Agent1 to compile the final prompt
3. Runs Agent2 with tool calling enabled
4. If a tool is called, executes it, rebuilds context, and re-runs Agent2 once
5. Returns the final user response
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.tami.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    TAMIResponse,
    TAMIMode,
)
from app.tami.context import build_context, context_to_json
from app.tami.agent1_prompt_builder import build_prompt
from app.tami.agent2_responder import (
    call_openai,
    generate_response,
    parse_response,
    create_fallback_response,
)
from app.tami.tools import dispatch_tool


MAX_TOOL_LOOPS = 1  # Maximum number of tool call loops


async def chat(
    db: AsyncSession,
    request: ChatRequest
) -> ChatResponse:
    """
    Main chat endpoint handler.

    Orchestrates the full TAMI interaction flow:
    1. Build context
    2. Build prompt (Agent1)
    3. Call OpenAI (Agent2)
    4. Handle tool calls if any
    5. Return final response
    """
    tool_calls_made = []

    # Step 1: Build context payload
    try:
        context = await build_context(
            db,
            request.user_id,
            request.active_scenario_id
        )
    except Exception as e:
        return ChatResponse(
            response=create_fallback_response(
                f"I couldn't load your financial data: {str(e)}. Please make sure you've completed onboarding.",
                TAMIMode.CLARIFY
            ),
            context_summary=None,
            tool_calls_made=[]
        )

    # Step 2: Build prompt (Agent1)
    prompt_data = build_prompt(
        context=context,
        user_message=request.message,
        conversation_history=request.conversation_history,
        active_scenario_id=request.active_scenario_id
    )

    messages = prompt_data["messages"]
    tools = prompt_data["tools"]

    # Step 3: Call OpenAI (Agent2)
    response_content, tool_call = await call_openai(
        messages=messages,
        tools=tools,
        response_format=prompt_data.get("response_format")
    )

    # Step 4: Handle tool call if present (max 1 loop)
    loop_count = 0
    while tool_call and loop_count < MAX_TOOL_LOOPS:
        loop_count += 1

        # Execute the tool
        tool_result = await dispatch_tool(
            db=db,
            user_id=request.user_id,
            tool_name=tool_call["name"],
            tool_args=tool_call["arguments"]
        )

        tool_calls_made.append({
            "tool_name": tool_call["name"],
            "tool_args": tool_call["arguments"],
            "result": tool_result
        })

        # Rebuild context after tool execution (state may have changed)
        try:
            context = await build_context(
                db,
                request.user_id,
                request.active_scenario_id
            )
        except Exception:
            pass  # Use previous context if rebuild fails

        # Generate response with tool result
        response_content = await generate_response(
            messages=messages,
            tools=tools,
            tool_result={
                "tool_call_id": tool_call["id"],
                "tool_name": tool_call["name"],
                "tool_args": tool_call["arguments"],
                "result": tool_result
            }
        )

        # Check if another tool call is needed
        # (We don't loop again since MAX_TOOL_LOOPS = 1)
        tool_call = None

    # Step 5: Parse and return response
    if response_content:
        tami_response = parse_response(response_content)
    else:
        tami_response = create_fallback_response(
            "I wasn't able to generate a response. Please try again.",
            TAMIMode.CLARIFY
        )

    return ChatResponse(
        response=tami_response,
        context_summary={
            "user_id": context.user_id,
            "starting_cash": context.starting_cash,
            "runway_weeks": context.runway_weeks,
            "active_scenarios_count": len(context.active_scenarios),
            "rules_evaluated": len(context.rule_evaluations),
        },
        tool_calls_made=tool_calls_made
    )


async def get_scenario_suggestions(
    db: AsyncSession,
    user_id: str
) -> Dict[str, Any]:
    """Get scenario suggestions for a user."""
    from app.tami.tools import _get_suggestions
    return await _get_suggestions(db, user_id, {})


async def create_scenario_layer(
    db: AsyncSession,
    user_id: str,
    scenario_type: str,
    scope: Dict[str, Any],
    params: Dict[str, Any],
    linked_changes: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """Create a new scenario layer."""
    from app.tami.tools import _create_or_update_layer
    return await _create_or_update_layer(db, user_id, {
        "scenario_type": scenario_type,
        "scope": scope,
        "params": params,
        "linked_changes": linked_changes,
        "name": name
    })


async def iterate_scenario_layer(
    db: AsyncSession,
    user_id: str,
    scenario_id: str,
    patch: Dict[str, Any]
) -> Dict[str, Any]:
    """Update an existing scenario layer."""
    from app.tami.tools import _iterate_layer
    return await _iterate_layer(db, user_id, {
        "scenario_id": scenario_id,
        "patch": patch
    })


async def discard_scenario_layer(
    db: AsyncSession,
    user_id: str,
    scenario_id: str
) -> Dict[str, Any]:
    """Discard a scenario layer."""
    from app.tami.tools import _discard_layer
    return await _discard_layer(db, user_id, {
        "scenario_id": scenario_id
    })


async def build_goal_scenarios(
    db: AsyncSession,
    user_id: str,
    goal: str,
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build scenarios to achieve a goal."""
    from app.tami.tools import _build_goal_scenarios
    return await _build_goal_scenarios(db, user_id, {
        "goal": goal,
        "constraints": constraints or {}
    })
