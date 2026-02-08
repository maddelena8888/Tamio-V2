"""Scenario schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.scenario import (
    FinancialRuleCreate,
    FinancialRuleUpdate,
    FinancialRuleResponse,
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    CustomScenarioCreate,
    ForecastDeltaItem,
    RuleEvaluationResponse,
    ScenarioForecastResponse,
    ScenarioLayerAdd,
    SuggestedDependentScenario,
    ScenarioComparisonResponse,
    ScenarioEventDetail,
    ScenarioLayerResponse,
    PaymentDelayParams,
    ClientLossParams,
    ClientGainParams,
    ClientChangeParams,
    HiringParams,
    FiringParams,
    ContractorChangeParams,
    ExpenseChangeParams,
    DecisionSignal,
)

# Re-export the model enums that were previously imported here
from app.models.scenario import RuleType, RuleSeverity, ScenarioType, ScenarioStatus

__all__ = [
    # Enums from models
    "RuleType",
    "RuleSeverity",
    "ScenarioType",
    "ScenarioStatus",
    # Schemas
    "FinancialRuleCreate",
    "FinancialRuleUpdate",
    "FinancialRuleResponse",
    "ScenarioCreate",
    "ScenarioUpdate",
    "ScenarioResponse",
    "CustomScenarioCreate",
    "ForecastDeltaItem",
    "RuleEvaluationResponse",
    "ScenarioForecastResponse",
    "ScenarioLayerAdd",
    "SuggestedDependentScenario",
    "ScenarioComparisonResponse",
    "ScenarioEventDetail",
    "ScenarioLayerResponse",
    "PaymentDelayParams",
    "ClientLossParams",
    "ClientGainParams",
    "ClientChangeParams",
    "HiringParams",
    "FiringParams",
    "ContractorChangeParams",
    "ExpenseChangeParams",
    "DecisionSignal",
]
