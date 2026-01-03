"""Agent1: Prompt Builder - Compiles context and guardrails into prompts.

This agent is responsible for building the complete prompt that will be
sent to Agent2. It includes:
- System role and boundaries
- Operating principles
- Injected deterministic context
- Relevant knowledge from the curated knowledge base
- Tool schemas
- Response format requirements
"""
from typing import List, Dict, Any, Optional
import json

from app.tami.schemas import ContextPayload, ChatMessage
from app.tami.context import format_context_for_prompt
from app.tami.tools import get_tool_schemas
from app.tami.intent import Intent, classify_intent, get_relevant_knowledge_keys
from app.tami.knowledge import (
    get_glossary_term,
    get_glossary_by_category,
    get_scenario_explanation,
    get_risk_status,
    get_best_practices,
    get_feature_knowledge,
    get_common_situation,
    get_how_to_guide,
    search_glossary,
    RISK_INTERPRETATION,
)


SYSTEM_ROLE = """You are TAMI (Tamio AI), a deterministic financial assistant for Tamio - a cash flow forecasting platform for founders.

Your role is to help users understand their financial position and reason through scenarios. You are NOT a general financial advisor - you operate strictly within the Tamio domain.

## IDENTITY
- You are TAMI, the AI assistant embedded in Tamio
- You help founders understand their cash flow forecasts and make safe decisions under uncertainty
- You are calm, precise, and data-driven in your responses

## CORE BOUNDARIES (NON-NEGOTIABLE)
1. **No Assumptions**: Only use data from the provided context. Never assume relationships, amounts, or timings.
2. **No Advice**: You explain and help users reason. You can suggest scenarios to explore, but the user must approve any changes.
3. **Ask When Uncertain**: If data is missing or ambiguous, ask a clarifying question.
4. **Cite Data**: Always cite specific numbers inline (e.g., "Your payroll in week 6 is $180k").
5. **Separate BASE vs SCENARIO**: Always clearly distinguish between base forecast and scenario overlays in your responses.

## WHAT YOU CAN DO
- Explain the current forecast and cash position
- Highlight risks (buffer breaches, low runway)
- Suggest scenarios the user might want to explore
- Help build and iterate on scenarios (with user approval)
- Compare scenario impacts to base forecast
- Answer questions about the data shown

## WHAT YOU CANNOT DO
- Make assumptions about data not provided
- Commit or confirm scenarios (user must do this)
- Give investment, tax, or legal advice
- Access external data sources
- Make predictions beyond the 13-week forecast horizon
"""

OPERATING_PRINCIPLES = """## OPERATING PRINCIPLES

### Data Integrity
- Every statement must be traceable to the context payload
- If asked about something not in context, say "I don't have that information in your current data"
- Use exact numbers from the context, don't round or approximate

### Scenario Handling
- BASE FORECAST = the forecast without any scenario overlays
- SCENARIO FORECAST = what happens if a scenario is applied
- When discussing scenarios, always show the delta (difference from base)
- Never automatically apply changes - always ask for user confirmation

### Communication Style
- Be concise but complete
- Use markdown formatting for clarity
- Structure responses with clear sections when appropriate
- Lead with the most important information
- Use bullet points for lists of items

### Risk Communication
- Use severity indicators: GREEN (safe), AMBER (warning), RED (breach)
- Always mention the action window when discussing risks
- Connect risks to specific weeks in the forecast
"""

RESPONSE_FORMAT_JSON = """## RESPONSE FORMAT

You must always respond with valid JSON in this exact structure:

```json
{
  "message_markdown": "Your response in markdown format...",
  "mode": "explain_forecast | suggest_scenarios | build_scenario | goal_planning | clarify",
  "ui_hints": {
    "show_scenario_banner": true/false,
    "suggested_actions": [
      {
        "label": "Button text",
        "action": "call_tool | none",
        "tool_name": "tool.name if action is call_tool",
        "tool_args": {}
      }
    ]
  }
}
```

### Mode Selection
- `explain_forecast`: Explaining current state, answering questions about forecast
- `suggest_scenarios`: Suggesting scenarios the user might want to explore
- `build_scenario`: Actively building or iterating on a scenario
- `goal_planning`: Helping plan towards a financial goal
- `clarify`: Asking for more information

### UI Hints
- `show_scenario_banner`: true if any scenario is being built or discussed
- `suggested_actions`: Buttons to show the user (max 3)
"""

