"""TAMI Intent Classification Module.

Lightweight intent classification to route queries to appropriate knowledge
and provide more relevant responses.
"""
import re
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum


class Intent(str, Enum):
    """User intent categories for TAMI queries."""
    # Question types
    EXPLAIN_FORECAST = "explain_forecast"
    EXPLAIN_TERM = "explain_term"  # Glossary lookup
    EXPLAIN_SCENARIO = "explain_scenario"
    EXPLAIN_RISK = "explain_risk"
    HOW_TO = "how_to"

    # Action intents
    CREATE_SCENARIO = "create_scenario"
    MODIFY_SCENARIO = "modify_scenario"
    COMPARE_SCENARIOS = "compare_scenarios"
    GOAL_PLANNING = "goal_planning"

    # Status queries
    CHECK_STATUS = "check_status"
    CHECK_RUNWAY = "check_runway"
    CHECK_CASH = "check_cash"

    # General
    GREETING = "greeting"
    HELP = "help"
    GENERAL_QUESTION = "general_question"


# Pattern-based intent detection
# Each pattern maps to (intent, priority, keywords to extract)
INTENT_PATTERNS: List[Tuple[str, Intent, int]] = [
    # Greetings
    (r"^(hi|hello|hey|good morning|good afternoon|good evening)\b", Intent.GREETING, 100),

    # Help requests
    (r"\b(help|what can you do|how do you work)\b", Intent.HELP, 90),

    # How-to questions (high priority)
    (r"\bhow (do|can|should) i\b", Intent.HOW_TO, 85),
    (r"\bhow to\b", Intent.HOW_TO, 85),
    (r"\bsteps to\b", Intent.HOW_TO, 85),
    (r"\bwalk me through\b", Intent.HOW_TO, 85),
    (r"\bguide me\b", Intent.HOW_TO, 85),

    # Term/definition queries
    (r"\bwhat (is|are|does) (a |an |the )?([\w\s]+)\??\s*$", Intent.EXPLAIN_TERM, 80),
    (r"\bwhat does ([\w\s]+) mean\b", Intent.EXPLAIN_TERM, 80),
    (r"\bdefine\b", Intent.EXPLAIN_TERM, 80),
    (r"\bexplain ([\w\s]+) to me\b", Intent.EXPLAIN_TERM, 75),
    (r"\bmeaning of\b", Intent.EXPLAIN_TERM, 80),

    # Risk queries
    (r"\b(risk|danger|warning|breach|red|amber|green)\b", Intent.EXPLAIN_RISK, 75),
    (r"\b(is|am) (i|we|my) (safe|at risk|in trouble)\b", Intent.EXPLAIN_RISK, 75),
    (r"\bbuffer\b", Intent.EXPLAIN_RISK, 70),

    # Cash and runway queries
    (r"\brunway\b", Intent.CHECK_RUNWAY, 70),
    (r"\bhow (long|many weeks|many months)\b.*\blast\b", Intent.CHECK_RUNWAY, 70),
    (r"\bcash (position|balance|on hand)\b", Intent.CHECK_CASH, 70),
    (r"\bhow much (cash|money)\b", Intent.CHECK_CASH, 70),

    # Status queries
    (r"\b(what.*(look|state|status)|how.*(doing|look))\b", Intent.CHECK_STATUS, 65),
    (r"\b(overview|summary|dashboard)\b", Intent.CHECK_STATUS, 65),

    # Scenario creation
    (r"\bwhat (if|happens if)\b", Intent.CREATE_SCENARIO, 80),
    (r"\bif (i|we) (lose|add|hire|fire|cut|delay|increase|decrease)\b", Intent.CREATE_SCENARIO, 80),
    (r"\bscenario where\b", Intent.CREATE_SCENARIO, 80),
    (r"\bmodel (a|the)\b", Intent.CREATE_SCENARIO, 75),
    (r"\bshow me (what|if)\b", Intent.CREATE_SCENARIO, 75),

    # Scenario modification
    (r"\bchange (the|this) scenario\b", Intent.MODIFY_SCENARIO, 85),
    (r"\bupdate (the|this) scenario\b", Intent.MODIFY_SCENARIO, 85),
    (r"\bmodify\b", Intent.MODIFY_SCENARIO, 80),
    (r"\binstead\b", Intent.MODIFY_SCENARIO, 70),
    (r"\bwhat if.*(instead|rather)\b", Intent.MODIFY_SCENARIO, 75),

    # Scenario comparison
    (r"\bcompare\b", Intent.COMPARE_SCENARIOS, 80),
    (r"\bdifference between\b", Intent.COMPARE_SCENARIOS, 80),
    (r"\bwhich (scenario|option|is better)\b", Intent.COMPARE_SCENARIOS, 75),

    # Goal planning
    (r"\b(how (can|do) (i|we)|i want to|i need to)\b.*(reach|achieve|get to|extend|increase|reduce)\b", Intent.GOAL_PLANNING, 75),
    (r"\bextend.*(runway)\b", Intent.GOAL_PLANNING, 75),
    (r"\breduce.*(burn|expenses)\b", Intent.GOAL_PLANNING, 75),
    (r"\bincrease.*(runway|cash)\b", Intent.GOAL_PLANNING, 75),
    (r"\bgoal\b", Intent.GOAL_PLANNING, 70),

    # Forecast explanation
    (r"\bforecast\b", Intent.EXPLAIN_FORECAST, 60),
    (r"\bexplain\b", Intent.EXPLAIN_FORECAST, 50),
    (r"\bwhy\b", Intent.EXPLAIN_FORECAST, 50),

    # Specific scenario type queries
    (r"\b(client|customer) (loss|leaving|churning|cancel)\b", Intent.EXPLAIN_SCENARIO, 70),
    (r"\b(hire|hiring|new employee|add.*staff)\b", Intent.EXPLAIN_SCENARIO, 70),
    (r"\b(delay|late) (payment|invoice)\b", Intent.EXPLAIN_SCENARIO, 70),
    (r"\b(cut|reduce|lower).*(expense|cost|spending)\b", Intent.EXPLAIN_SCENARIO, 70),
]

