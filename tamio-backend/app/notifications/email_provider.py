"""
Email Provider - V4 Architecture

Abstract email sending with support for multiple providers.
Default: Resend (simple, modern API)
Fallback: SMTP (for self-hosted)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Email message to send."""
    to: str
    subject: str
    html_body: str
    plain_text_body: str
    from_email: Optional[str] = None
    reply_to: Optional[str] = None


@dataclass
class SendResult:
    """Result of sending an email."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send(self, message: EmailMessage) -> SendResult:
        """Send an email message."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured."""
        pass


class ResendProvider(EmailProvider):
    """
    Resend email provider.

    Requires RESEND_API_KEY environment variable.
    https://resend.com/docs/api-reference/emails/send-email
    """

    def __init__(self, api_key: str, from_email: str = "Tamio <notifications@tamio.app>"):
        self.api_key = api_key
        self.from_email = from_email
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def send(self, message: EmailMessage) -> SendResult:
        if not self.is_configured():
            return SendResult(success=False, error="Resend API key not configured")

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "from": message.from_email or self.from_email,
                        "to": [message.to],
                        "subject": message.subject,
                        "html": message.html_body,
                        "text": message.plain_text_body,
                        **({"reply_to": message.reply_to} if message.reply_to else {}),
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return SendResult(
                        success=True,
                        message_id=data.get("id"),
                    )
                else:
                    error_msg = response.text
                    logger.error(f"Resend API error: {response.status_code} - {error_msg}")
                    return SendResult(success=False, error=error_msg)

        except Exception as e:
            logger.exception("Failed to send email via Resend")
            return SendResult(success=False, error=str(e))


