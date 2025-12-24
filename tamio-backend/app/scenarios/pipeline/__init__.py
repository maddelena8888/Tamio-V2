"""
Scenario Pipeline Module - Deterministic Multi-Step Scenario Engine.

This module implements the scenario pipeline as described in the Mermaid decision trees:
1. seedScenario() - Initialize scenario with type and entry path
2. collectScopeAndParams() - Gather required parameters, return prompts if missing
3. generateLinkedPrompts() - Generate prompts for linked changes
4. applyScenarioToCanonical() - Generate ScenarioDelta
5. buildScenarioLayer() - Create layered events from base + delta
6. runRules() - Evaluate financial rules on layered forecast
7. commitScenario() - Commit deltas to canonical data
8. discardScenario() - Discard scenario without changes
"""

from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    PromptRequest,
    LinkedChange,
    PipelineStage,
    PipelineResult,
    AnswerType,
)

from app.scenarios.pipeline.engine import ScenarioPipeline

__all__ = [
    "ScenarioDefinition",
    "ScenarioDelta",
    "PromptRequest",
    "LinkedChange",
    "PipelineStage",
    "PipelineResult",
    "AnswerType",
    "ScenarioPipeline",
]
