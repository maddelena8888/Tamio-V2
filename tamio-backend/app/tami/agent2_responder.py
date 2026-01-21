"""Agent2: Responder - Answers user questions using Claude (Anthropic) with function calling.

This agent receives the compiled prompt from Agent1 and:
1. Calls Anthropic API with function calling enabled
2. If a tool is called, executes it and returns the result
3. Returns a structured response in the required format
"""
import json
from typing import Dict, Any, List, Optional, Tuple, AsyncIterator
from anthropic import AsyncAnthropic

from app.config import settings
from app.tami.schemas import TAMIResponse, TAMIMode, UIHints, SuggestedAction


# Initialize Anthropic client
def get_anthropic_client() -> AsyncAnthropic:
    """Get the Anthropic client."""
    return AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)


def _convert_tools_to_anthropic_format(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert OpenAI-style tool definitions to Anthropic format."""
    anthropic_tools = []
    for tool in tools:
        if tool.get("type") == "function":
            func = tool["function"]
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", {"type": "object", "properties": {}})
            })
    return anthropic_tools


def _extract_system_message(messages: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract system message from messages list (Anthropic requires it separately)."""
    system_content = ""
    other_messages = []

    for msg in messages:
        if msg.get("role") == "system":
            system_content = msg.get("content", "")
        else:
            other_messages.append(msg)

    return system_content, other_messages


async def call_openai_streaming(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    use_fast_model: bool = False,
) -> AsyncIterator[str]:
    """
    Call Anthropic API with streaming enabled.

    Yields chunks of the response as they arrive.
    Note: When streaming, we don't use JSON response format to allow
    natural text streaming. The final response is parsed separately.

    Args:
        messages: The conversation messages
        tools: Available tools for function calling
        use_fast_model: If True, use claude-haiku for faster responses
    """
    client = get_anthropic_client()

    # Select model based on complexity
    model = settings.ANTHROPIC_MODEL_FAST if use_fast_model else settings.ANTHROPIC_MODEL

    # Extract system message (Anthropic requires it separately)
    system_content, conversation_messages = _extract_system_message(messages)

    kwargs = {
        "model": model,
        "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
        "messages": conversation_messages,
    }

    if system_content:
        kwargs["system"] = system_content

    # Only add tools for complex queries (fast model doesn't need them)
    if tools and not use_fast_model:
        anthropic_tools = _convert_tools_to_anthropic_format(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

    try:
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    except Exception as e:
        yield f"Error: {str(e)}"


async def call_openai(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Call Anthropic API with function calling enabled.

    Returns:
        Tuple of (response_content, tool_call) where tool_call is None if no tool was called
    """
    client = get_anthropic_client()

    # Extract system message (Anthropic requires it separately)
    system_content, conversation_messages = _extract_system_message(messages)

    # Build request kwargs
    kwargs = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
        "messages": conversation_messages,
    }

    if system_content:
        kwargs["system"] = system_content

    # Add tools if provided
    if tools:
        anthropic_tools = _convert_tools_to_anthropic_format(tools)
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

    try:
        response = await client.messages.create(**kwargs)

        # Check if a tool was called
        for content_block in response.content:
            if content_block.type == "tool_use":
                return None, {
                    "id": content_block.id,
                    "name": content_block.name,
                    "arguments": content_block.input
                }

        # Extract text content
        text_content = ""
        for content_block in response.content:
            if content_block.type == "text":
                text_content += content_block.text

        return text_content, None

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
    client = get_anthropic_client()

    # Extract system message
    system_content, conversation_messages = _extract_system_message(messages)

    # If we have a tool result, add it to messages in Anthropic format
    if tool_result:
        # Add assistant message with tool use
        conversation_messages.append({
            "role": "assistant",
            "content": [{
                "type": "tool_use",
                "id": tool_result["tool_call_id"],
                "name": tool_result["tool_name"],
                "input": tool_result["tool_args"]
            }]
        })
        # Add tool result
        conversation_messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_result["tool_call_id"],
                "content": json.dumps(tool_result["result"])
            }]
        })

    kwargs = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
        "messages": conversation_messages,
    }

    if system_content:
        kwargs["system"] = system_content

    try:
        response = await client.messages.create(**kwargs)

        # Extract text content
        text_content = ""
        for content_block in response.content:
            if content_block.type == "text":
                text_content += content_block.text

        return text_content

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
    Parse the Anthropic response into a TAMIResponse object.

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
