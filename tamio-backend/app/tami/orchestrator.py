"""TAMI Orchestrator - Coordinates Agent1 and Agent2.

The orchestrator:
1. Builds context payload from database
2. Loads user behavior signals (activities, conversation history)
3. Runs Agent1 to compile the final prompt with relevant knowledge
4. Runs Agent2 with tool calling enabled
5. If a tool is called, executes it, rebuilds context, and re-runs Agent2 once
6. Saves conversation to database for persistence
7. Returns the final user response
"""
from typing import Dict, Any, List, Optional, AsyncIterator
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update

from app.tami.schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    TAMIResponse,
    TAMIMode,
)
from app.tami.context import (
    build_context,
    context_to_json,
    load_recent_activities,
    load_recent_conversation,
)
from app.tami.agent1_prompt_builder import build_prompt
from app.tami.agent2_responder import (
    call_openai,
    call_openai_streaming,
    generate_response,
    generate_response_streaming,
    parse_response,
    create_fallback_response,
)
from app.tami.tools import dispatch_tool, get_tool_schemas
from app.tami.models import ConversationSession, ConversationMessage, UserActivity
from app.tami.intent import Intent, should_use_fast_model
from app.tami.cache import context_cache


MAX_TOOL_LOOPS = 1  # Maximum number of tool call loops


def _intent_to_mode(intent: Intent) -> str:
    """Map intent to TAMI mode for streaming responses."""
    mapping = {
        Intent.CREATE_SCENARIO: "build_scenario",
        Intent.MODIFY_SCENARIO: "build_scenario",
        Intent.COMPARE_SCENARIOS: "suggest_scenarios",
        Intent.GOAL_PLANNING: "goal_planning",
        Intent.EXPLAIN_FORECAST: "explain_forecast",
        Intent.EXPLAIN_RISK: "explain_forecast",
        Intent.EXPLAIN_TERM: "explain_forecast",
        Intent.CHECK_STATUS: "explain_forecast",
        Intent.CHECK_RUNWAY: "explain_forecast",
        Intent.CHECK_CASH: "explain_forecast",
        Intent.CHECK_PAYROLL: "explain_forecast",
        Intent.CHECK_CONCENTRATION: "explain_forecast",
        Intent.GENERATE_BRIEFING: "explain_forecast",
        Intent.GREETING: "explain_forecast",
        Intent.HELP: "clarify",
        Intent.GENERAL_QUESTION: "explain_forecast",
    }
    return mapping.get(intent, "explain_forecast")


async def chat(
    db: AsyncSession,
    request: ChatRequest,
    session_id: Optional[str] = None
) -> ChatResponse:
    """
    Main chat endpoint handler.

    Orchestrates the full TAMI interaction flow:
    1. Build context
    2. Load user behavior signals
    3. Build prompt with relevant knowledge (Agent1)
    4. Call OpenAI (Agent2)
    5. Handle tool calls if any
    6. Save conversation messages
    7. Return final response
    """
    tool_calls_made = []
    detected_intent = None

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

    # Step 2: Load user behavior signals
    user_behavior = await _load_user_behavior(db, request.user_id, session_id)

    # Step 3: Get or create conversation session
    session = await _get_or_create_session(db, request.user_id, session_id)
    session_id_val = session.id  # Capture eagerly before DB ops expire the ORM object

    # Step 4: Build prompt with relevant knowledge (Agent1)
    prompt_data = build_prompt(
        context=context,
        user_message=request.message,
        conversation_history=request.conversation_history,
        active_scenario_id=request.active_scenario_id,
        user_behavior=user_behavior
    )

    messages = prompt_data["messages"]
    tools = prompt_data["tools"]
    detected_intent = prompt_data.get("intent", {}).get("detected")

    # Step 5: Save user message to conversation
    await _save_message(
        db=db,
        session_id=session_id_val,
        role="user",
        content=request.message,
        detected_intent=detected_intent
    )

    # Step 6: Call OpenAI (Agent2)
    response_content, tool_call = await call_openai(
        messages=messages,
        tools=tools,
        response_format=prompt_data.get("response_format")
    )

    # Step 7: Handle tool call if present (max 1 loop)
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

    # Step 8: Parse and return response
    if response_content:
        tami_response = parse_response(response_content)
    else:
        tami_response = create_fallback_response(
            "I wasn't able to generate a response. Please try again.",
            TAMIMode.CLARIFY
        )

    # Step 9: Save assistant message to conversation
    await _save_message(
        db=db,
        session_id=session_id_val,
        role="assistant",
        content=tami_response.message_markdown,
        mode=tami_response.mode.value,
        ui_hints=tami_response.ui_hints.model_dump() if tami_response.ui_hints else None,
        tool_calls=tool_calls_made if tool_calls_made else None
    )

    # Update session last_message_at (use SQL update to avoid expired ORM object)
    await db.execute(
        update(ConversationSession)
        .where(ConversationSession.id == session_id_val)
        .values(last_message_at=datetime.utcnow())
    )
    await db.flush()

    return ChatResponse(
        response=tami_response,
        context_summary={
            "user_id": context.user_id,
            "starting_cash": context.starting_cash,
            "runway_weeks": context.runway_weeks,
            "active_scenarios_count": len(context.active_scenarios),
            "rules_evaluated": len(context.rule_evaluations),
            "detected_intent": detected_intent,
            "session_id": session_id_val,
        },
        tool_calls_made=tool_calls_made
    )