# Keywords that map to specific glossary categories
GLOSSARY_KEYWORDS: Dict[str, List[str]] = {
    "runway": ["runway", "months of runway", "burn rate", "operating expenses"],
    "forecasting": ["forecast", "projection", "13-week", "cash flow forecast"],
    "scenarios": ["scenario", "what-if", "modeling", "simulation"],
    "risk": ["buffer", "breach", "threshold", "minimum cash"],
    "clients": ["client", "customer", "revenue", "churn", "payment behavior"],
    "expenses": ["expense", "payroll", "fixed cost", "variable cost", "overhead"],
}


def classify_intent(message: str, context: Optional[Dict[str, Any]] = None) -> Tuple[Intent, float, List[str]]:
    """
    Classify the intent of a user message.

    Args:
        message: The user's message
        context: Optional context (e.g., active scenario, recent activities)

    Returns:
        Tuple of (intent, confidence, extracted_keywords)
    """
    message_lower = message.lower().strip()

    # Check for empty or very short messages
    if len(message_lower) < 2:
        return (Intent.GENERAL_QUESTION, 0.3, [])

    best_intent = Intent.GENERAL_QUESTION
    best_priority = 0
    extracted_keywords: List[str] = []

    # Pattern-based matching
    for pattern, intent, priority in INTENT_PATTERNS:
        match = re.search(pattern, message_lower, re.IGNORECASE)
        if match and priority > best_priority:
            best_intent = intent
            best_priority = priority
            # Extract matched groups if any
            if match.groups():
                extracted_keywords = [g.strip() for g in match.groups() if g]

    # Context-aware adjustments
    if context:
        # If there's an active scenario, bias toward scenario-related intents
        if context.get("active_scenario_id"):
            if best_intent == Intent.GENERAL_QUESTION:
                best_intent = Intent.EXPLAIN_SCENARIO
                best_priority = 55
            elif best_intent == Intent.CREATE_SCENARIO:
                best_intent = Intent.MODIFY_SCENARIO
                best_priority = max(best_priority, 70)

        # If user recently viewed scenarios page, bias toward scenario intents
        recent_activities = context.get("recent_activities", [])
        scenario_activities = [a for a in recent_activities if "scenario" in str(a).lower()]
        if scenario_activities and best_intent == Intent.GENERAL_QUESTION:
            best_intent = Intent.EXPLAIN_SCENARIO
            best_priority = 50

    # Calculate confidence (normalize priority to 0-1 range)
    confidence = min(best_priority / 100.0, 1.0)

    return (best_intent, confidence, extracted_keywords)


def extract_glossary_terms(message: str) -> List[str]:
    """
    Extract potential glossary terms from a message.

    Returns list of terms that might need glossary lookup.
    """
    message_lower = message.lower()
    found_terms = []

    for category, keywords in GLOSSARY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in message_lower:
                found_terms.append(keyword)

    return found_terms


