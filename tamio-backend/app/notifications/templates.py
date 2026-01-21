"""
Email Templates - V4 Architecture

HTML and plain text email templates for notifications.
"""

from typing import Optional
from datetime import datetime

from app.detection.models import AlertSeverity, DetectionType


def get_severity_color(severity: AlertSeverity) -> str:
    """Get color for severity level."""
    return {
        AlertSeverity.EMERGENCY: "#DC2626",   # Red
        AlertSeverity.THIS_WEEK: "#F59E0B",   # Amber
        AlertSeverity.UPCOMING: "#3B82F6",    # Blue
    }.get(severity, "#6B7280")


def get_severity_label(severity: AlertSeverity) -> str:
    """Get human-readable severity label."""
    return {
        AlertSeverity.EMERGENCY: "EMERGENCY - Action Required Today",
        AlertSeverity.THIS_WEEK: "This Week - Needs Attention",
        AlertSeverity.UPCOMING: "Upcoming - For Your Awareness",
    }.get(severity, "Alert")


def get_detection_type_icon(detection_type: DetectionType) -> str:
    """Get emoji icon for detection type."""
    return {
        DetectionType.LATE_PAYMENT: "⏰",
        DetectionType.UNEXPECTED_REVENUE: "💰",
        DetectionType.UNEXPECTED_EXPENSE: "📊",
        DetectionType.CLIENT_CHURN: "👤",
        DetectionType.REVENUE_VARIANCE: "📈",
        DetectionType.PAYMENT_TIMING_CONFLICT: "📅",
        DetectionType.VENDOR_TERMS_EXPIRING: "📋",
        DetectionType.STATUTORY_DEADLINE: "🏛️",
        DetectionType.BUFFER_BREACH: "⚠️",
        DetectionType.RUNWAY_THRESHOLD: "🛫",
        DetectionType.PAYROLL_SAFETY: "💵",
        DetectionType.HEADCOUNT_CHANGE: "👥",
    }.get(detection_type, "🔔")


# =============================================================================
# BASE TEMPLATE
# =============================================================================

