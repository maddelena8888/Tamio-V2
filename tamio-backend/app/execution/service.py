"""
Execution Service - V4 Architecture

Handles the execution of approved actions.
V1: Prepares artifacts for manual execution
V2: Can auto-execute via integrations with automation rules
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.preparation.models import PreparedAction, ActionOption, ActionStatus, ActionType
from .models import (
    ExecutionRecord,
    ExecutionMethod,
    ExecutionResult,
    ExecutionAutomationRule,
    AutomationActionType,
)

logger = logging.getLogger(__name__)


# Mapping from ActionType to AutomationActionType
ACTION_TYPE_TO_AUTOMATION = {
    ActionType.INVOICE_FOLLOW_UP: AutomationActionType.INVOICE_FOLLOW_UP,
    ActionType.PAYMENT_REMINDER: AutomationActionType.INVOICE_FOLLOW_UP,
    ActionType.COLLECTION_ESCALATION: AutomationActionType.INVOICE_FOLLOW_UP,
    ActionType.PAYMENT_BATCH: AutomationActionType.PAYMENT_BATCH,
    ActionType.PAYMENT_PRIORITIZATION: AutomationActionType.PAYMENT_BATCH,
    ActionType.VENDOR_DELAY: AutomationActionType.VENDOR_DELAY,
    ActionType.STATUTORY_PAYMENT: AutomationActionType.STATUTORY_PAYMENT,
    ActionType.PAYROLL_CONTINGENCY: AutomationActionType.PAYROLL,
    ActionType.PAYROLL_CONFIRMATION: AutomationActionType.PAYROLL,
    ActionType.EXCESS_CASH_ALLOCATION: AutomationActionType.EXCESS_ALLOCATION,
}


@dataclass
class AutomationCheckResult:
    """Result of checking automation rules for an action."""
    can_auto_execute: bool
    reason: str
    rule_id: Optional[str] = None
    requires_approval: bool = True
    threshold_exceeded: bool = False
    excluded_by_tag: bool = False


class ExecutionService:
    """
    Manages action execution.

    V1 Flow (Manual):
    1. User approves action in Action Queue
    2. System provides execution artifacts (copy-paste ready)
    3. User executes externally (sends email, uploads to bank)
    4. User marks complete in Tamio
    5. System updates status and creates ExecutionRecord

    V2 Flow (Automated):
    1. User approves action
    2. System checks automation rules
    3. If auto-executable, executes via API
    4. Creates ExecutionRecord with result
    5. Notifies user of completion
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def approve_action(
        self,
        action_id: str,
        option_id: Optional[str] = None,
        edited_content: Optional[dict] = None
    ) -> PreparedAction:
        """
        Approve a prepared action.

        If option_id is provided, selects that option.
        If edited_content is provided, updates the option's prepared_content.
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.id == action_id)
            .where(PreparedAction.user_id == self.user_id)
        )
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError("Action not found")

        if action.status != ActionStatus.PENDING_APPROVAL:
            raise ValueError(f"Action is not pending approval (status: {action.status})")

        # Select option
        if option_id:
            action.selected_option_id = option_id

            # Update content if edited
            if edited_content:
                option_result = await self.db.execute(
                    select(ActionOption).where(ActionOption.id == option_id)
                )
                option = option_result.scalar_one_or_none()
                if option:
                    option.prepared_content = {**option.prepared_content, **edited_content}
                action.status = ActionStatus.EDITED
            else:
                action.status = ActionStatus.APPROVED
        else:
            action.status = ActionStatus.APPROVED

        action.approved_at = datetime.utcnow()
        return action

    async def mark_executed(
        self,
        action_id: str,
        external_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> ExecutionRecord:
        """
        Mark an approved action as executed (V1 manual flow).

        User has copied content and executed externally.
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.id == action_id)
            .where(PreparedAction.user_id == self.user_id)
        )
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError("Action not found")

        if action.status not in [ActionStatus.APPROVED, ActionStatus.EDITED]:
            raise ValueError(f"Action must be approved before execution (status: {action.status})")

        # Update action status
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.utcnow()

        # Get the executed content
        executed_content = {}
        if action.selected_option_id:
            option_result = await self.db.execute(
                select(ActionOption).where(ActionOption.id == action.selected_option_id)
            )
            option = option_result.scalar_one_or_none()
            if option:
                executed_content = option.prepared_content

        # Create execution record
        record = ExecutionRecord(
            user_id=self.user_id,
            action_id=action_id,
            option_id=action.selected_option_id,
            method=ExecutionMethod.MANUAL,
            result=ExecutionResult.SUCCESS,
            executed_content=executed_content,
            external_reference=external_reference,
            notes=notes,
            confirmed_at=datetime.utcnow(),
        )

        self.db.add(record)

        # Resolve linked alert if exists
        if action.alert:
            from app.detection.models import AlertStatus
            action.alert.status = AlertStatus.RESOLVED
            action.alert.resolved_at = datetime.utcnow()

        return record

    async def skip_action(
        self,
        action_id: str,
        reason: Optional[str] = None
    ) -> PreparedAction:
        """
        Skip an action (defer decision).
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.id == action_id)
            .where(PreparedAction.user_id == self.user_id)
        )
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError("Action not found")

        action.status = ActionStatus.SKIPPED
        action.user_notes = reason
        return action

    async def override_action(
        self,
        action_id: str,
        reason: Optional[str] = None
    ) -> PreparedAction:
        """
        Override an action (reject recommendation, handle manually).
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.id == action_id)
            .where(PreparedAction.user_id == self.user_id)
        )
        action = result.scalar_one_or_none()

        if not action:
            raise ValueError("Action not found")

        action.status = ActionStatus.OVERRIDDEN
        action.user_notes = reason
        return action

    async def get_execution_queue(self) -> list[PreparedAction]:
        """
        Get all approved actions waiting for execution.
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.user_id == self.user_id)
            .where(PreparedAction.status.in_([ActionStatus.APPROVED, ActionStatus.EDITED]))
        )
        return result.scalars().all()

    async def get_execution_artifacts(self, action_id: str) -> dict:
        """
        Get ready-to-use execution artifacts for an action.

        Returns content formatted for easy execution:
        - Emails: subject, body, recipient (copy-paste ready)
        - Payments: CSV download, bank instructions
        - Calls: talking points
        """
        result = await self.db.execute(
            select(PreparedAction)
            .where(PreparedAction.id == action_id)
            .where(PreparedAction.user_id == self.user_id)
        )
        action = result.scalar_one_or_none()

        if not action or not action.selected_option_id:
            return {}

        option_result = await self.db.execute(
            select(ActionOption).where(ActionOption.id == action.selected_option_id)
        )
        option = option_result.scalar_one_or_none()

        if not option:
            return {}

        content = option.prepared_content

        # Format based on action type
        artifacts = {
            "action_type": action.action_type.value,
            "raw_content": content,
        }

        # Add formatted versions for common types
        if "email_subject" in content:
            artifacts["email"] = {
                "subject": content["email_subject"],
                "body": content["email_body"],
                "recipient": content.get("recipient", ""),
                "copy_button": True,
            }

        if "payments" in content:
            artifacts["payment_batch"] = {
                "total": content.get("total", 0),
                "count": len(content.get("payments", [])),
                "csv_available": True,
            }

        if "talking_points" in content:
            artifacts["call"] = {
                "talking_points": content["talking_points"],
            }

        return artifacts

    async def get_recent_activity(self, limit: int = 20) -> list[ExecutionRecord]:
        """
        Get recent execution activity for the activity log.
        """
        result = await self.db.execute(
            select(ExecutionRecord)
            .where(ExecutionRecord.user_id == self.user_id)
            .order_by(ExecutionRecord.executed_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    # =========================================================================
    # V2 Automation Rules
    # =========================================================================

    async def get_automation_rule(
        self,
        action_type: ActionType,
    ) -> Optional[ExecutionAutomationRule]:
        """
        Get the automation rule for a specific action type.
        """
        automation_type = ACTION_TYPE_TO_AUTOMATION.get(action_type)
        if not automation_type:
            return None

        result = await self.db.execute(
            select(ExecutionAutomationRule)
            .where(
                and_(
                    ExecutionAutomationRule.user_id == self.user_id,
                    ExecutionAutomationRule.action_type == automation_type,
                )
            )
        )
        return result.scalar_one_or_none()

    async def check_automation_eligibility(
        self,
        action: PreparedAction,
    ) -> AutomationCheckResult:
        """
        Check if an action can be auto-executed based on automation rules.

        Checks:
        1. Action type has automation rule
        2. Auto-execute is enabled
        3. Amount is within threshold (if set)
        4. Entity is not in excluded tags
        5. Entity is in included tags (if set)
        6. Action is not locked (payroll)
        """
        # Get the automation type for this action
        automation_type = ACTION_TYPE_TO_AUTOMATION.get(action.action_type)

        if not automation_type:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason=f"No automation mapping for action type: {action.action_type.value}",
            )

        # Payroll is always locked - never auto-execute
        if automation_type == AutomationActionType.PAYROLL:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason="Payroll actions require manual execution",
                requires_approval=True,
            )

        # Get the user's automation rule for this type
        rule = await self.get_automation_rule(action.action_type)

        if not rule:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason=f"No automation rule configured for {automation_type.value}",
            )

        # Check if auto-execute is enabled
        if not rule.auto_execute:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason="Automation is disabled for this action type",
                rule_id=rule.id,
                requires_approval=rule.require_approval,
            )

        # Check if rule is locked
        if rule.is_locked:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason="This action type is locked for automation",
                rule_id=rule.id,
            )

        # Get the action's cash impact for threshold check
        action_amount = await self._get_action_amount(action)

        # Check threshold
        if rule.threshold_amount is not None and action_amount > rule.threshold_amount:
            return AutomationCheckResult(
                can_auto_execute=False,
                reason=f"Amount ${action_amount:,.0f} exceeds threshold ${rule.threshold_amount:,.0f}",
                rule_id=rule.id,
                threshold_exceeded=True,
                requires_approval=rule.require_approval,
            )

        # Get entity tags (client/vendor tags)
        entity_tags = await self._get_entity_tags(action)

        # Check excluded tags
        if rule.excluded_tags:
            for tag in rule.excluded_tags:
                if tag in entity_tags:
                    return AutomationCheckResult(
                        can_auto_execute=False,
                        reason=f"Entity has excluded tag: {tag}",
                        rule_id=rule.id,
                        excluded_by_tag=True,
                        requires_approval=rule.require_approval,
                    )

        # Check included tags (if set, entity must have at least one)
        if rule.included_tags:
            has_included_tag = any(tag in entity_tags for tag in rule.included_tags)
            if not has_included_tag:
                return AutomationCheckResult(
                    can_auto_execute=False,
                    reason=f"Entity does not have any required tags: {rule.included_tags}",
                    rule_id=rule.id,
                    requires_approval=rule.require_approval,
                )

        # All checks passed - can auto-execute
        return AutomationCheckResult(
            can_auto_execute=True,
            reason="All automation conditions met",
            rule_id=rule.id,
            requires_approval=rule.require_approval,
        )

    async def _get_action_amount(self, action: PreparedAction) -> float:
        """Get the cash impact amount from an action."""
        if not action.options:
            # Load options if not already loaded
            result = await self.db.execute(
                select(ActionOption)
                .where(ActionOption.action_id == action.id)
                .where(ActionOption.is_recommended == True)
            )
            option = result.scalar_one_or_none()
            if option and option.cash_impact:
                return abs(option.cash_impact)

        # Check from loaded options
        for option in action.options if action.options else []:
            if option.cash_impact:
                return abs(option.cash_impact)

        return 0.0

    async def _get_entity_tags(self, action: PreparedAction) -> List[str]:
        """Get tags for the entity (client/vendor) associated with the action."""
        tags = []

        # Get the prepared content to extract entity info
        if action.selected_option_id:
            result = await self.db.execute(
                select(ActionOption)
                .where(ActionOption.id == action.selected_option_id)
            )
            option = result.scalar_one_or_none()
        else:
            # Get the recommended option
            result = await self.db.execute(
                select(ActionOption)
                .where(ActionOption.action_id == action.id)
                .where(ActionOption.is_recommended == True)
            )
            option = result.scalar_one_or_none()

        if not option:
            return tags

        content = option.prepared_content or {}

        # Check for relationship type (client)
        if "relationship_type" in content:
            tags.append(content["relationship_type"])

        # Check for vendor flexibility
        if "vendor_flexibility" in content:
            tags.append(content["vendor_flexibility"])

        # Check for entity tags
        if "tags" in content:
            tags.extend(content["tags"])

        return tags

    async def approve_and_check_automation(
        self,
        action_id: str,
        option_id: Optional[str] = None,
        edited_content: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Approve an action and check if it can be auto-executed.

        Returns both the approved action and automation check result.
        If auto-executable, optionally triggers execution.
        """
        # First approve the action
        action = await self.approve_action(action_id, option_id, edited_content)

        # Check automation eligibility
        automation_check = await self.check_automation_eligibility(action)

        return {
            "action": action,
            "automation": {
                "can_auto_execute": automation_check.can_auto_execute,
                "reason": automation_check.reason,
                "requires_approval": automation_check.requires_approval,
                "threshold_exceeded": automation_check.threshold_exceeded,
                "excluded_by_tag": automation_check.excluded_by_tag,
            },
        }

    async def auto_execute(
        self,
        action: PreparedAction,
    ) -> ExecutionRecord:
        """
        Auto-execute an action (V2 flow).

        This is called after approval when automation check passes.
        Executes via appropriate integration:
        - Email actions: Send via Resend/SMTP
        - Payment actions: Prepare batch file (actual submission requires bank integration)
        """
        if action.status not in [ActionStatus.APPROVED, ActionStatus.EDITED]:
            raise ValueError(f"Action must be approved for auto-execution (status: {action.status})")

        # Verify automation eligibility
        automation_check = await self.check_automation_eligibility(action)
        if not automation_check.can_auto_execute:
            raise ValueError(f"Action cannot be auto-executed: {automation_check.reason}")

        # Get the executed content
        executed_content = {}
        option_id = action.selected_option_id

        if not option_id:
            # Get the recommended option
            result = await self.db.execute(
                select(ActionOption)
                .where(ActionOption.action_id == action.id)
                .where(ActionOption.is_recommended == True)
            )
            option = result.scalar_one_or_none()
            if option:
                option_id = option.id
                executed_content = option.prepared_content or {}
        else:
            result = await self.db.execute(
                select(ActionOption).where(ActionOption.id == option_id)
            )
            option = result.scalar_one_or_none()
            if option:
                executed_content = option.prepared_content or {}

        # Execute based on action type
        execution_result = ExecutionResult.SUCCESS
        external_system = "tamio"
        external_reference = None
        notes = "Auto-executed based on automation rules"

        # Email actions - actually send the email
        if action.action_type in [
            ActionType.INVOICE_FOLLOW_UP,
            ActionType.PAYMENT_REMINDER,
            ActionType.COLLECTION_ESCALATION,
            ActionType.VENDOR_DELAY,
        ]:
            email_result = await self._execute_email_action(executed_content)
            if email_result["success"]:
                external_system = email_result.get("provider", "resend")
                external_reference = email_result.get("message_id")
                notes = f"Email sent to {email_result.get('recipient', 'recipient')}"
            else:
                execution_result = ExecutionResult.FAILED
                notes = f"Email send failed: {email_result.get('error', 'Unknown error')}"

        # Update action status
        action.status = ActionStatus.EXECUTED
        action.executed_at = datetime.utcnow()
        if option_id:
            action.selected_option_id = option_id

        # Create execution record
        record = ExecutionRecord(
            user_id=self.user_id,
            action_id=action.id,
            option_id=option_id,
            method=ExecutionMethod.AUTOMATED,
            result=execution_result,
            executed_content=executed_content,
            external_system=external_system,
            external_reference=external_reference,
            notes=notes,
            confirmed_at=datetime.utcnow() if execution_result == ExecutionResult.SUCCESS else None,
        )

        self.db.add(record)

        # Resolve linked alert if exists and execution succeeded
        if action.alert and execution_result == ExecutionResult.SUCCESS:
            from app.detection.models import AlertStatus
            action.alert.status = AlertStatus.RESOLVED
            action.alert.resolved_at = datetime.utcnow()

        logger.info(
            f"Auto-executed action {action.id} (type: {action.action_type.value}, result: {execution_result.value})"
        )

        return record

    async def _execute_email_action(self, content: dict) -> dict:
        """
        Execute an email action by actually sending the email.

        Expects content with:
        - email_subject: Subject line
        - email_body: Body text (HTML or plain)
        - recipient: Email address

        Returns:
        - success: bool
        - message_id: str (if successful)
        - provider: str
        - error: str (if failed)
        """
        from app.config import settings
        from app.notifications.email_provider import (
            get_email_provider,
            EmailMessage,
        )

        # Validate required fields
        recipient = content.get("recipient") or content.get("email_to")
        subject = content.get("email_subject")
        body = content.get("email_body") or content.get("message")

        if not recipient:
            return {"success": False, "error": "No recipient email address"}
        if not subject:
            return {"success": False, "error": "No email subject"}
        if not body:
            return {"success": False, "error": "No email body"}

        # Get email provider
        provider = get_email_provider(
            resend_api_key=getattr(settings, "RESEND_API_KEY", None),
            console_mode=settings.APP_ENV == "development",
        )

        # Determine if body is HTML
        is_html = body.strip().startswith("<") or "<br" in body or "<p>" in body

        # Create message
        message = EmailMessage(
            to=recipient,
            subject=subject,
            html_body=body if is_html else f"<p>{body}</p>",
            plain_text_body=body if not is_html else body.replace("<br>", "\n").replace("</p>", "\n"),
        )

        # Send
        try:
            result = await provider.send(message)

            if result.success:
                logger.info(f"Auto-executed email sent to {recipient}")
                return {
                    "success": True,
                    "message_id": result.message_id,
                    "provider": "resend" if settings.RESEND_API_KEY else "console",
                    "recipient": recipient,
                }
            else:
                logger.error(f"Auto-executed email failed: {result.error}")
                return {
                    "success": False,
                    "error": result.error,
                }
        except Exception as e:
            logger.exception("Failed to send auto-executed email")
            return {
                "success": False,
                "error": str(e),
            }

    # =========================================================================
    # Automation Rule Management
    # =========================================================================

    async def get_all_automation_rules(self) -> List[ExecutionAutomationRule]:
        """Get all automation rules for the user."""
        result = await self.db.execute(
            select(ExecutionAutomationRule)
            .where(ExecutionAutomationRule.user_id == self.user_id)
        )
        return list(result.scalars().all())

    async def create_or_update_automation_rule(
        self,
        action_type: AutomationActionType,
        auto_execute: bool = False,
        threshold_amount: Optional[float] = None,
        threshold_currency: str = "USD",
        excluded_tags: Optional[List[str]] = None,
        included_tags: Optional[List[str]] = None,
        require_approval: bool = True,
    ) -> ExecutionAutomationRule:
        """
        Create or update an automation rule.

        Cannot modify locked rules (payroll).
        """
        # Check for existing rule
        result = await self.db.execute(
            select(ExecutionAutomationRule)
            .where(
                and_(
                    ExecutionAutomationRule.user_id == self.user_id,
                    ExecutionAutomationRule.action_type == action_type,
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.is_locked:
                raise ValueError(f"Cannot modify locked automation rule for {action_type.value}")

            # Update existing
            existing.auto_execute = auto_execute
            existing.threshold_amount = threshold_amount
            existing.threshold_currency = threshold_currency
            existing.excluded_tags = excluded_tags or []
            existing.included_tags = included_tags
            existing.require_approval = require_approval
            existing.updated_at = datetime.utcnow()
            return existing
        else:
            # Create new
            rule = ExecutionAutomationRule(
                user_id=self.user_id,
                action_type=action_type,
                auto_execute=auto_execute,
                threshold_amount=threshold_amount,
                threshold_currency=threshold_currency,
                excluded_tags=excluded_tags or [],
                included_tags=included_tags,
                require_approval=require_approval,
                is_locked=action_type == AutomationActionType.PAYROLL,
            )
            self.db.add(rule)
            return rule

    async def initialize_default_automation_rules(self) -> List[ExecutionAutomationRule]:
        """
        Initialize default automation rules for a new user.

        Default rules based on V4 brief:
        - Invoice Follow-ups: Disabled by default, exclude strategic clients
        - Payment Batches: Disabled, threshold $10,000
        - Vendor Delays: Disabled, only flexible vendors
        - Tax/Statutory: Always manual
        - Payroll: LOCKED - always manual
        - Excess Allocation: Disabled
        """
        rules = []

        # Invoice Follow-ups
        rules.append(await self.create_or_update_automation_rule(
            action_type=AutomationActionType.INVOICE_FOLLOW_UP,
            auto_execute=False,
            excluded_tags=["strategic"],
            require_approval=True,
        ))

        # Payment Batches
        rules.append(await self.create_or_update_automation_rule(
            action_type=AutomationActionType.PAYMENT_BATCH,
            auto_execute=False,
            threshold_amount=10000.00,
            require_approval=True,
        ))

        # Vendor Delays
        rules.append(await self.create_or_update_automation_rule(
            action_type=AutomationActionType.VENDOR_DELAY,
            auto_execute=False,
            included_tags=["flexible"],
            require_approval=True,
        ))

        # Tax/Statutory
        rules.append(await self.create_or_update_automation_rule(
            action_type=AutomationActionType.STATUTORY_PAYMENT,
            auto_execute=False,
            require_approval=True,
        ))

        # Payroll - LOCKED
        payroll_rule = ExecutionAutomationRule(
            user_id=self.user_id,
            action_type=AutomationActionType.PAYROLL,
            auto_execute=False,
            require_approval=True,
            is_locked=True,
        )
        self.db.add(payroll_rule)
        rules.append(payroll_rule)

        # Excess Allocation
        rules.append(await self.create_or_update_automation_rule(
            action_type=AutomationActionType.EXCESS_ALLOCATION,
            auto_execute=False,
            require_approval=True,
        ))

        return rules
