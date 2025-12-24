"""Agent2: Responder - Answers user questions using OpenAI with function calling.

This agent receives the compiled prompt from Agent1 and:
1. Calls OpenAI API with function calling enabled
2. If a tool is called, executes it and returns the result
3. Returns a structured response in the required format
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from openai import AsyncOpenAI

from app.config import settings
from app.tami.schemas import TAMIResponse, TAMIMode, UIHints, SuggestedAction


# Initialize OpenAI client
def get_openai_client() -> AsyncOpenAI:
    """Get the OpenAI client."""
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def call_openai(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Call OpenAI API with function calling enabled.

    Returns:
        Tuple of (response_content, tool_call) where tool_call is None if no tool was called
    """
    client = get_openai_client()

    # Build request kwargs
    kwargs = {
        "model": settings.OPENAI_MODEL,
        "messages": messages,
        "max_tokens": settings.OPENAI_MAX_TOKENS,
    }

    # Add tools if provided
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    # Add response format if provided
    if response_format:
        kwargs["response_format"] = response_format

    try:
        response = await client.chat.completions.create(**kwargs)

        message = response.choices[0].message

        # Check if a tool was called
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            return None, {
                "id": tool_call.id,
                "name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments)
            }

        # Return content
        return message.content, None

    except Exception as e:
        # Return error response
        error_response = {
            "message_markdown": f"I encountered an error processing your request: {str(e)}",
            "mode": "clarify",
            "ui_hints": {
                "show_scenario_banner": False,
                "suggested_actions": []
            }
        }
        return json.dumps(error_response), None


async def generate_response(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    tool_result: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generate a response after a tool call.

    If tool_result is provided, it's added to the messages and a new
    response is generated without tool calling enabled.
    """
    client = get_openai_client()

    # If we have a tool result, add it to messages
    if tool_result:
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": tool_result["tool_call_id"],
                "type": "function",
                "function": {
                    "name": tool_result["tool_name"],
                    "arguments": json.dumps(tool_result["tool_args"])
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tool_result["tool_call_id"],
            "content": json.dumps(tool_result["result"])
        })

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content

    except Exception as e:
        error_response = {
            "message_markdown": f"I encountered an error: {str(e)}",
            "mode": "clarify",
            "ui_hints": {
                "show_scenario_banner": False,
                "suggested_actions": []
            }
        }
        return json.dumps(error_response)


def parse_response(response_content: str) -> TAMIResponse:
    """
    Parse the OpenAI response into a TAMIResponse object.

    Handles cases where the response might not be valid JSON or
    might be missing required fields.
    """
    try:
        data = json.loads(response_content)
    except json.JSONDecodeError:
        # If not valid JSON, wrap the content as a message
        return TAMIResponse(
            message_markdown=response_content,
            mode=TAMIMode.EXPLAIN_FORECAST,
            ui_hints=UIHints()
        )

    # Extract and validate mode
    mode_str = data.get("mode", "explain_forecast")
    try:
        mode = TAMIMode(mode_str)
    except ValueError:
        mode = TAMIMode.EXPLAIN_FORECAST

    # Extract UI hints
    ui_hints_data = data.get("ui_hints", {})
    suggested_actions = []

    for action_data in ui_hints_data.get("suggested_actions", []):
        try:
            suggested_actions.append(SuggestedAction(
                label=action_data.get("label", ""),
                action=action_data.get("action", "none"),
                tool_name=action_data.get("tool_name"),
                tool_args=action_data.get("tool_args", {}),
            ))
        except Exception:
            continue

    ui_hints = UIHints(
        show_scenario_banner=ui_hints_data.get("show_scenario_banner", False),
        suggested_actions=suggested_actions,
    )

    return TAMIResponse(
        message_markdown=data.get("message_markdown", ""),
        mode=mode,
        ui_hints=ui_hints,
    )


def create_fallback_response(
    message: str,
    mode: TAMIMode = TAMIMode.CLARIFY
) -> TAMIResponse:
    """Create a fallback response for error cases."""
    return TAMIResponse(
        message_markdown=message,
        mode=mode,
        ui_hints=UIHints(
            show_scenario_banner=False,
            suggested_actions=[]
        )
    )