RESPONSE_FORMAT_STREAMING = """## RESPONSE FORMAT

Respond directly in markdown format. Do NOT wrap your response in JSON.

Write your response naturally using markdown formatting:
- Use headers (##, ###) to organize sections
- Use bullet points for lists
- Use **bold** for emphasis
- Use `code` for numbers or technical terms
- Be concise but complete

Your response will be streamed directly to the user, so start with the most important information.
"""


def build_prompt(
    context: ContextPayload,
    user_message: str,
    conversation_history: List[ChatMessage],
    active_scenario_id: Optional[str] = None,
    user_behavior: Optional[Dict[str, Any]] = None,
    streaming: bool = False
) -> Dict[str, Any]:
    """
    Build the complete prompt for Agent2.

    Args:
        context: The deterministic context payload
        user_message: The user's current message
        conversation_history: Previous messages in this conversation
        active_scenario_id: Optional currently active scenario
        user_behavior: Optional user behavior signals (activities, conversation history)
        streaming: If True, use plain markdown format instead of JSON

    Returns:
        Dict containing 'messages' for OpenAI API, 'tools' schema, and 'intent' info
    """
    # Classify intent to determine what knowledge to inject
    intent_context = {
        "active_scenario_id": active_scenario_id,
        "recent_activities": user_behavior.get("activities", []) if user_behavior else [],
    }
    intent, confidence, keywords = classify_intent(user_message, intent_context)

    # Get relevant knowledge based on intent
    relevant_knowledge = _gather_relevant_knowledge(intent, keywords, user_message)

    # Build system message with knowledge
    system_content = _build_system_message(
        context=context,
        active_scenario_id=active_scenario_id,
        knowledge=relevant_knowledge,
        user_behavior=user_behavior,
        streaming=streaming
    )

    # Build messages list
    messages = [{"role": "system", "content": system_content}]

    # Add conversation history
    for msg in conversation_history:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    # Get tool schemas (not used for streaming simple queries)
    tools = get_tool_schemas() if not streaming else []

    result = {
        "messages": messages,
        "tools": tools,
        "intent": {
            "detected": intent.value,
            "confidence": confidence,
            "keywords": keywords,
        },
    }

    # Only add response_format for non-streaming (JSON mode)
    if not streaming:
        result["response_format"] = {"type": "json_object"}

    return result


