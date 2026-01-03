"""TAMI - Tamio AI Assistant Module.

TAMI is a deterministic AI layer that helps users reason about their
cash flow forecasts and scenarios. It consists of:

Architecture:
- Agent1 (Prompt Builder): Compiles context, knowledge, and guardrails into prompts
- Agent2 (Responder): Answers questions using OpenAI with function calling

Key Components:
- Knowledge Base: Curated knowledge (glossary, scenarios, risk interpretation, best practices)
- Intent Classification: Routes queries to relevant knowledge
- Conversation Persistence: Saves chat history for context continuity
- User Activity Tracking: Tracks user behavior for more relevant responses

Usage:
    from app.tami import orchestrator
    response = await orchestrator.chat(db, request)
"""

# Re-export key components for easier access
from app.tami.orchestrator import chat, track_activity
from app.tami.intent import Intent, classify_intent
from app.tami.models import (
    ConversationSession,
    ConversationMessage,
    UserActivity,
    UserActivityType,
)

__all__ = [
    "chat",
    "track_activity",
    "Intent",
    "classify_intent",
    "ConversationSession",
    "ConversationMessage",
    "UserActivity",
    "UserActivityType",
]
