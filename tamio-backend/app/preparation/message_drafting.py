"""
Message Drafting - V4 Architecture

Template-based message generation for prepared actions.
Designed for easy OpenAI integration later.

Message types:
- Collection emails (soft, professional, firm)
- Vendor delay requests
- Payment reminders
- Escalation notices
"""

from typing import Dict, Any, Optional
from datetime import datetime, date, timedelta


# =============================================================================
# Collection Messages
# =============================================================================

def draft_collection_email(
    client_name: str,
    invoice_number: str,
    amount: float,
    due_date: str,
    days_overdue: int,
    tone: str = "professional",
    relationship_type: str = "transactional",
    revenue_percent: float = 0,
    custom_context: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Draft a collection email based on tone and client relationship.

    Args:
        client_name: Name of the client
        invoice_number: Invoice reference number
        amount: Amount owed
        due_date: Original due date string
        days_overdue: Days past due
        tone: "soft", "professional", or "firm"
        relationship_type: "strategic", "managed", or "transactional"
        revenue_percent: Client's share of total revenue
        custom_context: Additional context for customization

    Returns:
        Dict with "subject" and "body" keys
    """
    # Adjust tone for strategic clients
    if relationship_type == "strategic" and tone == "firm":
        tone = "professional"
    if revenue_percent >= 15 and tone == "firm":
        tone = "professional"

    templates = {
        "soft": {
            "subject": f"Quick follow-up on Invoice #{invoice_number}",
            "body": f"""Hi {client_name},

I hope this message finds you well! I wanted to quickly follow up on Invoice #{invoice_number} for ${amount:,.2f}, which was due on {due_date}.

I understand things can get busy - could you let me know the status of this payment when you get a chance? If you need me to resend the invoice or if there's anything I can help with, just let me know.

Thank you so much!

Best regards""",
        },
        "professional": {
            "subject": f"Following up on Invoice #{invoice_number}",
            "body": f"""Hi {client_name},

I'm following up on Invoice #{invoice_number} for ${amount:,.2f}, which is now {days_overdue} days past the due date of {due_date}.

Could you please provide an update on when we can expect payment? If there are any questions about the invoice or any issues I should be aware of, please don't hesitate to let me know.

Thank you for your attention to this matter.

Best regards""",
        },
        "firm": {
            "subject": f"Action Required: Invoice #{invoice_number} is {days_overdue} days overdue",
            "body": f"""Hi {client_name},

Invoice #{invoice_number} for ${amount:,.2f} is now {days_overdue} days overdue (original due date: {due_date}).

We need to resolve this payment as soon as possible. Please process this payment immediately or contact me to discuss if there are any issues preventing payment.

If you have already sent payment, please disregard this message and accept our thanks.

Best regards""",
        },
    }

    template = templates.get(tone, templates["professional"])
    return {
        "subject": template["subject"],
        "body": template["body"],
        "tone": tone,
        "adjusted_for_relationship": tone != tone,  # Flag if tone was adjusted
    }


def draft_escalation_email(
    client_name: str,
    invoice_number: str,
    amount: float,
    days_overdue: int,
    previous_attempts: int = 2
) -> Dict[str, str]:
    """
    Draft a formal escalation/demand letter.

    This is used when softer approaches have failed.
    """
    return {
        "subject": f"Urgent: Payment Required - Invoice #{invoice_number}",
        "body": f"""Dear {client_name},

This is a formal notice regarding Invoice #{invoice_number} for ${amount:,.2f}, which is now {days_overdue} days past due.

Despite {previous_attempts} previous reminder(s), we have not received payment or communication regarding this outstanding balance.

We request immediate payment within 7 days of this notice to avoid further action. Please remit payment to our standard payment details.

If there are extenuating circumstances or disputes regarding this invoice, please contact us immediately so we can work together to resolve them.

If you have already made this payment, please disregard this message and accept our apologies.

Regards""",
        "tone": "formal",
        "escalation_level": "demand_letter",
    }


# =============================================================================
# Vendor Messages
# =============================================================================

def draft_vendor_delay_message(
    vendor_name: str,
    original_date: str,
    new_date: str,
    amount: float,
    reason: str = "cash_flow",
    relationship_quality: str = "good"
) -> Dict[str, str]:
    """
    Draft a payment delay request to a vendor.

    Args:
        vendor_name: Name of the vendor
        original_date: Originally scheduled payment date
        new_date: Requested new payment date
        amount: Payment amount
        reason: Internal reason (not shared with vendor)
        relationship_quality: "good", "neutral", or "strained"
    """
    # More apologetic if relationship is strained
    if relationship_quality == "strained":
        apology = "I apologize for any inconvenience this may cause, and I want to assure you this is a temporary timing adjustment."
        closing = "Thank you for your patience and understanding. We truly value our partnership."
    elif relationship_quality == "good":
        apology = "I hope this timing works for you."
        closing = "Thanks so much for your flexibility. We really appreciate it."
    else:
        apology = "I appreciate your understanding on this."
        closing = "Thank you for your cooperation."

    return {
        "subject": f"Payment Timing Request - ${amount:,.2f}",
        "body": f"""Hi {vendor_name},

I wanted to reach out regarding our upcoming payment of ${amount:,.2f} scheduled for {original_date}.

Would it be possible to process this payment on {new_date} instead? {apology}

The full amount will be paid as scheduled on the new date.

{closing}

Best regards""",
        "tone": "collaborative",
        "internal_reason": reason,
    }


def draft_vendor_payment_confirmation(
    vendor_name: str,
    amount: float,
    payment_date: str,
    invoice_reference: Optional[str] = None
) -> Dict[str, str]:
    """
    Draft a payment confirmation message to vendor.
    """
    ref_text = f" for Invoice #{invoice_reference}" if invoice_reference else ""

    return {
        "subject": f"Payment Confirmation - ${amount:,.2f}",
        "body": f"""Hi {vendor_name},

This is to confirm that payment of ${amount:,.2f}{ref_text} has been scheduled for {payment_date}.

Please let me know if you need any additional information.

Best regards""",
        "tone": "informational",
    }


# =============================================================================
# Payment Reminder Messages
# =============================================================================

def draft_early_payment_request(
    client_name: str,
    invoice_number: str,
    amount: float,
    original_due_date: str,
    requested_date: str,
    relationship_type: str = "transactional"
) -> Dict[str, str]:
    """
    Draft a request for early payment from a client.

    Used when cash flow needs acceleration.
    """
    if relationship_type == "strategic":
        approach = "I wanted to reach out with a small request"
        closing = "No pressure at all if this doesn't work with your payment schedule - I just thought I'd ask."
    else:
        approach = "I have a quick favor to ask"
        closing = "If this is possible, it would be greatly appreciated."

    return {
        "subject": f"Early Payment Request - Invoice #{invoice_number}",
        "body": f"""Hi {client_name},

{approach}. Would it be possible to process payment on Invoice #{invoice_number} for ${amount:,.2f} a bit earlier than the due date of {original_due_date}?

If you could process this by {requested_date}, that would be incredibly helpful for our cash flow planning.

{closing}

Thank you!

Best regards""",
        "tone": "soft",
        "request_type": "early_payment",
    }


# =============================================================================
# Internal Messages / Talking Points
# =============================================================================

def generate_call_talking_points(
    entity_type: str,
    entity_name: str,
    context: Dict[str, Any]
) -> list[str]:
    """
    Generate talking points for a phone call.

    Args:
        entity_type: "client" or "vendor"
        entity_name: Name of the entity
        context: Relevant context data
    """
    points = []

    if entity_type == "client":
        invoice_number = context.get("invoice_number", "pending")
        amount = context.get("amount", 0)
        days_overdue = context.get("days_overdue", 0)

        points = [
            f"Reference Invoice #{invoice_number}",
            f"Amount outstanding: ${amount:,.2f}",
            f"Currently {days_overdue} days past due",
            "Ask about any issues or disputes with the invoice",
            "Confirm expected payment date",
            "Offer to resend invoice if needed",
            "Ask if they need different payment details",
        ]

        if context.get("relationship_type") == "strategic":
            points.append("Express appreciation for the partnership")

    elif entity_type == "vendor":
        amount = context.get("amount", 0)
        original_date = context.get("original_date", "")
        new_date = context.get("new_date", "")

        points = [
            f"Payment amount: ${amount:,.2f}",
            f"Original date: {original_date}",
            f"Requested new date: {new_date}",
            "Emphasize this is a one-time timing adjustment",
            "Confirm payment will be made in full",
            "Ask if this timing works for their accounting",
            "Express appreciation for flexibility",
        ]

    return points


def generate_action_summary(
    action_type: str,
    context: Dict[str, Any]
) -> str:
    """
    Generate a human-readable summary of a prepared action.
    """
    summaries = {
        "INVOICE_FOLLOW_UP": lambda c: f"Follow up on ${c.get('amount', 0):,.0f} invoice from {c.get('client_name', 'client')} ({c.get('days_overdue', 0)} days overdue)",
        "PAYMENT_REMINDER": lambda c: f"Send payment reminder for ${c.get('amount', 0):,.0f}",
        "COLLECTION_ESCALATION": lambda c: f"Escalate collection on ${c.get('amount', 0):,.0f} from {c.get('client_name', 'client')}",
        "VENDOR_DELAY": lambda c: f"Request payment delay for ${c.get('amount', 0):,.0f} to {c.get('vendor_name', 'vendor')}",
        "PAYMENT_BATCH": lambda c: f"Process payment batch of ${c.get('total_amount', 0):,.0f}",
        "PAYMENT_PRIORITIZATION": lambda c: f"Resequence {c.get('payment_count', 0)} payments totaling ${c.get('total_amount', 0):,.0f}",
        "PAYROLL_CONTINGENCY": lambda c: f"Address ${c.get('shortfall', 0):,.0f} shortfall before ${c.get('payroll_amount', 0):,.0f} payroll",
        "PAYROLL_CONFIRMATION": lambda c: f"Confirm ${c.get('payroll_amount', 0):,.0f} payroll for {c.get('payroll_date', 'upcoming')}",
        "CREDIT_LINE_DRAW": lambda c: f"Draw ${c.get('amount', 0):,.0f} from credit line",
        "STATUTORY_PAYMENT": lambda c: f"Process statutory payment of ${c.get('amount', 0):,.0f} due {c.get('due_date', 'soon')}",
    }

    generator = summaries.get(action_type, lambda c: f"Action: {action_type}")
    return generator(context)


# =============================================================================
# OpenAI Integration for Message Enhancement
# =============================================================================

import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Enhancement type prompts
ENHANCEMENT_PROMPTS = {
    "personalize": """You are a professional business communications expert.
Your task is to enhance the provided email template by adding personal touches based on the relationship context.
Keep the core message and tone intact, but make it feel more human and relationship-aware.
Do NOT change the key facts (amounts, dates, invoice numbers).
Return ONLY the enhanced email body, no additional commentary.""",

    "tone_adjust": """You are a professional business communications expert.
Your task is to adjust the tone of the provided email based on the context.
The current tone is: {current_tone}. Adjust to feel more: {target_tone}.
Keep the core message and all facts intact.
Return ONLY the enhanced email body, no additional commentary.""",

    "expand": """You are a professional business communications expert.
Your task is to expand the provided email with more context and detail.
Add relevant information that would be helpful for the recipient.
Keep the tone and key facts intact.
Return ONLY the enhanced email body, no additional commentary.""",

    "summarize": """You are a professional business communications expert.
Your task is to condense the provided email while keeping all essential information.
Make it shorter and more direct without losing important details.
Return ONLY the enhanced email body, no additional commentary.""",

    "soften": """You are a professional business communications expert.
Your task is to make the provided email gentler and more empathetic.
Add phrases that acknowledge the recipient's situation.
Keep all facts intact.
Return ONLY the enhanced email body, no additional commentary.""",

    "firm_up": """You are a professional business communications expert.
Your task is to make the provided email more direct and action-oriented.
Add clear deadlines and consequences where appropriate.
Keep the professional tone and all facts intact.
Return ONLY the enhanced email body, no additional commentary.""",
}


async def enhance_with_ai(
    template_output: Dict[str, str],
    context: Dict[str, Any],
    enhancement_type: str = "personalize"
) -> Dict[str, str]:
    """
    Enhance message content using OpenAI.

    Args:
        template_output: Dict with "subject" and "body" from template
        context: Additional context about the relationship and situation
        enhancement_type: Type of enhancement to apply:
            - "personalize": Add personal touches based on relationship
            - "tone_adjust": Fine-tune tone for specific situation
            - "expand": Add more detail/context
            - "summarize": Condense for brevity
            - "soften": Make more gentle/empathetic
            - "firm_up": Make more direct/action-oriented

    Returns:
        Enhanced template_output with "ai_enhanced": True flag
    """
    from app.config import settings

    # If no API key configured, return template unchanged
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured, skipping AI enhancement")
        return {**template_output, "ai_enhanced": False}

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Get the appropriate system prompt
        system_prompt = ENHANCEMENT_PROMPTS.get(
            enhancement_type,
            ENHANCEMENT_PROMPTS["personalize"]
        )

        # Format system prompt with context if needed
        if enhancement_type == "tone_adjust":
            system_prompt = system_prompt.format(
                current_tone=template_output.get("tone", "professional"),
                target_tone=context.get("target_tone", "warmer"),
            )

        # Build context message for the AI
        context_str = _build_context_string(context)

        # Prepare the user message
        user_message = f"""
CONTEXT:
{context_str}

CURRENT EMAIL:
Subject: {template_output.get('subject', '')}

Body:
{template_output.get('body', '')}

Please enhance this email according to your instructions.
"""

        # Call OpenAI
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL_FAST,  # Use faster model for message enhancement
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.7,  # Some creativity but not too much
        )

        enhanced_body = response.choices[0].message.content.strip()

        # Return enhanced output
        return {
            **template_output,
            "body": enhanced_body,
            "ai_enhanced": True,
            "enhancement_type": enhancement_type,
            "original_body": template_output.get("body", ""),
        }

    except Exception as e:
        logger.error(f"AI enhancement failed: {e}")
        # Return original template on error
        return {**template_output, "ai_enhanced": False, "ai_error": str(e)}


def _build_context_string(context: Dict[str, Any]) -> str:
    """Build a context string for the AI from context dict."""
    parts = []

    # Relationship info
    if "relationship_type" in context:
        parts.append(f"Client relationship: {context['relationship_type']}")
    if "revenue_percent" in context:
        parts.append(f"Client represents {context['revenue_percent']:.1f}% of revenue")
    if "payment_behavior" in context:
        parts.append(f"Payment history: {context['payment_behavior']}")

    # Invoice/payment context
    if "days_overdue" in context:
        parts.append(f"Invoice is {context['days_overdue']} days overdue")
    if "previous_attempts" in context:
        parts.append(f"Previous follow-up attempts: {context['previous_attempts']}")

    # Special circumstances
    if "special_notes" in context:
        parts.append(f"Special notes: {context['special_notes']}")
    if "churn_risk" in context:
        parts.append(f"Churn risk level: {context['churn_risk']}")

    return "\n".join(parts) if parts else "No additional context provided."


async def generate_ai_message(
    message_type: str,
    context: Dict[str, Any],
    tone: str = "professional",
) -> Dict[str, str]:
    """
    Generate a complete message using AI (not template-based).

    Use this for custom messages that don't fit templates.

    Args:
        message_type: Type of message to generate
        context: All relevant context for message generation
        tone: Desired tone (soft, professional, firm, formal)

    Returns:
        Dict with "subject", "body", and metadata
    """
    from app.config import settings

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not configured")
        return {
            "subject": f"{message_type.replace('_', ' ').title()}",
            "body": "Please configure OpenAI API key for AI-generated messages.",
            "ai_generated": False,
        }

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = f"""You are a professional business communications expert.
Generate a {tone} business email based on the following context.
The email should be concise, professional, and actionable.
Return your response in this exact format:
SUBJECT: [subject line here]
BODY:
[email body here]"""

        context_str = _build_context_string(context)
        user_message = f"""
MESSAGE TYPE: {message_type}
TONE: {tone}

CONTEXT:
{context_str}

Generate the email.
"""

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL_FAST,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.7,
        )

        content = response.choices[0].message.content.strip()

        # Parse response
        subject = ""
        body = content

        if "SUBJECT:" in content and "BODY:" in content:
            parts = content.split("BODY:", 1)
            subject_part = parts[0].replace("SUBJECT:", "").strip()
            body = parts[1].strip() if len(parts) > 1 else ""
            subject = subject_part

        return {
            "subject": subject,
            "body": body,
            "tone": tone,
            "ai_generated": True,
            "message_type": message_type,
        }

    except Exception as e:
        logger.error(f"AI message generation failed: {e}")
        return {
            "subject": f"{message_type.replace('_', ' ').title()}",
            "body": f"AI generation failed: {e}",
            "ai_generated": False,
            "ai_error": str(e),
        }


async def suggest_tone(
    client_context: Dict[str, Any],
    situation: str,
) -> Dict[str, Any]:
    """
    Use AI to suggest the best tone for a communication.

    Args:
        client_context: Client relationship data
        situation: Description of the current situation

    Returns:
        Dict with recommended tone and reasoning
    """
    from app.config import settings

    if not settings.OPENAI_API_KEY:
        # Fallback to rule-based suggestion
        return _rule_based_tone_suggestion(client_context, situation)

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = """You are a business communications strategist.
Based on the client context and situation, recommend the best communication tone.
Return your response in this exact format:
TONE: [soft/professional/firm/formal]
REASONING: [brief explanation why]"""

        context_str = _build_context_string(client_context)
        user_message = f"""
CLIENT CONTEXT:
{context_str}

SITUATION:
{situation}

What tone should we use?
"""

        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL_FAST,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=200,
            temperature=0.3,  # More deterministic for recommendations
        )

        content = response.choices[0].message.content.strip()

        # Parse response
        tone = "professional"
        reasoning = content

        if "TONE:" in content:
            parts = content.split("REASONING:", 1)
            tone_part = parts[0].replace("TONE:", "").strip().lower()
            if tone_part in ["soft", "professional", "firm", "formal"]:
                tone = tone_part
            reasoning = parts[1].strip() if len(parts) > 1 else ""

        return {
            "recommended_tone": tone,
            "reasoning": reasoning,
            "ai_suggested": True,
        }

    except Exception as e:
        logger.error(f"AI tone suggestion failed: {e}")
        return _rule_based_tone_suggestion(client_context, situation)


def _rule_based_tone_suggestion(
    client_context: Dict[str, Any],
    situation: str,
) -> Dict[str, Any]:
    """Fallback rule-based tone suggestion."""
    tone = "professional"
    reasons = []

    relationship = client_context.get("relationship_type", "")
    revenue_pct = client_context.get("revenue_percent", 0)
    payment_behavior = client_context.get("payment_behavior", "")
    churn_risk = client_context.get("churn_risk", "")

    # Strategic clients get softer tone
    if relationship == "strategic":
        tone = "soft"
        reasons.append("Strategic client relationship")

    # High revenue clients get softer tone
    if revenue_pct >= 15:
        tone = "soft"
        reasons.append(f"High revenue client ({revenue_pct:.0f}%)")

    # Delayed payers need firmer tone
    if payment_behavior == "delayed" and tone != "soft":
        tone = "firm"
        reasons.append("History of delayed payments")

    # High churn risk needs careful handling
    if churn_risk == "high":
        tone = "soft"
        reasons.append("High churn risk")

    # Escalation situations need formal tone
    if "escalat" in situation.lower():
        tone = "formal"
        reasons.append("Escalation situation")

    return {
        "recommended_tone": tone,
        "reasoning": "; ".join(reasons) if reasons else "Standard professional approach",
        "ai_suggested": False,
    }