def _build_system_message(
    context: ContextPayload,
    active_scenario_id: Optional[str] = None,
    knowledge: Optional[Dict[str, Any]] = None,
    user_behavior: Optional[Dict[str, Any]] = None,
    streaming: bool = False
) -> str:
    """Build the complete system message with context and relevant knowledge."""
    parts = []

    # Add role and boundaries
    parts.append(SYSTEM_ROLE)
    parts.append("")

    # Add operating principles
    parts.append(OPERATING_PRINCIPLES)
    parts.append("")

    # Add relevant knowledge (if any)
    if knowledge:
        knowledge_section = _format_knowledge_section(knowledge)
        if knowledge_section:
            parts.append("## RELEVANT KNOWLEDGE")
            parts.append("Use this curated knowledge to provide accurate, helpful responses:")
            parts.append("")
            parts.append(knowledge_section)
            parts.append("")

    # Add user behavior context (if any)
    if user_behavior:
        behavior_section = _format_behavior_section(user_behavior)
        if behavior_section:
            parts.append("## USER BEHAVIOR CONTEXT")
            parts.append("Consider what the user has been doing recently:")
            parts.append("")
            parts.append(behavior_section)
            parts.append("")

    # Add context
    parts.append("## CURRENT CONTEXT (DETERMINISTIC DATA)")
    parts.append("")
    parts.append(format_context_for_prompt(context))
    parts.append("")

    # Add JSON context for precise tool use (only for non-streaming)
    if not streaming:
        parts.append("## CONTEXT JSON (for tool calls)")
        parts.append("```json")
        parts.append(json.dumps(context.model_dump(), indent=2, default=str))
        parts.append("```")
        parts.append("")

    # Active scenario mode
    if active_scenario_id:
        parts.append(f"## ACTIVE SCENARIO MODE")
        parts.append(f"Currently editing scenario: {active_scenario_id}")
        parts.append("The user is in scenario editing mode. Focus responses on this scenario.")
        parts.append("")

    # Add response format (different for streaming vs non-streaming)
    parts.append(RESPONSE_FORMAT_STREAMING if streaming else RESPONSE_FORMAT_JSON)

    return "\n".join(parts)


def _gather_relevant_knowledge(
    intent: Intent,
    keywords: List[str],
    user_message: str
) -> Dict[str, Any]:
    """
    Gather relevant knowledge based on detected intent and keywords.

    Returns a dict with relevant knowledge items from each category.
    """
    knowledge: Dict[str, Any] = {
        "glossary_terms": [],
        "scenario_info": [],
        "risk_info": None,
        "best_practices": [],
        "features": [],
        "how_to_guides": [],
        "situations": [],
    }

    # Get knowledge keys based on intent
    keys = get_relevant_knowledge_keys(intent, keywords)

    # Gather glossary terms
    for term in keys.get("glossary_terms", []):
        term_info = get_glossary_term(term)
        if term_info:
            knowledge["glossary_terms"].append(term_info)

    # Also search glossary if we have keywords
    if keywords and intent == Intent.EXPLAIN_TERM:
        for keyword in keywords:
            matches = search_glossary(keyword)
            for match in matches[:2]:  # Limit to top 2 matches per keyword
                if match not in knowledge["glossary_terms"]:
                    knowledge["glossary_terms"].append(match)

    # Gather scenario explanations
    for scenario_type in keys.get("scenario_types", []):
        scenario_info = get_scenario_explanation(scenario_type)
        if scenario_info:
            knowledge["scenario_info"].append(scenario_info)

    # Gather risk interpretation if relevant
    if intent in (Intent.EXPLAIN_RISK, Intent.CHECK_STATUS, Intent.CHECK_RUNWAY):
        knowledge["risk_info"] = RISK_INTERPRETATION

    # Gather best practices
    for category in keys.get("best_practice_categories", []):
        practices = get_best_practices(category)
        if isinstance(practices, list):
            knowledge["best_practices"].extend(practices)
        elif practices:
            knowledge["best_practices"].append(practices)

    # Gather feature knowledge
    for feature in keys.get("features", []):
        feature_info = get_feature_knowledge(feature)
        if feature_info:
            knowledge["features"].append(feature_info)

    # Gather how-to guides
    for topic in keys.get("how_to_topics", []):
        guide = get_how_to_guide(topic)
        if guide:
            knowledge["how_to_guides"].append(guide)

    # Gather situation guides
    for situation in keys.get("situations", []):
        situation_info = get_common_situation(situation)
        if situation_info:
            knowledge["situations"].append(situation_info)

    return knowledge