def get_relevant_knowledge_keys(intent: Intent, keywords: List[str]) -> Dict[str, List[str]]:
    """
    Get relevant knowledge base keys based on intent and keywords.

    Returns dict with keys for each knowledge category to look up.
    """
    keys = {
        "glossary_terms": [],
        "scenario_types": [],
        "best_practice_categories": [],
        "features": [],
        "how_to_topics": [],
        "situations": [],
    }

    # Map intents to knowledge lookups
    if intent == Intent.EXPLAIN_TERM:
        keys["glossary_terms"] = keywords if keywords else []

    elif intent == Intent.HOW_TO:
        # Map common how-to phrases to topics
        keyword_str = " ".join(keywords).lower()
        if "client" in keyword_str or "customer" in keyword_str:
            keys["how_to_topics"].append("add_client")
        if "expense" in keyword_str or "cost" in keyword_str:
            keys["how_to_topics"].append("add_expense")
        if "scenario" in keyword_str:
            keys["how_to_topics"].append("create_scenario")
        if "forecast" in keyword_str:
            keys["how_to_topics"].append("interpret_forecast")
        if "xero" in keyword_str:
            keys["how_to_topics"].append("connect_xero")

    elif intent == Intent.EXPLAIN_RISK:
        keys["best_practice_categories"].append("risk_management")
        keys["features"].append("buffer_rules")

    elif intent in (Intent.CREATE_SCENARIO, Intent.EXPLAIN_SCENARIO):
        # Map keywords to scenario types
        keyword_str = " ".join(keywords).lower()
        if any(w in keyword_str for w in ["client", "customer", "churn", "lose", "loss"]):
            keys["scenario_types"].append("client_loss")
        if any(w in keyword_str for w in ["hire", "staff", "employee", "team"]):
            keys["scenario_types"].append("new_hire")
        if any(w in keyword_str for w in ["delay", "late", "payment"]):
            keys["scenario_types"].append("payment_delay")
        if any(w in keyword_str for w in ["expense", "cut", "reduce", "cost"]):
            keys["scenario_types"].append("expense_adjustment")

    elif intent == Intent.GOAL_PLANNING:
        keys["best_practice_categories"].append("runway_extension")
        keys["how_to_topics"].append("extend_runway")

    elif intent == Intent.CHECK_RUNWAY:
        keys["glossary_terms"].extend(["runway", "burn_rate"])
        keys["features"].append("runway_tracking")

    elif intent == Intent.CHECK_CASH:
        keys["glossary_terms"].extend(["cash_position", "opening_balance"])
        keys["features"].append("cash_tracking")

    elif intent == Intent.HELP:
        keys["features"].append("tami_assistant")
        keys["situations"].append("first_time_user")

    return keys


def get_intent_description(intent: Intent) -> str:
    """Get a human-readable description of an intent."""
    descriptions = {
        Intent.EXPLAIN_FORECAST: "Explaining the cash flow forecast",
        Intent.EXPLAIN_TERM: "Defining a financial term",
        Intent.EXPLAIN_SCENARIO: "Explaining a scenario type",
        Intent.EXPLAIN_RISK: "Explaining risk status or buffer rules",
        Intent.HOW_TO: "Providing step-by-step guidance",
        Intent.CREATE_SCENARIO: "Creating a what-if scenario",
        Intent.MODIFY_SCENARIO: "Modifying an existing scenario",
        Intent.COMPARE_SCENARIOS: "Comparing multiple scenarios",
        Intent.GOAL_PLANNING: "Planning toward a financial goal",
        Intent.CHECK_STATUS: "Checking overall financial status",
        Intent.CHECK_RUNWAY: "Checking cash runway",
        Intent.CHECK_CASH: "Checking cash position",
        Intent.GREETING: "Responding to greeting",
        Intent.HELP: "Providing help and guidance",
        Intent.GENERAL_QUESTION: "Answering a general question",
    }
    return descriptions.get(intent, "Processing query")


def should_use_fast_model(intent: Intent, confidence: float) -> bool:
    """
    Determine if we should use the fast model (gpt-4o-mini) for this query.

    Fast model is appropriate for:
    - Simple clarifying questions
    - Greetings and help
    - Term definitions
    - High-confidence simple queries

    Full model needed for:
    - Scenario creation/modification (needs tool calling)
    - Complex analysis
    - Goal planning
    - Low-confidence queries (need more reasoning)
    """
    # Always use fast model for these simple intents
    fast_intents = {
        Intent.GREETING,
        Intent.HELP,
        Intent.EXPLAIN_TERM,
        Intent.GENERAL_QUESTION,
    }

    if intent in fast_intents:
        return True

    # Use fast model for simple status checks with high confidence
    simple_status_intents = {
        Intent.CHECK_STATUS,
        Intent.CHECK_RUNWAY,
        Intent.CHECK_CASH,
        Intent.EXPLAIN_RISK,
    }

    if intent in simple_status_intents and confidence >= 0.7:
        return True

    # Use full model for complex operations
    complex_intents = {
        Intent.CREATE_SCENARIO,
        Intent.MODIFY_SCENARIO,
        Intent.COMPARE_SCENARIOS,
        Intent.GOAL_PLANNING,
    }

    if intent in complex_intents:
        return False

    # Default: use fast model for high confidence, full for uncertain
    return confidence >= 0.6