class SMTPProvider(EmailProvider):
    """
    SMTP email provider.

    For self-hosted or traditional SMTP servers.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password)

    async def send(self, message: EmailMessage) -> SendResult:
        if not self.is_configured():
            return SendResult(success=False, error="SMTP not configured")

        try:
            import aiosmtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = message.from_email or self.from_email
            msg["To"] = message.to

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            # Attach plain text and HTML versions
            msg.attach(MIMEText(message.plain_text_body, "plain"))
            msg.attach(MIMEText(message.html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=self.use_tls,
            )

            return SendResult(success=True)

        except Exception as e:
            logger.exception("Failed to send email via SMTP")
            return SendResult(success=False, error=str(e))


class ConsoleProvider(EmailProvider):
    """
    Console email provider for development/testing.

    Logs emails to console instead of sending.
    """

    def is_configured(self) -> bool:
        return True

    async def send(self, message: EmailMessage) -> SendResult:
        logger.info(
            f"\n{'='*60}\n"
            f"EMAIL (Console Mode)\n"
            f"{'='*60}\n"
            f"To: {message.to}\n"
            f"Subject: {message.subject}\n"
            f"{'='*60}\n"
            f"{message.plain_text_body}\n"
            f"{'='*60}\n"
        )
        return SendResult(success=True, message_id="console-dev")


# =============================================================================
# SLACK PROVIDER
# =============================================================================

@dataclass
class SlackMessage:
    """Slack message to send."""
    channel: str  # Channel ID or name (e.g., #treasury-alerts)
    text: str  # Plain text fallback
    blocks: Optional[list] = None  # Rich Block Kit blocks
    thread_ts: Optional[str] = None  # Reply to thread


@dataclass
class SlackResult:
    """Result of sending a Slack message."""
    success: bool
    message_ts: Optional[str] = None  # Message timestamp (ID)
    channel: Optional[str] = None
    error: Optional[str] = None


class SlackProvider:
    """
    Slack notification provider.

    Requires SLACK_BOT_TOKEN and SLACK_CHANNEL environment variables.
    Uses Slack Web API: https://api.slack.com/methods/chat.postMessage
    """

    def __init__(
        self,
        bot_token: str,
        default_channel: str = "#treasury-alerts",
    ):
        self.bot_token = bot_token
        self.default_channel = default_channel

    def is_configured(self) -> bool:
        return bool(self.bot_token)

    async def send(self, message: SlackMessage) -> SlackResult:
        if not self.is_configured():
            return SlackResult(success=False, error="Slack bot token not configured")

        try:
            import httpx

            channel = message.channel or self.default_channel

            payload = {
                "channel": channel,
                "text": message.text,
            }

            if message.blocks:
                payload["blocks"] = message.blocks

            if message.thread_ts:
                payload["thread_ts"] = message.thread_ts

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30.0,
                )

                data = response.json()

                if data.get("ok"):
                    return SlackResult(
                        success=True,
                        message_ts=data.get("ts"),
                        channel=data.get("channel"),
                    )
                else:
                    error_msg = data.get("error", "Unknown Slack error")
                    logger.error(f"Slack API error: {error_msg}")
                    return SlackResult(success=False, error=error_msg)

        except Exception as e:
            logger.exception("Failed to send Slack message")
            return SlackResult(success=False, error=str(e))

    def build_alert_blocks(
        self,
        title: str,
        description: str,
        severity: str,
        cash_impact: Optional[float] = None,
        dashboard_url: Optional[str] = None,
    ) -> list:
        """
        Build Slack Block Kit blocks for an alert notification.

        Returns rich formatting with severity colors and action buttons.
        """
        # Severity emoji and color
        severity_config = {
            "emergency": {"emoji": "🔴", "text": "EMERGENCY"},
            "this_week": {"emoji": "🟡", "text": "This Week"},
            "upcoming": {"emoji": "🔵", "text": "Upcoming"},
        }
        config = severity_config.get(severity.lower(), severity_config["upcoming"])

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{config['emoji']} {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Severity:* {config['text']}\n\n{description}"
                }
            },
        ]

        # Add cash impact if present
        if cash_impact is not None:
            impact_text = f"${abs(cash_impact):,.0f}"
            if cash_impact < 0:
                impact_text = f"-{impact_text}"
            blocks.append({
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Cash Impact:*\n{impact_text}"
                    }
                ]
            })

        # Add action button
        if dashboard_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in Dashboard",
                            "emoji": True
                        },
                        "url": dashboard_url,
                        "action_id": "view_dashboard"
                    }
                ]
            })

        blocks.append({"type": "divider"})

        return blocks

    def build_digest_blocks(
        self,
        emergency_count: int,
        this_week_count: int,
        upcoming_count: int,
        actions_pending: int,
        dashboard_url: Optional[str] = None,
    ) -> list:
        """Build Slack blocks for daily digest."""
        # Header with appropriate emoji
        if emergency_count > 0:
            header = f"🔴 Daily Digest: {emergency_count} Emergency Alert(s)"
        elif this_week_count > 0:
            header = f"🟡 Daily Digest: {this_week_count} Item(s) Need Attention"
        else:
            header = "✅ Daily Digest: All Clear"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header,
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*🔴 Emergency*\n{emergency_count}"},
                    {"type": "mrkdwn", "text": f"*🟡 This Week*\n{this_week_count}"},
                    {"type": "mrkdwn", "text": f"*🔵 Upcoming*\n{upcoming_count}"},
                    {"type": "mrkdwn", "text": f"*✅ Actions Pending*\n{actions_pending}"},
                ]
            },
        ]

        if dashboard_url:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Open Dashboard",
                            "emoji": True
                        },
                        "url": dashboard_url,
                        "style": "primary",
                        "action_id": "open_dashboard"
                    }
                ]
            })

        return blocks


class ConsoleSlackProvider(SlackProvider):
    """Console Slack provider for development/testing."""

    def __init__(self):
        super().__init__(bot_token="", default_channel="#console")

    def is_configured(self) -> bool:
        return True

    async def send(self, message: SlackMessage) -> SlackResult:
        logger.info(
            f"\n{'='*60}\n"
            f"SLACK (Console Mode)\n"
            f"{'='*60}\n"
            f"Channel: {message.channel}\n"
            f"Text: {message.text}\n"
            f"{'='*60}\n"
        )
        return SlackResult(success=True, message_ts="console-dev", channel=message.channel)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def get_email_provider(
    resend_api_key: Optional[str] = None,
    smtp_config: Optional[dict] = None,
    console_mode: bool = False,
) -> EmailProvider:
    """
    Get the appropriate email provider based on configuration.

    Priority:
    1. Console mode (for development)
    2. Resend (if API key provided)
    3. SMTP (if config provided)
    4. Console fallback
    """
    if console_mode:
        logger.info("Using console email provider (development mode)")
        return ConsoleProvider()

    if resend_api_key:
        logger.info("Using Resend email provider")
        return ResendProvider(api_key=resend_api_key)

    if smtp_config:
        logger.info("Using SMTP email provider")
        return SMTPProvider(**smtp_config)

    logger.warning("No email provider configured, using console fallback")
    return ConsoleProvider()


def get_slack_provider(
    bot_token: Optional[str] = None,
    default_channel: str = "#treasury-alerts",
    console_mode: bool = False,
) -> SlackProvider:
    """
    Get the appropriate Slack provider based on configuration.

    Args:
        bot_token: Slack bot OAuth token
        default_channel: Default channel to post to
        console_mode: If True, use console provider for development
    """
    if console_mode:
        logger.info("Using console Slack provider (development mode)")
        return ConsoleSlackProvider()

    if bot_token:
        logger.info("Using Slack provider")
        return SlackProvider(bot_token=bot_token, default_channel=default_channel)

    logger.warning("No Slack token configured, using console fallback")
    return ConsoleSlackProvider()