def _format_knowledge_section(knowledge: Dict[str, Any]) -> str:
    """Format the gathered knowledge as a prompt section."""
    lines = []

    # Glossary terms
    if knowledge.get("glossary_terms"):
        lines.append("### Definitions")
        for term in knowledge["glossary_terms"]:
            lines.append(f"**{term.get('term', 'Term')}**: {term.get('definition', '')}")
            if term.get("example"):
                lines.append(f"  _Example: {term['example']}_")
        lines.append("")

    # Scenario info
    if knowledge.get("scenario_info"):
        lines.append("### Scenario Types")
        for scenario in knowledge["scenario_info"]:
            lines.append(f"**{scenario.get('name', 'Scenario')}**")
            lines.append(f"- What it does: {scenario.get('what_it_does', '')}")
            if scenario.get("when_to_suggest"):
                lines.append(f"- When to suggest: {', '.join(scenario['when_to_suggest'][:2])}")
            if scenario.get("common_mistakes"):
                lines.append(f"- Avoid: {scenario['common_mistakes'][0] if scenario['common_mistakes'] else ''}")
        lines.append("")

    # Risk info
    if knowledge.get("risk_info"):
        lines.append("### Risk Status Meanings")
        risk = knowledge["risk_info"]
        for status in ["GREEN", "AMBER", "RED"]:
            if status in risk:
                s = risk[status]
                lines.append(f"**{status}**: {s.get('meaning', '')} - Action: {s.get('recommended_action', '')}")
        lines.append("")

    # Best practices
    if knowledge.get("best_practices"):
        lines.append("### Best Practices")
        for practice in knowledge["best_practices"][:3]:  # Limit to 3
            if isinstance(practice, dict):
                lines.append(f"- **{practice.get('title', '')}**: {practice.get('guidance', '')}")
            else:
                lines.append(f"- {practice}")
        lines.append("")

    # Features
    if knowledge.get("features"):
        lines.append("### Feature Information")
        for feature in knowledge["features"]:
            lines.append(f"**{feature.get('name', 'Feature')}**: {feature.get('description', '')}")
            if feature.get("key_points"):
                for point in feature["key_points"][:2]:
                    lines.append(f"  - {point}")
        lines.append("")

    # How-to guides
    if knowledge.get("how_to_guides"):
        lines.append("### Step-by-Step Guides")
        for guide in knowledge["how_to_guides"]:
            lines.append(f"**{guide.get('title', 'Guide')}**")
            if guide.get("steps"):
                for i, step in enumerate(guide["steps"][:4], 1):  # Limit steps
                    lines.append(f"  {i}. {step}")
        lines.append("")

    # Situations
    if knowledge.get("situations"):
        lines.append("### Common Situations")
        for situation in knowledge["situations"]:
            lines.append(f"**{situation.get('scenario', 'Situation')}**")
            lines.append(f"Response approach: {situation.get('response_template', '')[:200]}...")
        lines.append("")

    return "\n".join(lines)


def _format_behavior_section(user_behavior: Dict[str, Any]) -> str:
    """Format user behavior signals as a prompt section."""
    lines = []

    activities = user_behavior.get("activities", [])
    conversation = user_behavior.get("conversation", [])

    if activities:
        # Group by type for a cleaner summary
        type_counts: Dict[str, int] = {}
        for act in activities:
            act_type = act.get("activity_type", "unknown").replace("_", " ").title()
            type_counts[act_type] = type_counts.get(act_type, 0) + 1

        lines.append("Recent activity:")
        for act_type, count in sorted(type_counts.items(), key=lambda x: -x[1])[:3]:
            lines.append(f"- {act_type}: {count}x")

    if conversation:
        lines.append(f"Conversation messages so far: {len(conversation)}")
        # Note the last topic if available
        user_msgs = [m for m in conversation if m.get("role") == "user"]
        if user_msgs and user_msgs[-1].get("detected_intent"):
            last_intent = user_msgs[-1]["detected_intent"].replace("_", " ").title()
            lines.append(f"Previous topic: {last_intent}")

    return "\n".join(lines)


def get_system_boundaries() -> str:
    """Get just the system boundaries for reference."""
    return SYSTEM_ROLE


def get_operating_principles() -> str:
    """Get just the operating principles for reference."""
    return OPERATING_PRINCIPLES