BASE_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #1F2937;
            margin: 0;
            padding: 0;
            background-color: #F3F4F6;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 24px;
            margin-bottom: 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            text-align: center;
            padding: 20px 0;
        }}
        .logo {{
            font-size: 24px;
            font-weight: bold;
            color: #1F2937;
        }}
        .severity-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            color: white;
            background-color: {severity_color};
        }}
        .alert-title {{
            font-size: 20px;
            font-weight: 600;
            margin: 16px 0 8px;
        }}
        .alert-description {{
            color: #4B5563;
            margin-bottom: 16px;
        }}
        .impact {{
            background: #F9FAFB;
            border-radius: 6px;
            padding: 12px 16px;
            margin: 16px 0;
        }}
        .impact-label {{
            font-size: 12px;
            color: #6B7280;
            text-transform: uppercase;
        }}
        .impact-value {{
            font-size: 24px;
            font-weight: 600;
            color: #1F2937;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #2563EB;
            color: white;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 500;
            margin-top: 16px;
        }}
        .button:hover {{
            background-color: #1D4ED8;
        }}
        .footer {{
            text-align: center;
            color: #6B7280;
            font-size: 12px;
            padding: 20px 0;
        }}
        .context-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #E5E7EB;
        }}
        .context-label {{
            color: #6B7280;
        }}
        .context-value {{
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">Tamio</div>
        </div>
        {content}
        <div class="footer">
            <p>Tamio - Your Treasury Operator</p>
            <p>
                <a href="{dashboard_url}">Open Dashboard</a> |
                <a href="{settings_url}">Notification Settings</a>
            </p>
        </div>
    </div>
</body>
</html>
"""


# =============================================================================
# ALERT TEMPLATES
# =============================================================================

def build_alert_email(
    alert_title: str,
    alert_description: str,
    severity: AlertSeverity,
    detection_type: DetectionType,
    cash_impact: Optional[float],
    context_data: dict,
    dashboard_url: str,
    settings_url: str,
    deadline: Optional[datetime] = None,
) -> tuple[str, str, str]:
    """
    Build alert notification email.

    Returns: (subject, html_body, plain_text_body)
    """
    severity_label = get_severity_label(severity)
    severity_color = get_severity_color(severity)
    icon = get_detection_type_icon(detection_type)

    # Build subject
    subject = f"{icon} [{severity.value.upper()}] {alert_title}"

    # Build impact section
    impact_html = ""
    if cash_impact:
        formatted_impact = f"${abs(cash_impact):,.0f}"
        impact_label = "Potential Impact"
        impact_html = f"""
        <div class="impact">
            <div class="impact-label">{impact_label}</div>
            <div class="impact-value">{formatted_impact}</div>
        </div>
        """

    # Build context section - OBLIGATION-FOCUSED
    context_html = ""
    if context_data:
        context_items = []

        # Priority 1: Obligation-focused fields (show these first)
        obligation_fields = {
            "obligation_name": "Obligation",
            "shortfall": "Shortfall",
            "obligation_due_date": "Obligation Due",
            "obligation_amount": "Obligation Amount",
            "coverage_percent": "Coverage",
        }

        # Priority 2: Other context fields
        other_fields = {
            "days_overdue": "Days Overdue",
            "amount": "Amount",
            "due_date": "Due Date",
            "variance_percent": "Variance",
            "runway_months": "Runway",
            "client_name": "Client",
            "vendor_name": "Vendor",
            "invoice_number": "Invoice",
        }

        # Process obligation fields first
        for key, label in obligation_fields.items():
            if key in context_data:
                value = context_data[key]
                if key in ("shortfall", "obligation_amount"):
                    value = f"${value:,.0f}" if isinstance(value, (int, float)) else value
                elif key == "coverage_percent":
                    value = f"{value}%" if isinstance(value, (int, float)) else value
                context_items.append(f"""
                <div class="context-item">
                    <span class="context-label">{label}</span>
                    <span class="context-value">{value}</span>
                </div>
                """)

        # Process other fields
        for key, label in other_fields.items():
            if key in context_data:
                value = context_data[key]
                if key == "amount":
                    value = f"${value:,.0f}" if isinstance(value, (int, float)) else value
                elif key == "variance_percent":
                    value = f"{value}%"
                elif key == "runway_months":
                    value = f"{value} months"
                context_items.append(f"""
                <div class="context-item">
                    <span class="context-label">{label}</span>
                    <span class="context-value">{value}</span>
                </div>
                """)

        # Add "Caused By" section if late payments are causing the issue
        causing_payments = context_data.get("causing_payments", [])
        if causing_payments:
            caused_by_items = []
            for payment in causing_payments[:3]:  # Show up to 3
                client_name = payment.get("client_name", "Unknown")
                amount = payment.get("amount", 0)
                days = payment.get("days_overdue", 0)
                caused_by_items.append(f"{client_name}: ${amount:,.0f} ({days}d overdue)")

            if caused_by_items:
                context_items.append(f"""
                <div class="context-item" style="flex-direction: column; align-items: flex-start;">
                    <span class="context-label">Caused By</span>
                    <span class="context-value" style="margin-top: 4px;">{'; '.join(caused_by_items)}</span>
                </div>
                """)

        if context_items:
            context_html = f"<div>{''.join(context_items)}</div>"

    # Build deadline section
    deadline_html = ""
    if deadline:
        deadline_str = deadline.strftime("%B %d, %Y")
        deadline_html = f"""
        <div class="context-item">
            <span class="context-label">Deadline</span>
            <span class="context-value" style="color: {severity_color};">{deadline_str}</span>
        </div>
        """

    # Build main content
    content = f"""
    <div class="card">
        <span class="severity-badge" style="background-color: {severity_color};">{severity_label}</span>
        <h2 class="alert-title">{alert_title}</h2>
        <p class="alert-description">{alert_description}</p>
        {impact_html}
        {context_html}
        {deadline_html}
        <a href="{dashboard_url}" class="button">View in Dashboard</a>
    </div>
    """

    html_body = BASE_HTML_TEMPLATE.format(
        subject=subject,
        content=content,
        severity_color=severity_color,
        dashboard_url=dashboard_url,
        settings_url=settings_url,
    )

    # Build plain text version with obligation-focused context
    plain_text_lines = [
        severity_label,
        "",
        alert_title,
        "",
        alert_description,
    ]

    # Add obligation context
    if context_data:
        obligation_name = context_data.get("obligation_name")
        shortfall = context_data.get("shortfall")
        obligation_due = context_data.get("obligation_due_date")

        if obligation_name:
            plain_text_lines.append("")
            plain_text_lines.append(f"Obligation: {obligation_name}")
            if shortfall:
                plain_text_lines.append(f"Shortfall: ${shortfall:,.0f}")
            if obligation_due:
                plain_text_lines.append(f"Due: {obligation_due}")

        # Add caused by context
        causing_payments = context_data.get("causing_payments", [])
        if causing_payments:
            caused_by_parts = []
            for payment in causing_payments[:3]:
                client = payment.get("client_name", "Unknown")
                amount = payment.get("amount", 0)
                days = payment.get("days_overdue", 0)
                caused_by_parts.append(f"{client}: ${amount:,.0f} ({days}d overdue)")
            plain_text_lines.append("")
            plain_text_lines.append(f"Caused by: {'; '.join(caused_by_parts)}")

    if cash_impact:
        plain_text_lines.append("")
        plain_text_lines.append(f"Cash Impact: ${abs(cash_impact):,.0f}")

    plain_text_lines.extend([
        "",
        f"View in Dashboard: {dashboard_url}",
        "",
        "---",
        "Tamio - Your Treasury Operator",
    ])

    plain_text = "\n".join(plain_text_lines)

    return subject, html_body, plain_text.strip()


# =============================================================================
# ESCALATION TEMPLATE
# =============================================================================

def build_escalation_email(
    alert_title: str,
    old_severity: AlertSeverity,
    new_severity: AlertSeverity,
    reason: str,
    dashboard_url: str,
    settings_url: str,
) -> tuple[str, str, str]:
    """
    Build escalation notification email.

    Returns: (subject, html_body, plain_text_body)
    """
    severity_color = get_severity_color(new_severity)

    subject = f"🚨 Alert Escalated: {alert_title}"

    content = f"""
    <div class="card">
        <span class="severity-badge" style="background-color: {severity_color};">
            ESCALATED TO {new_severity.value.upper()}
        </span>
        <h2 class="alert-title">{alert_title}</h2>
        <p class="alert-description">
            This alert has been escalated from <strong>{old_severity.value}</strong>
            to <strong>{new_severity.value}</strong>.
        </p>
        <div class="impact">
            <div class="impact-label">Reason for Escalation</div>
            <div style="margin-top: 8px;">{reason}</div>
        </div>
        <a href="{dashboard_url}" class="button">Take Action Now</a>
    </div>
    """

    html_body = BASE_HTML_TEMPLATE.format(
        subject=subject,
        content=content,
        severity_color=severity_color,
        dashboard_url=dashboard_url,
        settings_url=settings_url,
    )

    plain_text = f"""
ALERT ESCALATED

{alert_title}

Escalated from {old_severity.value} to {new_severity.value}

Reason: {reason}

Take Action: {dashboard_url}

---
Tamio - Your Treasury Operator
"""

    return subject, html_body, plain_text.strip()


# =============================================================================
# ACTION READY TEMPLATE
# =============================================================================

def build_action_ready_email(
    action_type: str,
    problem_summary: str,
    options_count: int,
    deadline: Optional[datetime],
    dashboard_url: str,
    settings_url: str,
) -> tuple[str, str, str]:
    """
    Build action ready notification email.

    Returns: (subject, html_body, plain_text_body)
    """
    subject = f"✅ Action Ready: {problem_summary[:50]}..."

    deadline_html = ""
    if deadline:
        deadline_str = deadline.strftime("%B %d, %Y")
        deadline_html = f"""
        <div class="context-item">
            <span class="context-label">Decision needed by</span>
            <span class="context-value">{deadline_str}</span>
        </div>
        """

    content = f"""
    <div class="card">
        <span class="severity-badge" style="background-color: #10B981;">ACTION READY</span>
        <h2 class="alert-title">Your Action is Ready</h2>
        <p class="alert-description">{problem_summary}</p>
        <div class="impact">
            <div class="impact-label">Options Prepared</div>
            <div class="impact-value">{options_count} options</div>
        </div>
        {deadline_html}
        <a href="{dashboard_url}" class="button">Review & Approve</a>
    </div>
    """

    html_body = BASE_HTML_TEMPLATE.format(
        subject=subject,
        content=content,
        severity_color="#10B981",
        dashboard_url=dashboard_url,
        settings_url=settings_url,
    )

    plain_text = f"""
ACTION READY

{problem_summary}

{options_count} options have been prepared for your review.

{"Decision needed by: " + deadline.strftime("%B %d, %Y") if deadline else ""}

Review & Approve: {dashboard_url}

---
Tamio - Your Treasury Operator
"""

    return subject, html_body, plain_text.strip()


# =============================================================================
# DAILY DIGEST TEMPLATE
# =============================================================================

def build_daily_digest_email(
    emergency_count: int,
    this_week_count: int,
    upcoming_count: int,
    actions_pending: int,
    alerts_summary: list[dict],
    dashboard_url: str,
    settings_url: str,
) -> tuple[str, str, str]:
    """
    Build daily digest email.

    Returns: (subject, html_body, plain_text_body)
    """
    total = emergency_count + this_week_count + upcoming_count

    if emergency_count > 0:
        subject = f"🔴 Daily Digest: {emergency_count} Emergency Alert(s)"
    elif this_week_count > 0:
        subject = f"🟡 Daily Digest: {this_week_count} Alert(s) Need Attention"
    else:
        subject = f"✅ Daily Digest: All Clear"

    # Build alerts summary
    alerts_html = ""
    if alerts_summary:
        items = []
        for alert in alerts_summary[:10]:  # Limit to 10
            severity_color = get_severity_color(AlertSeverity(alert["severity"]))
            items.append(f"""
            <div style="padding: 12px; border-left: 4px solid {severity_color}; margin-bottom: 8px; background: #F9FAFB;">
                <strong>{alert["title"]}</strong>
                <div style="color: #6B7280; font-size: 14px;">{alert.get("description", "")[:100]}</div>
            </div>
            """)
        alerts_html = "".join(items)

    content = f"""
    <div class="card">
        <h2 class="alert-title">Your Daily Treasury Summary</h2>
        <div style="display: flex; gap: 16px; margin: 16px 0;">
            <div style="flex: 1; text-align: center; padding: 16px; background: #FEE2E2; border-radius: 6px;">
                <div style="font-size: 24px; font-weight: bold; color: #DC2626;">{emergency_count}</div>
                <div style="font-size: 12px; color: #991B1B;">Emergency</div>
            </div>
            <div style="flex: 1; text-align: center; padding: 16px; background: #FEF3C7; border-radius: 6px;">
                <div style="font-size: 24px; font-weight: bold; color: #D97706;">{this_week_count}</div>
                <div style="font-size: 12px; color: #92400E;">This Week</div>
            </div>
            <div style="flex: 1; text-align: center; padding: 16px; background: #DBEAFE; border-radius: 6px;">
                <div style="font-size: 24px; font-weight: bold; color: #2563EB;">{upcoming_count}</div>
                <div style="font-size: 12px; color: #1E40AF;">Upcoming</div>
            </div>
        </div>
        <div style="text-align: center; padding: 16px; background: #F0FDF4; border-radius: 6px; margin-bottom: 16px;">
            <div style="font-size: 24px; font-weight: bold; color: #16A34A;">{actions_pending}</div>
            <div style="font-size: 12px; color: #166534;">Actions Pending Approval</div>
        </div>
        {f'<h3>Recent Alerts</h3>{alerts_html}' if alerts_html else '<p style="color: #6B7280;">No alerts requiring attention.</p>'}
        <a href="{dashboard_url}" class="button">Open Dashboard</a>
    </div>
    """

    html_body = BASE_HTML_TEMPLATE.format(
        subject=subject,
        content=content,
        severity_color="#6B7280",
        dashboard_url=dashboard_url,
        settings_url=settings_url,
    )

    plain_text = f"""
DAILY TREASURY SUMMARY

Emergency Alerts: {emergency_count}
This Week: {this_week_count}
Upcoming: {upcoming_count}

Actions Pending Approval: {actions_pending}

Open Dashboard: {dashboard_url}

---
Tamio - Your Treasury Operator
"""

    return subject, html_body, plain_text.strip()