async def chat_streaming(
    db: AsyncSession,
    request: ChatRequest,
    session_id: Optional[str] = None
) -> AsyncIterator[Dict[str, Any]]:
    """
    Streaming version of chat.

    Yields events as they become available:
    - {"type": "chunk", "content": "..."} for text chunks
    - {"type": "done", "mode": "...", "ui_hints": {...}, "context_summary": {...}}
    """
    detected_intent = None

    # Step 1: Build context (use cache if available for faster response)
    try:
        # Try to get cached context first
        context = context_cache.get(request.user_id, request.active_scenario_id)
        if context is None:
            # No cache hit, build fresh context
            context = await build_context(
                db,
                request.user_id,
                request.active_scenario_id
            )
            # Cache for subsequent messages in this conversation
            context_cache.set(request.user_id, context, request.active_scenario_id)
    except Exception as e:
        yield {
            "type": "error",
            "error": f"Couldn't load financial data: {str(e)}"
        }
        return

    # Step 2: Load user behavior
    user_behavior = await _load_user_behavior(db, request.user_id, session_id)

    # Step 3: Get or create session
    session = await _get_or_create_session(db, request.user_id, session_id)

    # Step 4: Build prompt (Agent1) - use streaming format for plain markdown output
    prompt_data = build_prompt(
        context=context,
        user_message=request.message,
        conversation_history=request.conversation_history,
        active_scenario_id=request.active_scenario_id,
        user_behavior=user_behavior,
        streaming=True  # Use plain markdown format, not JSON
    )

    messages = prompt_data["messages"]
    tools = prompt_data["tools"]
    detected_intent = prompt_data.get("intent", {}).get("detected")
    intent_confidence = prompt_data.get("intent", {}).get("confidence", 0.5)

    # Determine if we should use the fast model
    try:
        intent_enum = Intent(detected_intent) if detected_intent else Intent.GENERAL_QUESTION
    except ValueError:
        intent_enum = Intent.GENERAL_QUESTION
    use_fast = should_use_fast_model(intent_enum, intent_confidence)

    # Step 5: Save user message
    session_id_val = session.id  # Capture eagerly before DB ops expire ORM object
    await _save_message(
        db=db,
        session_id=session_id_val,
        role="user",
        content=request.message,
        detected_intent=detected_intent
    )

    # Step 6: Generate response — tool-calling path for complex intents,
    # direct streaming for simple intents.
    full_content = ""
    tool_calls_made = []

    if not use_fast:
        # Complex intent: may need tool calling.
        # Use non-streaming initial call WITH tool schemas so the LLM
        # can decide whether to invoke a tool.
        tool_schemas = get_tool_schemas()
        response_content, tool_call = await call_openai(
            messages=messages,
            tools=tool_schemas,
        )

        if tool_call:
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

            # Stream the final explanation of the tool result
            async for chunk in generate_response_streaming(
                messages=messages,
                tools=tool_schemas,
                tool_result={
                    "tool_call_id": tool_call["id"],
                    "tool_name": tool_call["name"],
                    "tool_args": tool_call["arguments"],
                    "result": tool_result,
                }
            ):
                full_content += chunk
                yield {"type": "chunk", "content": chunk}
        else:
            # LLM chose not to call a tool — yield the text response
            full_content = response_content or ""
            yield {"type": "chunk", "content": full_content}
    else:
        # Simple intent: stream directly (existing behavior)
        async for chunk in call_openai_streaming(messages, tools, use_fast_model=use_fast):
            full_content += chunk
            yield {"type": "chunk", "content": chunk}

    # Step 7: Derive mode from intent (since streaming returns plain text, not JSON)
    mode = _intent_to_mode(intent_enum)

    # Step 8: Save assistant message
    await _save_message(
        db=db,
        session_id=session_id_val,
        role="assistant",
        content=full_content,
        mode=mode,
        ui_hints=None,  # No UI hints in streaming mode
        tool_calls=tool_calls_made if tool_calls_made else None,
    )

    # Update session last_message_at (use SQL update to avoid expired ORM object)
    await db.execute(
        update(ConversationSession)
        .where(ConversationSession.id == session_id_val)
        .values(last_message_at=datetime.utcnow())
    )
    await db.flush()

    # Step 9: Yield final metadata
    yield {
        "type": "done",
        "mode": mode,
        "ui_hints": {},  # No UI hints in streaming mode
        "context_summary": {
            "user_id": context.user_id,
            "runway_weeks": context.runway_weeks,
            "detected_intent": detected_intent,
            "session_id": session_id_val,
        }
    }


