"""
Detection Rules - V4 Architecture

Default detection rules and their configurations.
Based on the V4 brief's detection monitoring requirements.
"""

from .models import DetectionType


# Default thresholds for each detection type
DETECTION_RULES = {
    DetectionType.LATE_PAYMENT: {
        "name": "Late Payment Tracking",
        "description": "Detect invoices that are overdue and require follow-up",
        "default_thresholds": {
            "days_overdue": 7,  # Trigger after 7 days late
            "min_amount": 0,   # Any amount
        },
        "data_sources": ["ar_invoices", "bank_transactions"],
    },

    DetectionType.UNEXPECTED_REVENUE: {
        "name": "Unexpected Revenue Detection",
        "description": "Identify payment variances vs invoiced amounts",
        "default_thresholds": {
            "variance_percent": 10,  # 10% under or over
        },
        "data_sources": ["bank_transactions", "ar_invoices"],
    },

    DetectionType.CLIENT_CHURN: {
        "name": "Client Churn Detection",
        "description": "Flag revenue loss from cancellations or non-renewals",
        "default_thresholds": {
            "revenue_at_risk_percent": 5,  # Flag if 5%+ revenue at risk
        },
        "data_sources": ["recurring_invoices", "crm_status"],
    },

    DetectionType.STATUTORY_DEADLINE: {
        "name": "Statutory Deadline Monitoring",
        "description": "Track upcoming tax and regulatory deadlines",
        "default_thresholds": {
            "alert_days_before": [14, 7, 3],  # Alert at 14, 7, and 3 days
        },
        "data_sources": ["obligations", "user_defined_deadlines"],
    },

    DetectionType.UNEXPECTED_EXPENSE: {
        "name": "Unexpected Expense Detection",
        "description": "Flag abnormal expense spikes",
        "default_thresholds": {
            "variance_percent": 20,  # 20% above 3-month average
            "lookback_months": 3,
        },
        "data_sources": ["bank_transactions", "expense_history"],
    },

    DetectionType.PAYMENT_TIMING_CONFLICT: {
        "name": "Payment Timing Conflicts",
        "description": "Detect obligation clustering that strains cash",
        "default_thresholds": {
            "max_weekly_percent": 40,  # Flag if >40% of cash in one week
        },
        "data_sources": ["obligations", "bank_balances"],
    },

    DetectionType.VENDOR_TERMS_EXPIRING: {
        "name": "Vendor Payment Terms Expiring",
        "description": "Prevent late payments and fees",
        "default_thresholds": {
            "alert_days_before": 3,
        },
        "data_sources": ["ap_invoices", "payment_terms"],
    },

    DetectionType.HEADCOUNT_CHANGE: {
        "name": "Unbudgeted Headcount Increase",
        "description": "Detect new hires increasing burn",
        "default_thresholds": {
            "alert_on_any_change": True,
        },
        "data_sources": ["payroll"],
    },

    DetectionType.BUFFER_BREACH: {
        "name": "Buffer Breach Monitoring",
        "description": "Ensure cash covers obligations plus buffer",
        "default_thresholds": {
            "buffer_months": 3,  # Target 3 months buffer
            "warning_percent": 80,  # Warn at 80% of target
            "critical_percent": 50,  # Critical at 50% of target
        },
        "data_sources": ["bank_balances", "monthly_burn"],
    },

    DetectionType.RUNWAY_THRESHOLD: {
        "name": "Runway Monitoring",
        "description": "Track remaining months of runway",
        "default_thresholds": {
            "warning_months": 3,
            "critical_months": 1,
        },
        "data_sources": ["bank_balances", "monthly_burn"],
    },

    DetectionType.PAYROLL_SAFETY: {
        "name": "Payroll Safety Calculation",
        "description": "Confirm payroll viability or prepare contingency",
        "default_thresholds": {
            "days_before_payroll": 7,  # Check 7 days before
            "min_buffer_after": 0.1,   # 10% buffer after payroll
        },
        "data_sources": ["bank_balances", "payroll", "obligations"],
    },

    DetectionType.REVENUE_VARIANCE: {
        "name": "Revenue Variance Tracking",
        "description": "Track actual vs expected revenue",
        "default_thresholds": {
            "variance_percent": 15,  # Flag 15%+ variance
        },
        "data_sources": ["bank_transactions", "forecast"],
    },
}


def get_default_rules_for_user(user_id: str) -> list[dict]:
    """
    Generate default detection rules for a new user.

    Returns a list of rule configurations ready for insertion.
    """
    rules = []
    for detection_type, config in DETECTION_RULES.items():
        rules.append({
            "user_id": user_id,
            "detection_type": detection_type,
            "name": config["name"],
            "description": config["description"],
            "thresholds": config["default_thresholds"],
            "enabled": True,
        })
    return rules
