"""
Base Scenario Handler - Abstract base class for scenario handlers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import secrets

from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    PromptRequest,
    EventDelta,
)


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(8)}"


class BaseScenarioHandler(ABC):
    """
    Abstract base class for scenario handlers.

    Each scenario type has a handler that knows how to:
    1. Determine required parameters
    2. Generate linked change prompts
    3. Apply the scenario to generate deltas
    """

    @abstractmethod
    def required_params(self) -> List[str]:
        """
        Return list of required parameter names for this scenario type.

        Used to validate that all necessary inputs are provided.
        """
        pass

    @abstractmethod
    def linked_prompt_types(self) -> List[str]:
        """
        Return list of linked change types this scenario can trigger.

        Used to determine which linked prompts to generate.
        """
        pass

    @abstractmethod
    async def apply(
        self,
        db: AsyncSession,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Apply the scenario to generate a ScenarioDelta.

        This is the core transformation that determines all changes
        to canonical data if the scenario is confirmed.
        """
        pass

    def create_event_delta(
        self,
        scenario_id: str,
        operation: str,
        event_data: Dict[str, Any],
        original_event_id: str = None,
        linked_change_id: str = None,
        change_reason: str = "",
    ) -> EventDelta:
        """Helper to create an EventDelta."""
        return EventDelta(
            event_id=event_data.get("id", generate_id("evt")),
            original_event_id=original_event_id,
            operation=operation,
            event_data=event_data,
            scenario_id=scenario_id,
            linked_change_id=linked_change_id,
            change_reason=change_reason,
        )

    def validate_params(self, definition: ScenarioDefinition) -> List[str]:
        """
        Validate that all required parameters are present.

        Returns list of missing parameter names.
        """
        required = self.required_params()
        missing = []

        for param in required:
            if param.startswith("scope."):
                attr = param.replace("scope.", "")
                val = getattr(definition.scope, attr, None)
                if val is None or (isinstance(val, list) and len(val) == 0):
                    missing.append(param)
            else:
                if param not in definition.parameters:
                    missing.append(param)

        return missing