async def _load_user_behavior(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Load user behavior signals for context enrichment."""
    activities = await load_recent_activities(db, user_id, hours=24, limit=20)
    conversation = await load_recent_conversation(db, user_id, session_id, limit=10)

    return {
        "activities": activities,
        "conversation": conversation,
    }


async def _get_or_create_session(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str] = None
) -> ConversationSession:
    """Get existing session or create a new one."""
    if session_id:
        result = await db.execute(
            select(ConversationSession).where(ConversationSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session:
            return session

    # Find or create active session
    result = await db.execute(
        select(ConversationSession)
        .where(
            ConversationSession.user_id == user_id,
            ConversationSession.is_active == True
        )
        .order_by(desc(ConversationSession.last_message_at))
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if session:
        return session

    # Create new session
    session = ConversationSession(
        user_id=user_id,
        is_active=True
    )
    db.add(session)
    await db.flush()
    return session


async def _save_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    detected_intent: Optional[str] = None,
    mode: Optional[str] = None,
    ui_hints: Optional[Dict[str, Any]] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None
) -> ConversationMessage:
    """Save a message to the conversation history."""
    message = ConversationMessage(
        session_id=session_id,
        role=role,
        content=content,
        detected_intent=detected_intent,
        mode=mode,
        ui_hints=ui_hints,
        tool_calls=tool_calls
    )
    db.add(message)
    await db.flush()
    return message


async def track_activity(
    db: AsyncSession,
    user_id: str,
    activity_type: str,
    context: Optional[Dict[str, Any]] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> UserActivity:
    """
    Track a user activity for behavioral context.

    This should be called from various parts of the application
    to track what the user is doing.
    """
    activity = UserActivity(
        user_id=user_id,
        activity_type=activity_type,
        context=context,
        entity_type=entity_type,
        entity_id=entity_id,
        conversation_session_id=session_id
    )
    db.add(activity)
    await db.flush()
    return activity


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
