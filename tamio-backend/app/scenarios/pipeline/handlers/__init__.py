"""
Scenario Handlers - Type-specific scenario processing.

Each handler implements:
- required_params(): List of required parameter names
- linked_prompts(): Generate linked change prompts
- apply(): Generate ScenarioDelta from definition
"""

from typing import TYPE_CHECKING
from app.scenarios.pipeline.types import ScenarioTypeEnum

if TYPE_CHECKING:
    from app.scenarios.pipeline.handlers.base import BaseScenarioHandler


def get_handler(scenario_type: ScenarioTypeEnum) -> "BaseScenarioHandler":
    """Get the appropriate handler for a scenario type."""
    from app.scenarios.pipeline.handlers.payment_delay_in import PaymentDelayInHandler
    from app.scenarios.pipeline.handlers.client_loss import ClientLossHandler
    from app.scenarios.pipeline.handlers.client_gain import ClientGainHandler
    from app.scenarios.pipeline.handlers.client_change import ClientChangeHandler
    from app.scenarios.pipeline.handlers.hiring import HiringHandler
    from app.scenarios.pipeline.handlers.firing import FiringHandler
    from app.scenarios.pipeline.handlers.contractor_gain import ContractorGainHandler
    from app.scenarios.pipeline.handlers.contractor_loss import ContractorLossHandler
    from app.scenarios.pipeline.handlers.increased_expense import IncreasedExpenseHandler
    from app.scenarios.pipeline.handlers.decreased_expense import DecreasedExpenseHandler
    from app.scenarios.pipeline.handlers.payment_delay_out import PaymentDelayOutHandler

    handlers = {
        ScenarioTypeEnum.PAYMENT_DELAY_IN: PaymentDelayInHandler(),
        ScenarioTypeEnum.CLIENT_LOSS: ClientLossHandler(),
        ScenarioTypeEnum.CLIENT_GAIN: ClientGainHandler(),
        ScenarioTypeEnum.CLIENT_CHANGE: ClientChangeHandler(),
        ScenarioTypeEnum.HIRING: HiringHandler(),
        ScenarioTypeEnum.FIRING: FiringHandler(),
        ScenarioTypeEnum.CONTRACTOR_GAIN: ContractorGainHandler(),
        ScenarioTypeEnum.CONTRACTOR_LOSS: ContractorLossHandler(),
        ScenarioTypeEnum.INCREASED_EXPENSE: IncreasedExpenseHandler(),
        ScenarioTypeEnum.DECREASED_EXPENSE: DecreasedExpenseHandler(),
        ScenarioTypeEnum.PAYMENT_DELAY_OUT: PaymentDelayOutHandler(),
    }

    handler = handlers.get(scenario_type)
    if not handler:
        raise ValueError(f"No handler for scenario type: {scenario_type}")

    return handler
