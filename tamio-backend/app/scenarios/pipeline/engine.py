"""
Scenario Pipeline Engine - Orchestrates deterministic scenario processing.

Pipeline Stages (matching Mermaid):
1. seedScenario(type, entryPath) - Initialize scenario
2. collectScopeAndParams(scenario) - Gather required params, return prompts if missing
3. generateLinkedPrompts(scenario, context) - Generate linked change prompts
4. applyScenarioToCanonical(scenario, context) - Generate ScenarioDelta
5. buildScenarioLayer(base_events, delta) - Create layered events
6. runRules(layered_events, rules) - Evaluate financial rules
7. commitScenario(delta) - Commit to canonical data
8. discardScenario(scenario_id) - Discard without changes
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any, List, Optional, Tuple
from datetime import date, timedelta, datetime
from decimal import Decimal
import secrets

from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    PromptRequest,
    LinkedChange,
    PipelineStage,
    PipelineResult,
    ScenarioTypeEnum,
    EntryPath,
    ScenarioStatusEnum,
    AnswerType,
    ScopeConfig,
    EventDelta,
    ObjectDelta,
    ScheduleDelta,
    AgreementDelta,
    PromptOption,
    LinkedChangeType,
    RuleResult,
    ForecastSummary,
    WeekSummary,
    DeltaSummary,
)
from app.scenarios import models
from app.scenarios.overlay import ScenarioOverlayService, compute_weekly_forecast_from_events
from app.scenarios.commit import ScenarioCommitService
from app.data.models import CashEvent, Client, ExpenseBucket, User, CashAccount
from app.forecast.engine_v2 import calculate_13_week_forecast


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(8)}"


class ScenarioPipeline:
    """
    Main pipeline engine for scenario processing.

    Implements deterministic, multi-step scenario modeling with:
    - Required prompt generation when info is missing
    - Linked change suggestions based on decision trees
    - Layer-based overlay without mutating canonical data
    - Full attribution tracking for explainability
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # PIPELINE STAGE 1: SEED SCENARIO
    # =========================================================================

    async def seed_scenario(
        self,
        user_id: str,
        scenario_type: ScenarioTypeEnum,
        entry_path: EntryPath = EntryPath.MANUAL,
        name: Optional[str] = None,
        suggested_reason: Optional[str] = None,
    ) -> ScenarioDefinition:
        """
        Stage 1: Initialize a new scenario.

        Creates a ScenarioDefinition in DRAFT status with no parameters.
        Next step: collectScopeAndParams() to gather required inputs.
        """
        scenario_id = generate_id("sc")

        # Generate default name if not provided
        if not name:
            type_names = {
                ScenarioTypeEnum.PAYMENT_DELAY_IN: "Payment Delay (In)",
                ScenarioTypeEnum.CLIENT_LOSS: "Client Loss",
                ScenarioTypeEnum.CLIENT_GAIN: "New Client",
                ScenarioTypeEnum.CLIENT_CHANGE: "Client Change",
                ScenarioTypeEnum.HIRING: "New Hire",
                ScenarioTypeEnum.FIRING: "Termination",
                ScenarioTypeEnum.CONTRACTOR_GAIN: "New Contractor",
                ScenarioTypeEnum.CONTRACTOR_LOSS: "Contractor End",
                ScenarioTypeEnum.INCREASED_EXPENSE: "New Expense",
                ScenarioTypeEnum.DECREASED_EXPENSE: "Expense Reduction",
                ScenarioTypeEnum.PAYMENT_DELAY_OUT: "Payment Delay (Out)",
            }
            name = f"{type_names.get(scenario_type, 'Scenario')} - {date.today()}"

        definition = ScenarioDefinition(
            scenario_id=scenario_id,
            user_id=user_id,
            scenario_type=scenario_type,
            entry_path=entry_path,
            suggested_reason=suggested_reason,
            name=name,
            status=ScenarioStatusEnum.DRAFT,
            current_stage=PipelineStage.SCOPE,
            completed_stages=[],
            created_at=datetime.now(),
        )

        return definition

    # =========================================================================
    # PIPELINE STAGE 2: COLLECT SCOPE AND PARAMS
    # =========================================================================

    async def collect_scope_and_params(
        self,
        definition: ScenarioDefinition,
        provided_answers: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ScenarioDefinition, List[PromptRequest]]:
        """
        Stage 2: Collect scope and parameters for the scenario.

        Returns prompts for any required information that is missing.
        If all required params are provided, advances to next stage.
        """
        provided_answers = provided_answers or {}

        # Apply any provided answers
        definition = self._apply_answers(definition, provided_answers)

        # Get required params for this scenario type
        required_prompts = await self._get_required_prompts(definition)

        # Filter to only unanswered prompts
        pending_prompts = [
            p for p in required_prompts
            if not self._is_param_provided(definition, p.maps_to)
        ]

        if pending_prompts:
            definition.pending_prompts = pending_prompts
            definition.current_stage = PipelineStage.PARAMS
        else:
            # All required params collected, advance stage
            if PipelineStage.SCOPE not in definition.completed_stages:
                definition.completed_stages.append(PipelineStage.SCOPE)
            if PipelineStage.PARAMS not in definition.completed_stages:
                definition.completed_stages.append(PipelineStage.PARAMS)
            definition.current_stage = PipelineStage.LINKED_PROMPTS
            definition.pending_prompts = []

        return definition, pending_prompts

    async def _get_required_prompts(
        self,
        definition: ScenarioDefinition
    ) -> List[PromptRequest]:
        """Get required prompts for a scenario type."""
        prompts = []
        scenario_type = definition.scenario_type

        # =====================================================================
        # PAYMENT DELAY (CASH IN)
        # =====================================================================
        if scenario_type == ScenarioTypeEnum.PAYMENT_DELAY_IN:
            # Client selection
            clients = await self._get_clients(definition.user_id)
            if clients:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which client's payments are being delayed?",
                    help_text="Select the client whose payments will come in later than expected",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=c.id, label=c.name, description=c.client_type)
                        for c in clients
                    ],
                    required=True,
                    maps_to="scope.client_ids",
                ))

            # Delay duration
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="How many weeks will the payment be delayed?",
                help_text="Enter the number of weeks to shift payment dates forward",
                answer_type=AnswerType.NUMERIC,
                required=True,
                min_value=1,
                max_value=52,
                maps_to="parameters.delay_weeks",
            ))

            # Partial payment
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Is this a partial payment?",
                help_text="If yes, specify what percentage has already been paid",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="parameters.is_partial",
            ))

            # Partial percentage (conditional)
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What percentage has been paid?",
                help_text="Enter the percentage of the original amount already received",
                answer_type=AnswerType.PERCENTAGE,
                required=False,
                min_value=0,
                max_value=100,
                maps_to="parameters.partial_payment_pct",
                depends_on=["parameters.is_partial"],
            ))

        # =====================================================================
        # CLIENT LOSS
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_LOSS:
            clients = await self._get_clients(definition.user_id)
            if clients:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which client are you losing?",
                    help_text="Select the client who will no longer be paying",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=c.id, label=c.name, description=c.client_type)
                        for c in clients
                    ],
                    required=True,
                    maps_to="scope.client_ids",
                ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When is the effective end date?",
                help_text="Revenue will be removed from this date forward",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.effective_date",
            ))

        # =====================================================================
        # CLIENT GAIN
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_GAIN:
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the client/project name?",
                help_text="Enter a name to identify this new revenue source",
                answer_type=AnswerType.TEXT,
                required=True,
                maps_to="parameters.client_name",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does this engagement start?",
                help_text="First expected payment date",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.start_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What type of agreement is this?",
                help_text="This affects how revenue is scheduled",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="retainer", label="Retainer", description="Fixed monthly payment"),
                    PromptOption(value="project", label="Project", description="Milestone-based payments"),
                    PromptOption(value="usage", label="Usage-based", description="Variable based on usage"),
                ],
                required=True,
                maps_to="parameters.agreement_type",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly amount?",
                help_text="Expected monthly revenue (or average for variable)",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.monthly_amount",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What are the payment terms?",
                help_text="Days from invoice to expected payment",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="0", label="Due on receipt", is_default=True),
                    PromptOption(value="15", label="Net 15"),
                    PromptOption(value="30", label="Net 30"),
                    PromptOption(value="45", label="Net 45"),
                    PromptOption(value="60", label="Net 60"),
                ],
                required=True,
                maps_to="parameters.payment_terms_days",
            ))

        # =====================================================================
        # CLIENT CHANGE (Upsell/Downsell)
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_CHANGE:
            clients = await self._get_clients(definition.user_id)
            if clients:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which client's contract is changing?",
                    help_text="Select the client whose revenue will change",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=c.id, label=c.name, description=c.client_type)
                        for c in clients
                    ],
                    required=True,
                    maps_to="scope.client_ids",
                ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What type of change is this?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="upsell", label="Upsell", description="Increasing revenue"),
                    PromptOption(value="downsell", label="Downsell", description="Decreasing revenue"),
                    PromptOption(value="scope_change", label="Scope Change", description="Restructuring"),
                ],
                required=True,
                maps_to="parameters.change_type",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly change amount?",
                help_text="Positive for increase, negative for decrease",
                answer_type=AnswerType.CURRENCY,
                required=True,
                maps_to="parameters.delta_amount",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does this change take effect?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.effective_date",
            ))

        # =====================================================================
        # HIRING
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.HIRING:
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the role title?",
                help_text="e.g., Senior Developer, Marketing Manager",
                answer_type=AnswerType.TEXT,
                required=True,
                maps_to="parameters.role_title",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When is the start date?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.start_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly cost (fully loaded)?",
                help_text="Include salary, benefits, taxes, etc.",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.monthly_cost",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the pay cycle?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="monthly", label="Monthly", is_default=True),
                    PromptOption(value="bi-weekly", label="Bi-weekly"),
                    PromptOption(value="weekly", label="Weekly"),
                ],
                required=True,
                maps_to="parameters.pay_frequency",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Are there one-off hiring costs?",
                help_text="Recruiter fees, equipment, onboarding, etc.",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="parameters.has_onboarding_costs",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What are the one-off hiring costs?",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="parameters.onboarding_costs",
                depends_on=["parameters.has_onboarding_costs"],
            ))

        # =====================================================================
        # FIRING
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.FIRING:
            # Could add employee selection if we track them
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the role/employee being terminated?",
                answer_type=AnswerType.TEXT,
                required=True,
                maps_to="parameters.role_title",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the termination date?",
                help_text="Last day of employment",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.end_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly cost being removed?",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.monthly_cost",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Are there severance or termination costs?",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="parameters.has_severance",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the severance amount?",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="parameters.severance_amount",
                depends_on=["parameters.has_severance"],
            ))

        # =====================================================================
        # CONTRACTOR GAIN
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CONTRACTOR_GAIN:
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the contractor/vendor name?",
                answer_type=AnswerType.TEXT,
                required=True,
                maps_to="parameters.contractor_name",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does this engagement start?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.start_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly estimate?",
                help_text="Average monthly cost for this contractor",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.monthly_estimate",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Is this fixed or variable cost?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="fixed", label="Fixed", description="Same amount each month"),
                    PromptOption(value="variable", label="Variable", description="Varies based on work"),
                ],
                required=True,
                maps_to="parameters.cost_type",
            ))

        # =====================================================================
        # CONTRACTOR LOSS
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CONTRACTOR_LOSS:
            # Get contractor expenses
            buckets = await self._get_expense_buckets(definition.user_id, "contractors")
            if buckets:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which contractor/expense is ending?",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=b.id, label=b.name, description=f"${b.monthly_amount}/mo")
                        for b in buckets
                    ],
                    required=True,
                    maps_to="scope.bucket_ids",
                ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does this end?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.end_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the monthly amount being reduced?",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.monthly_estimate",
            ))

        # =====================================================================
        # INCREASED EXPENSE
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.INCREASED_EXPENSE:
            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What category is this expense?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="software", label="Software/Tools"),
                    PromptOption(value="rent", label="Rent/Facilities"),
                    PromptOption(value="marketing", label="Marketing"),
                    PromptOption(value="tax", label="Tax Payment"),
                    PromptOption(value="equipment", label="Equipment"),
                    PromptOption(value="other", label="Other"),
                ],
                required=True,
                maps_to="parameters.category",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the expense name/description?",
                answer_type=AnswerType.TEXT,
                required=True,
                maps_to="parameters.expense_name",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Is this a one-off or recurring expense?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="one_off", label="One-off", description="Single payment"),
                    PromptOption(value="recurring", label="Recurring", description="Ongoing expense"),
                ],
                required=True,
                maps_to="parameters.expense_type",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the amount?",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.amount",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does this expense start/occur?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.effective_date",
            ))

        # =====================================================================
        # DECREASED EXPENSE
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.DECREASED_EXPENSE:
            buckets = await self._get_expense_buckets(definition.user_id)
            if buckets:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which expense is being reduced?",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=b.id, label=b.name, description=f"${b.monthly_amount}/mo")
                        for b in buckets
                    ],
                    required=True,
                    maps_to="scope.bucket_ids",
                ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the reduction amount per month?",
                answer_type=AnswerType.CURRENCY,
                required=True,
                min_value=0,
                maps_to="parameters.reduction_amount",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="When does the reduction take effect?",
                answer_type=AnswerType.DATE,
                required=True,
                maps_to="parameters.effective_date",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Is there a notice period or termination fee?",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="parameters.has_termination_costs",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What is the termination fee?",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="parameters.termination_fee",
                depends_on=["parameters.has_termination_costs"],
            ))

        # =====================================================================
        # PAYMENT DELAY (CASH OUT)
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.PAYMENT_DELAY_OUT:
            buckets = await self._get_expense_buckets(definition.user_id)
            if buckets:
                prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.SCOPE,
                    question="Which vendor/obligation is being delayed?",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=b.id, label=b.name, description=f"${b.monthly_amount}/mo")
                        for b in buckets
                    ],
                    required=True,
                    maps_to="scope.bucket_ids",
                ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="How many weeks will the payment be delayed?",
                answer_type=AnswerType.NUMERIC,
                required=True,
                min_value=1,
                max_value=12,
                maps_to="parameters.delay_weeks",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="Is this a partial payment?",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="parameters.is_partial",
            ))

            prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.PARAMS,
                question="What percentage has been paid?",
                answer_type=AnswerType.PERCENTAGE,
                required=False,
                min_value=0,
                max_value=100,
                maps_to="parameters.partial_payment_pct",
                depends_on=["parameters.is_partial"],
            ))

        return prompts

    # =========================================================================
    # PIPELINE STAGE 3: GENERATE LINKED PROMPTS
    # =========================================================================

    async def generate_linked_prompts(
        self,
        definition: ScenarioDefinition,
        canonical_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ScenarioDefinition, List[PromptRequest]]:
        """
        Stage 3: Generate prompts for linked changes based on decision tree.

        Example: Client Loss -> Prompt for contractor/tool reductions with lag
        """
        linked_prompts = []
        scenario_type = definition.scenario_type

        # =====================================================================
        # PAYMENT DELAY (IN) -> Linked: Delay vendors or reduce discretionary
        # =====================================================================
        if scenario_type == ScenarioTypeEnum.PAYMENT_DELAY_IN:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does this delay affect your cash-out timing?",
                help_text="You may want to adjust outgoing payments to match",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.affects_cash_out",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="How would you like to adjust?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(
                        value="delay_vendors",
                        label="Delay vendor payments",
                        description="Push out some outgoing payments"
                    ),
                    PromptOption(
                        value="reduce_discretionary",
                        label="Reduce discretionary spend",
                        description="Cut non-essential expenses"
                    ),
                    PromptOption(
                        value="none",
                        label="No adjustment",
                        description="Keep outgoing payments as scheduled"
                    ),
                ],
                required=False,
                maps_to="linked.adjustment_type",
                depends_on=["linked.affects_cash_out"],
            ))

        # =====================================================================
        # CLIENT LOSS -> Linked: Reduce contractors/tools/project costs
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_LOSS:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Should any costs be reduced when losing this client?",
                help_text="Variable costs tied to this client may no longer be needed",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="linked.reduce_costs",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Which costs should be reduced?",
                answer_type=AnswerType.MULTI_SELECT,
                options=[
                    PromptOption(value="contractors", label="Contractors", description="Reduce contractor spend"),
                    PromptOption(value="tools", label="Tools/Software", description="Cancel unused tools"),
                    PromptOption(value="project_costs", label="Project Costs", description="Reduce project expenses"),
                ],
                required=False,
                maps_to="linked.cost_types",
                depends_on=["linked.reduce_costs"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the total monthly reduction?",
                help_text="Total amount to reduce across selected categories",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.reduction_amount",
                depends_on=["linked.reduce_costs"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="How many weeks lag before cost reduction takes effect?",
                help_text="Notice periods, contract terms, etc.",
                answer_type=AnswerType.NUMERIC,
                required=False,
                min_value=0,
                max_value=12,
                maps_to="linked.lag_weeks",
                depends_on=["linked.reduce_costs"],
            ))

        # =====================================================================
        # CLIENT GAIN -> Linked: Add contractors/hiring/tools/onboarding
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_GAIN:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does this new client require additional capacity/cost?",
                help_text="You may need to hire or add contractors",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="linked.needs_capacity",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What type of capacity is needed?",
                answer_type=AnswerType.MULTI_SELECT,
                options=[
                    PromptOption(value="contractors", label="Contractors"),
                    PromptOption(value="hiring", label="New Hires"),
                    PromptOption(value="tools", label="Tools/Software"),
                    PromptOption(value="onboarding", label="One-off Onboarding"),
                ],
                required=False,
                maps_to="linked.capacity_types",
                depends_on=["linked.needs_capacity"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the monthly recurring cost?",
                help_text="Additional monthly cost for ongoing capacity",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.monthly_cost",
                depends_on=["linked.needs_capacity"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What are the one-off setup costs?",
                help_text="Onboarding, equipment, setup fees, etc.",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.onetime_cost",
                depends_on=["linked.needs_capacity"],
            ))

        # =====================================================================
        # CLIENT CHANGE -> Linked: Cost delta changes
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CLIENT_CHANGE:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does the cost base change with this contract change?",
                answer_type=AnswerType.TOGGLE,
                required=True,
                maps_to="linked.cost_changes",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Which cost drivers change?",
                answer_type=AnswerType.MULTI_SELECT,
                options=[
                    PromptOption(value="contractors", label="Contractors"),
                    PromptOption(value="delivery", label="Delivery Costs"),
                    PromptOption(value="tools", label="Tools"),
                ],
                required=False,
                maps_to="linked.cost_drivers",
                depends_on=["linked.cost_changes"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the monthly cost change?",
                help_text="Positive for increase, negative for decrease",
                answer_type=AnswerType.CURRENCY,
                required=False,
                maps_to="linked.cost_delta",
                depends_on=["linked.cost_changes"],
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Lag weeks before cost change takes effect?",
                answer_type=AnswerType.NUMERIC,
                required=False,
                min_value=0,
                max_value=8,
                maps_to="linked.lag_weeks",
                depends_on=["linked.cost_changes"],
            ))

        # =====================================================================
        # HIRING -> Linked: Revenue increase to support hire
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.HIRING:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does revenue need to increase to support this hire?",
                help_text="Optional: model expected revenue growth",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.needs_revenue",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the expected monthly revenue increase?",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.revenue_increase",
                depends_on=["linked.needs_revenue"],
            ))

        # =====================================================================
        # FIRING -> Linked: Delivery capacity drop
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.FIRING:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does delivery capacity drop affect revenue?",
                help_text="May need to reduce client commitments",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.affects_revenue",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the expected revenue impact?",
                help_text="Monthly revenue reduction (if any)",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.revenue_reduction",
                depends_on=["linked.affects_revenue"],
            ))

        # =====================================================================
        # CONTRACTOR GAIN -> Linked: Client/project linkage
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CONTRACTOR_GAIN:
            clients = await self._get_clients(definition.user_id)

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Is this contractor linked to a specific client/project?",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.is_linked",
            ))

            if clients:
                linked_prompts.append(PromptRequest(
                    prompt_id=generate_id("pr"),
                    scenario_id=definition.scenario_id,
                    stage=PipelineStage.LINKED_PROMPTS,
                    question="Which client/project?",
                    answer_type=AnswerType.SINGLE_SELECT,
                    options=[
                        PromptOption(value=c.id, label=c.name)
                        for c in clients
                    ],
                    required=False,
                    maps_to="linked.linked_client_id",
                    depends_on=["linked.is_linked"],
                ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Lag weeks after revenue starts?",
                help_text="How long after client revenue starts does this cost begin?",
                answer_type=AnswerType.NUMERIC,
                required=False,
                min_value=0,
                max_value=8,
                maps_to="linked.lag_weeks",
                depends_on=["linked.is_linked"],
            ))

        # =====================================================================
        # CONTRACTOR LOSS -> Linked: Revenue impact
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.CONTRACTOR_LOSS:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does losing this contractor affect revenue/delivery?",
                help_text="May slow down milestones or reduce capacity",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.affects_delivery",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="What is the expected revenue impact?",
                answer_type=AnswerType.CURRENCY,
                required=False,
                min_value=0,
                maps_to="linked.revenue_impact",
                depends_on=["linked.affects_delivery"],
            ))

        # =====================================================================
        # INCREASED EXPENSE -> Linked: Rule gating
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.INCREASED_EXPENSE:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Should this expense be gated by a rule?",
                help_text="e.g., Only proceed if buffer rule still passes",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.is_gated",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Which rule should gate this expense?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(value="buffer", label="Cash Buffer Rule"),
                    PromptOption(value="payroll", label="Payroll Coverage"),
                    PromptOption(value="capex", label="CapEx Gate"),
                ],
                required=False,
                maps_to="linked.gating_rule",
                depends_on=["linked.is_gated"],
            ))

        # =====================================================================
        # PAYMENT DELAY (OUT) -> Linked: Clustering risk mitigation
        # =====================================================================
        elif scenario_type == ScenarioTypeEnum.PAYMENT_DELAY_OUT:
            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="Does delaying this create clustering risk later?",
                help_text="Multiple large payments due at the same time",
                answer_type=AnswerType.TOGGLE,
                required=False,
                maps_to="linked.has_clustering_risk",
            ))

            linked_prompts.append(PromptRequest(
                prompt_id=generate_id("pr"),
                scenario_id=definition.scenario_id,
                stage=PipelineStage.LINKED_PROMPTS,
                question="How would you like to mitigate?",
                answer_type=AnswerType.SINGLE_SELECT,
                options=[
                    PromptOption(
                        value="catch_up",
                        label="Create catch-up schedule",
                        description="Spread the delayed amount over time"
                    ),
                    PromptOption(
                        value="spread",
                        label="Spread future payments",
                        description="Reduce clustering by spreading payments"
                    ),
                    PromptOption(
                        value="none",
                        label="Accept clustering risk",
                        description="Keep payments as delayed"
                    ),
                ],
                required=False,
                maps_to="linked.mitigation_type",
                depends_on=["linked.has_clustering_risk"],
            ))

        # Filter to only required/unanswered prompts
        # Also exclude prompts whose dependencies are answered with False/None
        pending_linked = []
        for p in linked_prompts:
            # Skip if already answered
            if self._is_param_provided(definition, p.maps_to):
                continue

            # Check if dependencies are met
            if p.depends_on:
                deps_met = True
                for dep in p.depends_on:
                    dep_value = self._get_param_value(definition, dep)
                    # Skip this prompt if dependency is False or not provided
                    if dep_value is None or dep_value is False:
                        deps_met = False
                        break
                if not deps_met:
                    continue

            pending_linked.append(p)

        if pending_linked:
            definition.pending_prompts = pending_linked
        else:
            if PipelineStage.LINKED_PROMPTS not in definition.completed_stages:
                definition.completed_stages.append(PipelineStage.LINKED_PROMPTS)
            definition.current_stage = PipelineStage.CANONICAL_DELTAS
            definition.pending_prompts = []

        return definition, pending_linked

    # =========================================================================
    # PIPELINE STAGE 4: APPLY SCENARIO TO CANONICAL
    # =========================================================================

    async def apply_scenario_to_canonical(
        self,
        definition: ScenarioDefinition,
    ) -> ScenarioDelta:
        """
        Stage 4: Generate the ScenarioDelta from the scenario definition.

        This is the core transformation step that determines all changes
        to canonical data.
        """
        from app.scenarios.pipeline.handlers import get_handler

        # Get the appropriate handler for this scenario type
        handler = get_handler(definition.scenario_type)

        # Generate the delta
        delta = await handler.apply(self.db, definition)

        # Mark stage complete
        if PipelineStage.CANONICAL_DELTAS not in definition.completed_stages:
            definition.completed_stages.append(PipelineStage.CANONICAL_DELTAS)
        definition.current_stage = PipelineStage.OVERLAY_FORECAST

        return delta

    # =========================================================================
    # PIPELINE STAGE 5: BUILD SCENARIO LAYER
    # =========================================================================

    async def build_scenario_layer(
        self,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
    ) -> Tuple[ForecastSummary, ForecastSummary, DeltaSummary]:
        """
        Stage 5: Build layered forecast from base events + delta.

        V4 Implementation:
        - Applies delta directly to base forecast output (preserves alignment)
        - Works regardless of underlying data source (Client/ExpenseBucket or ObligationSchedule)

        Returns (base_forecast, scenario_forecast, delta_summary)
        """
        # Get base forecast - this is the source of truth
        base_forecast_data = await calculate_13_week_forecast(
            self.db, definition.user_id
        )

        forecast_start = date.today()

        # Check if we have schedule-based deltas (V4) or legacy event deltas
        has_schedule_deltas = (
            len(delta.created_schedules) > 0 or
            len(delta.updated_schedules) > 0 or
            len(delta.deleted_schedule_ids) > 0
        )

        if has_schedule_deltas:
            # V4: Apply schedule deltas directly to base forecast
            # This ensures scenario forecast starts from same base and stays aligned
            scenario_forecast_data = self._apply_schedule_deltas_to_forecast(
                base_forecast_data, delta, forecast_start
            )
        else:
            # Legacy: Use CashEvent-based approach
            result = await self.db.execute(
                select(CashEvent).where(
                    CashEvent.user_id == definition.user_id,
                    CashEvent.date >= date.today()
                ).order_by(CashEvent.date)
            )
            base_events = list(result.scalars().all())

            # Apply delta to create layered events
            layered_events = self._apply_delta_to_events(base_events, delta)

            # Compute scenario forecast
            scenario_forecast_data = await self._compute_forecast_with_events(
                definition.user_id, layered_events
            )

        # Convert to summary objects
        base_summary = self._forecast_to_summary(base_forecast_data)
        scenario_summary = self._forecast_to_summary(scenario_forecast_data)

        # Calculate deltas
        delta_summary = self._calculate_delta_summary(
            base_forecast_data, scenario_forecast_data, delta
        )

        if PipelineStage.OVERLAY_FORECAST not in definition.completed_stages:
            definition.completed_stages.append(PipelineStage.OVERLAY_FORECAST)
        definition.current_stage = PipelineStage.RULE_EVAL

        return base_summary, scenario_summary, delta_summary

    def _apply_schedule_deltas_to_forecast(
        self,
        base_forecast: Dict[str, Any],
        delta: ScenarioDelta,
        forecast_start: date,
    ) -> Dict[str, Any]:
        """
        Apply schedule-based deltas directly to the base forecast.

        This modifies the weekly cash_in/cash_out values based on:
        - created_schedules: Add new cash flows
        - updated_schedules: Modify/delete existing flows
        - deleted_schedule_ids: Remove cash flows

        Returns a new forecast dict with scenario applied.
        """
        import copy

        # Deep copy to avoid modifying base
        scenario_forecast = copy.deepcopy(base_forecast)
        weeks = scenario_forecast.get("weeks", [])

        # Helper to find week for a date
        def get_week_for_date(target_date: date) -> int:
            if isinstance(target_date, str):
                target_date = date.fromisoformat(target_date)
            days_from_start = (target_date - forecast_start).days
            week_num = (days_from_start // 7) + 1  # Week 1 starts at day 0
            return max(1, min(week_num, 13))  # Clamp to 1-13

        # Process created schedules (add new cash flows)
        for created in delta.created_schedules:
            data = created.schedule_data or {}
            due_date = data.get("due_date")
            if not due_date:
                continue

            if isinstance(due_date, str):
                due_date = date.fromisoformat(due_date)

            week_num = get_week_for_date(due_date)

            # Find the week in the forecast
            for week in weeks:
                if week["week_number"] == week_num:
                    amount = Decimal(str(data.get("estimated_amount", 0)))
                    category = data.get("category", "other")

                    # Determine direction
                    revenue_categories = {"revenue", "retainer", "project", "milestone", "invoice"}
                    direction = data.get("direction")
                    if not direction:
                        direction = "in" if category.lower() in revenue_categories else "out"

                    if direction == "in":
                        week["cash_in"] = str(Decimal(week["cash_in"]) + amount)
                    else:
                        week["cash_out"] = str(Decimal(week["cash_out"]) + amount)
                    break

        # Process updated schedules (modifications and deletions)
        for updated in delta.updated_schedules:
            data = updated.schedule_data or {}
            operation = updated.operation

            if operation == "delete":
                # Remove cash flow from the week it was originally scheduled
                original_amount = Decimal(str(data.get("original_amount", 0)))
                original_date = data.get("original_due_date")

                if original_date and original_amount > 0:
                    if isinstance(original_date, str):
                        original_date = date.fromisoformat(original_date)

                    week_num = get_week_for_date(original_date)

                    # Infer direction - deletions from client loss are typically revenue
                    category = data.get("category", "revenue")
                    revenue_categories = {"revenue", "retainer", "project", "milestone", "invoice"}
                    direction = "in" if category.lower() in revenue_categories else "out"

                    # If change_reason mentions "client" it's likely revenue
                    change_reason = updated.change_reason or ""
                    if "client" in change_reason.lower():
                        direction = "in"

                    for week in weeks:
                        if week["week_number"] == week_num:
                            if direction == "in":
                                week["cash_in"] = str(max(Decimal("0"), Decimal(week["cash_in"]) - original_amount))
                            else:
                                week["cash_out"] = str(max(Decimal("0"), Decimal(week["cash_out"]) - original_amount))
                            break

            elif operation == "modify":
                # Adjust amount - get the delta
                original_amount = Decimal(str(data.get("original_amount", 0)))
                new_amount = Decimal(str(data.get("estimated_amount", 0)))
                amount_change = new_amount - original_amount

                due_date = data.get("due_date")
                if due_date:
                    if isinstance(due_date, str):
                        due_date = date.fromisoformat(due_date)
                    week_num = get_week_for_date(due_date)

                    for week in weeks:
                        if week["week_number"] == week_num:
                            # Infer direction from category or existing data
                            category = data.get("category", "other")
                            revenue_categories = {"revenue", "retainer", "project", "milestone", "invoice"}
                            direction = "in" if category.lower() in revenue_categories else "out"

                            if direction == "in":
                                week["cash_in"] = str(Decimal(week["cash_in"]) + amount_change)
                            else:
                                week["cash_out"] = str(Decimal(week["cash_out"]) + amount_change)
                            break

            elif operation == "defer":
                # Move payment from one week to another
                original_date = data.get("original_due_date")
                new_date = data.get("due_date")
                amount = Decimal(str(data.get("estimated_amount", 0)))

                if original_date and new_date:
                    if isinstance(original_date, str):
                        original_date = date.fromisoformat(original_date)
                    if isinstance(new_date, str):
                        new_date = date.fromisoformat(new_date)

                    old_week = get_week_for_date(original_date)
                    new_week = get_week_for_date(new_date)

                    # Infer direction
                    category = data.get("category", "other")
                    revenue_categories = {"revenue", "retainer", "project", "milestone", "invoice"}
                    direction = "in" if category.lower() in revenue_categories else "out"

                    # Remove from old week
                    for week in weeks:
                        if week["week_number"] == old_week:
                            if direction == "in":
                                week["cash_in"] = str(max(Decimal("0"), Decimal(week["cash_in"]) - amount))
                            else:
                                week["cash_out"] = str(max(Decimal("0"), Decimal(week["cash_out"]) - amount))
                            break

                    # Add to new week (if within forecast window)
                    if new_week <= 13:
                        for week in weeks:
                            if week["week_number"] == new_week:
                                if direction == "in":
                                    week["cash_in"] = str(Decimal(week["cash_in"]) + amount)
                                else:
                                    week["cash_out"] = str(Decimal(week["cash_out"]) + amount)
                                break

        # Recalculate running balances
        starting_cash = Decimal(scenario_forecast.get("starting_cash", "0"))
        current_balance = starting_cash

        for week in weeks:
            week["starting_balance"] = str(current_balance)
            cash_in = Decimal(week["cash_in"])
            cash_out = Decimal(week["cash_out"])
            net_change = cash_in - cash_out
            week["net_change"] = str(net_change)
            ending_balance = current_balance + net_change
            week["ending_balance"] = str(ending_balance)
            current_balance = ending_balance

        # Recalculate summary
        forecast_weeks = [w for w in weeks if w["week_number"] > 0]
        balances = [Decimal(w["ending_balance"]) for w in forecast_weeks]

        if balances:
            lowest_balance = min(balances)
            lowest_week_idx = balances.index(lowest_balance)
            lowest_week = forecast_weeks[lowest_week_idx]["week_number"]
        else:
            lowest_balance = starting_cash
            lowest_week = 1

        total_cash_in = sum(Decimal(w["cash_in"]) for w in forecast_weeks)
        total_cash_out = sum(Decimal(w["cash_out"]) for w in forecast_weeks)

        # Runway calculation
        runway_weeks = 13
        for i, balance in enumerate(balances):
            if balance <= 0:
                runway_weeks = i + 1
                break

        scenario_forecast["summary"] = {
            "lowest_cash_week": lowest_week,
            "lowest_cash_amount": str(lowest_balance),
            "total_cash_in": str(total_cash_in),
            "total_cash_out": str(total_cash_out),
            "runway_weeks": runway_weeks,
        }

        return scenario_forecast

    def _apply_delta_to_events(
        self,
        base_events: List[CashEvent],
        delta: ScenarioDelta
    ) -> List[Any]:
        """Apply ScenarioDelta to base events to create layered list."""
        # Convert to dict for manipulation
        events_dict = {e.id: e for e in base_events}

        # Track deleted event IDs
        deleted_ids = set(delta.deleted_event_ids)

        # Apply updates
        for update in delta.updated_events:
            if update.original_event_id in events_dict:
                # Create mock event with updated data
                events_dict[update.original_event_id] = self._create_mock_event(
                    update.event_data
                )

        # Remove deleted events
        for event_id in deleted_ids:
            if event_id in events_dict:
                del events_dict[event_id]

        # Add new events
        added_events = []
        for created in delta.created_events:
            added_events.append(self._create_mock_event(created.event_data))

        return list(events_dict.values()) + added_events

    def _create_mock_event(self, data: Dict[str, Any]) -> Any:
        """Create a mock event object from dictionary data."""
        class MockEvent:
            def __init__(self, event_data):
                self.id = event_data.get("id", generate_id("mock"))
                date_val = event_data.get("date")
                if isinstance(date_val, str):
                    self.date = datetime.fromisoformat(date_val).date()
                else:
                    self.date = date_val
                self.amount = Decimal(str(event_data.get("amount", 0)))
                self.direction = event_data.get("direction", "out")
                self.event_type = event_data.get("event_type", "manual")
                self.category = event_data.get("category")
                self.confidence = event_data.get("confidence", "medium")
                self.scenario_id = event_data.get("scenario_id")

        return MockEvent(data)

    async def _compute_forecast_with_events(
        self,
        user_id: str,
        events: List[Any],
    ) -> Dict[str, Any]:
        """Compute 13-week forecast from provided events."""
        # Get starting cash
        result = await self.db.execute(
            select(func.sum(CashAccount.balance))
            .where(CashAccount.user_id == user_id)
        )
        starting_cash = result.scalar() or Decimal("0")

        forecast_start = date.today()
        weeks = []
        current_balance = starting_cash

        for week_num in range(1, 14):
            week_start = forecast_start + timedelta(days=(week_num - 1) * 7)
            week_end = week_start + timedelta(days=6)

            week_events = [
                e for e in events
                if week_start <= e.date <= week_end
            ]

            cash_in = sum(e.amount for e in week_events if e.direction == "in")
            cash_out = sum(e.amount for e in week_events if e.direction == "out")
            net_change = cash_in - cash_out
            ending_balance = current_balance + net_change

            weeks.append({
                "week_number": week_num,
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "starting_balance": str(current_balance),
                "cash_in": str(cash_in),
                "cash_out": str(cash_out),
                "net_change": str(net_change),
                "ending_balance": str(ending_balance),
            })

            current_balance = ending_balance

        balances = [Decimal(w["ending_balance"]) for w in weeks]
        lowest_balance = min(balances)
        lowest_week = balances.index(lowest_balance) + 1

        total_cash_in = sum(Decimal(w["cash_in"]) for w in weeks)
        total_cash_out = sum(Decimal(w["cash_out"]) for w in weeks)

        runway_weeks = 13
        for i, balance in enumerate(balances):
            if balance <= 0:
                runway_weeks = i + 1
                break

        return {
            "starting_cash": str(starting_cash),
            "forecast_start_date": forecast_start.isoformat(),
            "weeks": weeks,
            "summary": {
                "lowest_cash_week": lowest_week,
                "lowest_cash_amount": str(lowest_balance),
                "total_cash_in": str(total_cash_in),
                "total_cash_out": str(total_cash_out),
                "runway_weeks": runway_weeks,
            }
        }

    def _forecast_to_summary(self, forecast_data: Dict[str, Any]) -> ForecastSummary:
        """Convert forecast dict to ForecastSummary object."""
        weeks = []
        for w in forecast_data.get("weeks", []):
            weeks.append(WeekSummary(
                week_number=w["week_number"],
                week_start=date.fromisoformat(w["week_start"]),
                week_end=date.fromisoformat(w["week_end"]),
                starting_balance=Decimal(w["starting_balance"]),
                cash_in=Decimal(w["cash_in"]),
                cash_out=Decimal(w["cash_out"]),
                net_change=Decimal(w["net_change"]),
                ending_balance=Decimal(w["ending_balance"]),
            ))

        summary = forecast_data.get("summary", {})
        return ForecastSummary(
            starting_cash=Decimal(forecast_data.get("starting_cash", "0")),
            weeks=weeks,
            lowest_cash_week=summary.get("lowest_cash_week", 1),
            lowest_cash_amount=Decimal(summary.get("lowest_cash_amount", "0")),
            total_cash_in=Decimal(summary.get("total_cash_in", "0")),
            total_cash_out=Decimal(summary.get("total_cash_out", "0")),
            runway_weeks=summary.get("runway_weeks", 13),
        )

    def _calculate_delta_summary(
        self,
        base: Dict[str, Any],
        scenario: Dict[str, Any],
        delta: ScenarioDelta,
    ) -> DeltaSummary:
        """Calculate delta summary between base and scenario."""
        week_deltas = []
        base_weeks = base.get("weeks", [])
        scenario_weeks = scenario.get("weeks", [])

        for i, (bw, sw) in enumerate(zip(base_weeks, scenario_weeks)):
            week_deltas.append({
                "week_number": bw["week_number"],
                "delta_cash_in": str(Decimal(sw["cash_in"]) - Decimal(bw["cash_in"])),
                "delta_cash_out": str(Decimal(sw["cash_out"]) - Decimal(bw["cash_out"])),
                "delta_ending_balance": str(Decimal(sw["ending_balance"]) - Decimal(bw["ending_balance"])),
            })

        # Find top changed weeks
        changes = [(abs(Decimal(w["delta_ending_balance"])), w["week_number"]) for w in week_deltas]
        changes.sort(reverse=True)
        top_changed_weeks = [w for _, w in changes[:5] if _ > 0]

        base_summary = base.get("summary", {})
        scenario_summary = scenario.get("summary", {})

        return DeltaSummary(
            week_deltas=week_deltas,
            top_changed_weeks=top_changed_weeks,
            top_changed_events=[],  # Would need to track specific events
            net_cash_in_change=Decimal(scenario_summary.get("total_cash_in", "0")) - Decimal(base_summary.get("total_cash_in", "0")),
            net_cash_out_change=Decimal(scenario_summary.get("total_cash_out", "0")) - Decimal(base_summary.get("total_cash_out", "0")),
            runway_change=scenario_summary.get("runway_weeks", 0) - base_summary.get("runway_weeks", 0),
        )

    # =========================================================================
    # PIPELINE STAGE 6: RUN RULES
    # =========================================================================

    async def run_rules(
        self,
        definition: ScenarioDefinition,
        scenario_forecast: ForecastSummary,
    ) -> List[RuleResult]:
        """
        Stage 6: Evaluate financial rules against the scenario forecast.
        """
        from app.scenarios.rule_engine import evaluate_rules, generate_decision_signals

        # Get user's active rules
        result = await self.db.execute(
            select(models.FinancialRule).where(
                models.FinancialRule.user_id == definition.user_id,
                models.FinancialRule.is_active == True
            )
        )
        rules = result.scalars().all()

        rule_results = []

        for rule in rules:
            # Evaluate each rule
            if rule.rule_type == "minimum_cash_buffer":
                result = await self._evaluate_buffer_rule(
                    rule, scenario_forecast, definition.user_id
                )
                rule_results.append(result)

        if PipelineStage.RULE_EVAL not in definition.completed_stages:
            definition.completed_stages.append(PipelineStage.RULE_EVAL)

        definition.status = ScenarioStatusEnum.SIMULATED

        return rule_results

    async def _evaluate_buffer_rule(
        self,
        rule: models.FinancialRule,
        forecast: ForecastSummary,
        user_id: str,
    ) -> RuleResult:
        """Evaluate minimum cash buffer rule."""
        # Get monthly expenses
        result = await self.db.execute(
            select(func.sum(ExpenseBucket.monthly_amount))
            .where(ExpenseBucket.user_id == user_id)
        )
        monthly_opex = result.scalar() or Decimal("0")

        required_months = rule.threshold_config.get("months", 3)
        required_buffer = monthly_opex * required_months

        # Check each week
        breach_week = None
        breach_date = None
        breach_amount = None

        for week in forecast.weeks:
            if week.ending_balance < required_buffer:
                if breach_week is None:
                    breach_week = week.week_number
                    breach_date = week.week_end
                    breach_amount = required_buffer - week.ending_balance

        # Determine severity
        if breach_week is None:
            severity = "green"
            is_breached = False
            message = f"Cash buffer rule satisfied. Maintaining {required_months} months runway."
        elif breach_week <= 4:
            severity = "red"
            is_breached = True
            message = f"CRITICAL: Cash buffer breached in week {breach_week}. ${breach_amount:,.0f} below required buffer."
        elif breach_week <= 8:
            severity = "amber"
            is_breached = True
            message = f"WARNING: Cash buffer breached in week {breach_week}. Action needed soon."
        else:
            severity = "amber"
            is_breached = True
            message = f"NOTICE: Cash buffer breached in week {breach_week}. Plan ahead."

        # Recommended actions
        actions = []
        if is_breached:
            action_window = breach_week - 1 if breach_week > 1 else 0
            if action_window <= 2:
                actions = [
                    "Immediately review all outgoing payments",
                    "Contact clients to accelerate collections",
                    "Consider emergency credit line"
                ]
            elif action_window <= 4:
                actions = [
                    "Accelerate receivables collection",
                    "Defer discretionary spending",
                    "Review credit line availability"
                ]
            else:
                actions = [
                    "Plan cost optimization",
                    "Consider revenue acceleration",
                    "Review expense commitments"
                ]
        else:
            actions = ["No immediate action required"]

        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            rule_type=rule.rule_type,
            severity=severity,
            is_breached=is_breached,
            breach_week=breach_week,
            breach_date=breach_date,
            breach_amount=breach_amount,
            action_window_weeks=breach_week - 1 if breach_week else None,
            message=message,
            recommended_actions=actions,
        )

    # =========================================================================
    # PIPELINE STAGE 7: COMMIT SCENARIO
    # =========================================================================

    async def commit_scenario(
        self,
        definition: ScenarioDefinition,
        delta: ScenarioDelta,
    ) -> Dict[str, Any]:
        """
        Stage 7: Commit scenario deltas to canonical data.

        This is the only stage that modifies canonical data.

        V4 Implementation:
        - Uses ScenarioCommitService for schedule-based deltas
        - Falls back to legacy CashEvent-based approach for legacy deltas
        """
        # Check if we have schedule-based deltas (V4) or legacy event deltas
        has_schedule_deltas = (
            len(delta.created_schedules) > 0 or
            len(delta.updated_schedules) > 0 or
            len(delta.deleted_schedule_ids) > 0 or
            len(delta.created_agreements) > 0 or
            len(delta.deactivated_agreement_ids) > 0
        )

        if has_schedule_deltas:
            # V4: Use ScenarioCommitService for ObligationSchedule-based commits
            commit_service = ScenarioCommitService(self.db, definition.user_id)
            results = await commit_service.commit_scenario(definition, delta)

            # Update scenario status
            definition.status = ScenarioStatusEnum.CONFIRMED
            definition.confirmed_at = datetime.now()

            return results
        else:
            # Legacy: CashEvent-based commit
            try:
                # Apply created events
                for created in delta.created_events:
                    new_event = CashEvent(
                        id=created.event_id,
                        user_id=definition.user_id,
                        date=datetime.fromisoformat(created.event_data["date"]).date(),
                        amount=Decimal(str(created.event_data["amount"])),
                        direction=created.event_data["direction"],
                        event_type=created.event_data.get("event_type", "manual"),
                        category=created.event_data.get("category"),
                        confidence=created.event_data.get("confidence", "medium"),
                        confidence_reason=f"scenario_{definition.scenario_id}",
                        is_recurring=created.event_data.get("is_recurring", False),
                        recurrence_pattern=created.event_data.get("recurrence_pattern"),
                    )
                    self.db.add(new_event)

                # Apply updated events
                for updated in delta.updated_events:
                    result = await self.db.execute(
                        select(CashEvent).where(CashEvent.id == updated.original_event_id)
                    )
                    event = result.scalar_one_or_none()
                    if event:
                        for key, value in updated.event_data.items():
                            if key == "date":
                                event.date = datetime.fromisoformat(value).date()
                            elif key == "amount":
                                event.amount = Decimal(str(value))
                            elif hasattr(event, key):
                                setattr(event, key, value)

                # Apply deleted events
                for event_id in delta.deleted_event_ids:
                    result = await self.db.execute(
                        select(CashEvent).where(CashEvent.id == event_id)
                    )
                    event = result.scalar_one_or_none()
                    if event:
                        await self.db.delete(event)

                # Update scenario status
                definition.status = ScenarioStatusEnum.CONFIRMED
                definition.confirmed_at = datetime.now()

                await self.db.commit()
                return {
                    "events_created": len(delta.created_events),
                    "events_updated": len(delta.updated_events),
                    "events_deleted": len(delta.deleted_event_ids),
                }

            except Exception as e:
                await self.db.rollback()
                raise e

    # =========================================================================
    # PIPELINE STAGE 8: DISCARD SCENARIO
    # =========================================================================

    async def discard_scenario(
        self,
        definition: ScenarioDefinition,
    ) -> bool:
        """
        Stage 8: Discard scenario without changes.

        Base forecast remains unchanged.
        """
        definition.status = ScenarioStatusEnum.DISCARDED
        return True

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    async def _get_clients(self, user_id: str) -> List[Client]:
        """Get all clients for a user."""
        result = await self.db.execute(
            select(Client).where(Client.user_id == user_id)
        )
        return list(result.scalars().all())

    async def _get_expense_buckets(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> List[ExpenseBucket]:
        """Get expense buckets for a user."""
        query = select(ExpenseBucket).where(ExpenseBucket.user_id == user_id)
        if category:
            query = query.where(ExpenseBucket.category == category)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _apply_answers(
        self,
        definition: ScenarioDefinition,
        answers: Dict[str, Any]
    ) -> ScenarioDefinition:
        """Apply provided answers to the definition."""
        for key, value in answers.items():
            parts = key.split(".")
            if parts[0] == "scope":
                if parts[1] == "client_ids":
                    definition.scope.client_ids = [value] if isinstance(value, str) else value
                elif parts[1] == "bucket_ids":
                    definition.scope.bucket_ids = [value] if isinstance(value, str) else value
                elif parts[1] == "effective_date":
                    if isinstance(value, str):
                        definition.scope.effective_date = date.fromisoformat(value)
                    else:
                        definition.scope.effective_date = value
            elif parts[0] == "parameters":
                definition.parameters[parts[1]] = value
            elif parts[0] == "linked":
                # Store in parameters with linked_ prefix
                definition.parameters[f"linked_{parts[1]}"] = value

        definition.updated_at = datetime.now()
        return definition

    def _is_param_provided(self, definition: ScenarioDefinition, maps_to: str) -> bool:
        """Check if a parameter has been provided."""
        parts = maps_to.split(".")
        if parts[0] == "scope":
            scope_val = getattr(definition.scope, parts[1], None)
            return scope_val is not None and (not isinstance(scope_val, list) or len(scope_val) > 0)
        elif parts[0] == "parameters":
            return parts[1] in definition.parameters
        elif parts[0] == "linked":
            return f"linked_{parts[1]}" in definition.parameters
        return False

    def _get_param_value(self, definition: ScenarioDefinition, maps_to: str) -> Any:
        """Get the value of a parameter."""
        parts = maps_to.split(".")
        if parts[0] == "scope":
            return getattr(definition.scope, parts[1], None)
        elif parts[0] == "parameters":
            return definition.parameters.get(parts[1])
        elif parts[0] == "linked":
            return definition.parameters.get(f"linked_{parts[1]}")
        return None

    # =========================================================================
    # FULL PIPELINE EXECUTION
    # =========================================================================

    async def run_pipeline(
        self,
        definition: ScenarioDefinition,
        answers: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Run the full pipeline, stopping when prompts are needed.

        Returns a PipelineResult with current state and any pending prompts.
        """
        answers = answers or {}
        errors = []
        warnings = []

        try:
            # Stage 2: Collect scope and params
            if definition.current_stage in [PipelineStage.SCOPE, PipelineStage.PARAMS]:
                definition, prompts = await self.collect_scope_and_params(definition, answers)
                if prompts:
                    return PipelineResult(
                        scenario_id=definition.scenario_id,
                        scenario_definition=definition,
                        current_stage=definition.current_stage,
                        completed_stages=definition.completed_stages,
                        prompt_requests=prompts,
                    )

            # Stage 3: Linked prompts
            if definition.current_stage == PipelineStage.LINKED_PROMPTS:
                # Apply any provided answers first
                definition = self._apply_answers(definition, answers)
                definition, prompts = await self.generate_linked_prompts(definition)
                if prompts:
                    return PipelineResult(
                        scenario_id=definition.scenario_id,
                        scenario_definition=definition,
                        current_stage=definition.current_stage,
                        completed_stages=definition.completed_stages,
                        prompt_requests=prompts,
                    )

            # Stage 4: Generate delta
            if definition.current_stage == PipelineStage.CANONICAL_DELTAS:
                delta = await self.apply_scenario_to_canonical(definition)
            else:
                delta = None

            # Stage 5: Build layer and forecast
            base_summary = None
            scenario_summary = None
            delta_summary = None
            if definition.current_stage == PipelineStage.OVERLAY_FORECAST and delta:
                base_summary, scenario_summary, delta_summary = await self.build_scenario_layer(
                    definition, delta
                )

            # Stage 6: Run rules
            rule_results = []
            if definition.current_stage == PipelineStage.RULE_EVAL and scenario_summary:
                rule_results = await self.run_rules(definition, scenario_summary)

            return PipelineResult(
                scenario_id=definition.scenario_id,
                scenario_definition=definition,
                current_stage=definition.current_stage,
                completed_stages=definition.completed_stages,
                is_complete=definition.status == ScenarioStatusEnum.SIMULATED,
                prompt_requests=[],
                delta=delta,
                base_forecast_summary=base_summary,
                scenario_forecast_summary=scenario_summary,
                delta_summary=delta_summary,
                rule_results=rule_results,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            errors.append(str(e))
            return PipelineResult(
                scenario_id=definition.scenario_id,
                scenario_definition=definition,
                current_stage=definition.current_stage,
                completed_stages=definition.completed_stages,
                errors=errors,
            )
