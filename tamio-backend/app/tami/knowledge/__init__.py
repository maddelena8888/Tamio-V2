"""TAMI Complete Knowledge Base

This package contains ALL curated knowledge that TAMI uses to provide
accurate, relevant answers about Tamio's features and financial concepts.

Categories:
1. GLOSSARY - Financial terms and definitions (60+ terms)
2. SCENARIO_EXPLANATIONS - What each scenario does, when to use it
3. RISK_INTERPRETATION - RED/AMBER/GREEN framework, action windows
4. BEST_PRACTICES - Situational guidance and proactive advice
5. PRODUCT_FEATURES - How Tamio features work, how-to guides
6. COMMON_SITUATIONS - Pre-built responses for frequent cases
7. HOW_TO_GUIDES - Step-by-step instructions for common tasks
"""

from app.tami.knowledge.knowledge_base import (
    # Main knowledge dictionaries
    GLOSSARY,
    SCENARIO_EXPLANATIONS,
    RISK_INTERPRETATION,
    BEST_PRACTICES,
    PRODUCT_FEATURES,
    COMMON_SITUATIONS,
    HOW_TO_GUIDES,
    # Helper functions
    get_glossary_term,
    get_glossary_by_category,
    get_scenario_explanation,
    get_risk_status,
    get_best_practices,
    get_feature_knowledge,
    get_common_situation,
    get_how_to_guide,
    get_all_glossary,
    get_all_scenarios,
    get_all_features,
    get_all_situations,
    get_all_how_tos,
    search_glossary,
)

__all__ = [
    # Main knowledge dictionaries
    "GLOSSARY",
    "SCENARIO_EXPLANATIONS",
    "RISK_INTERPRETATION",
    "BEST_PRACTICES",
    "PRODUCT_FEATURES",
    "COMMON_SITUATIONS",
    "HOW_TO_GUIDES",
    # Helper functions
    "get_glossary_term",
    "get_glossary_by_category",
    "get_scenario_explanation",
    "get_risk_status",
    "get_best_practices",
    "get_feature_knowledge",
    "get_common_situation",
    "get_how_to_guide",
    "get_all_glossary",
    "get_all_scenarios",
    "get_all_features",
    "get_all_situations",
    "get_all_how_tos",
    "search_glossary",
]
