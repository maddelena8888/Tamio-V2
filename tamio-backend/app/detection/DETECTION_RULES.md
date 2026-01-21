# Detection Rules Documentation

This document defines the exact rules for each monitoring automation in the Tamio detection engine. These rules run automatically to identify cash flow risks and operational issues before they become problems.

**Note:** All default thresholds can be overridden by users in their `DetectionRule` configuration. User-defined thresholds always take precedence over system defaults.

---

## Table of Contents

1. [Late Payment Tracking](#1-late-payment-tracking)
2. [Unexpected Revenue Detection](#2-unexpected-revenue-detection)
3. [Client Churn Detection](#3-client-churn-detection)
4. [Statutory Deadline Monitoring](#4-statutory-deadline-monitoring)
5. [Unexpected Expense Detection](#5-unexpected-expense-detection)
6. [Payment Timing Conflicts](#6-payment-timing-conflicts)
7. [Vendor Payment Terms Expiring](#7-vendor-payment-terms-expiring)
8. [Headcount Change Detection](#8-headcount-change-detection)
9. [Buffer Breach Monitoring](#9-buffer-breach-monitoring)
10. [Runway Threshold Monitoring](#10-runway-threshold-monitoring)
11. [Payroll Safety](#11-payroll-safety)
12. [Revenue Variance](#12-revenue-variance)

**Appendices:**
- [Data Dependencies Summary](#data-dependencies-summary)
- [Data Model Field Requirements](#data-model-field-requirements)
- [Minimum Data Requirements for Alerts](#minimum-data-requirements-for-alerts)

---

## Data Dependencies Summary

This matrix shows which canonical data models each detection rule monitors:

| Detection Rule | ObligationAgreement | ObligationSchedule | PaymentEvent | Client | ExpenseBucket | CashAccount | AuditLog | UserConfiguration |
|----------------|:-------------------:|:------------------:|:------------:|:------:|:-------------:|:-----------:|:--------:|:-----------------:|
| LATE_PAYMENT | ✓ | ✓ (primary) | | ✓ | | | | ✓ |
| UNEXPECTED_REVENUE | | ✓ | ✓ (primary) | | | | | |
| CLIENT_CHURN | | | | ✓ (primary) | | | | |
| STATUTORY_DEADLINE | ✓ | ✓ (primary) | | | | | | |
| UNEXPECTED_EXPENSE | ✓ | | ✓ | | ✓ (primary) | | | ✓ |
| PAYMENT_TIMING_CONFLICT | ✓ | ✓ (primary) | | | | ✓ | | ✓ |
| VENDOR_TERMS_EXPIRING | ✓ | ✓ (primary) | | | ✓ | | | |
| HEADCOUNT_CHANGE | | | | | ✓ (primary) | | ✓ | |
| BUFFER_BREACH | | ✓ | | | | ✓ (primary) | | ✓ |
| RUNWAY_THRESHOLD | | ✓ | | | | ✓ (primary) | | ✓ |
| PAYROLL_SAFETY | | ✓ (primary) | | | ✓ | ✓ | | ✓ |
| REVENUE_VARIANCE | | ✓ | ✓ (primary) | | | | | |

**Legend:**
- ✓ (primary) = Main data source queried
- ✓ = Supporting data source joined/referenced

---

## 1. Late Payment Tracking

**Detection Type:** `LATE_PAYMENT`

### Purpose
Detect invoices that are overdue and require follow-up action.

### Data Sources
- `ObligationSchedule` (where obligation_type = "revenue")
- `ObligationAgreement`
- `Client`

### Field Requirements

**ObligationSchedule** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Must be unpaid |
| `due_date` | `<= today - threshold` | Past the overdue threshold |
| `estimated_amount` | `> 0` | Has a positive amount |
| `obligation_id` | NOT NULL | Links to agreement |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `= "revenue"` | Must be revenue, not expense |
| `client_id` | NOT NULL | Links to client for follow-up |

**Client** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `name` | NOT NULL | For alert context |
| `relationship_type` | Any | Used by preparation agent for tone |
| `avg_payment_delay_days` | Any | Used for risk assessment |

### Trigger Logic
```
IF schedule.status IN ("scheduled", "due")
   AND schedule.due_date <= (today - late_payment_threshold_days)
   AND schedule.estimated_amount >= min_amount
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `days_overdue` | 7 days | Days after due date to trigger alert |
| `min_amount` | $0 | Minimum invoice amount to track |

### User Configurable
- `UserConfiguration.late_payment_threshold_days`
- Rule-level threshold overrides

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≥14 days overdue | EMERGENCY |
| ≥7 days overdue | THIS_WEEK |
| <7 days overdue | UPCOMING |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "schedule_id": "uuid",
  "obligation_id": "uuid",
  "client_id": "uuid",
  "client_name": "Acme Corp",
  "days_overdue": 14,
  "amount": 25000.00,
  "due_date": "2024-01-15"
}
```

### Deduplication
One active alert per `schedule_id`. New alerts not created if existing ACTIVE/ACKNOWLEDGED/PREPARING alert exists for same schedule.

---

## 2. Unexpected Revenue Detection

**Detection Type:** `UNEXPECTED_REVENUE`

### Purpose
Identify payment variances vs invoiced amounts to catch under/overpayments.

### Data Sources
- `PaymentEvent`
- `ObligationSchedule`

### Field Requirements

**PaymentEvent** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `variance_vs_expected` | NOT NULL | Calculated variance (positive = overpaid) |
| `payment_date` | `>= today - 30 days` | Recent payments only |
| `amount` | `> 0` | Actual payment amount |
| `schedule_id` | NOT NULL | Links to expected schedule |

**ObligationSchedule** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `estimated_amount` | `> 0` | Expected payment amount |

### Trigger Logic
```
IF payment.variance_vs_expected IS NOT NULL
   AND payment.payment_date >= (today - 30 days)
   AND ABS((actual - expected) / expected * 100) >= variance_percent
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `variance_percent` | 10% | Minimum variance to trigger (under or over) |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| Overpayment (actual > expected) | THIS_WEEK |
| Underpayment (actual < expected) | UPCOMING |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "payment_id": "uuid",
  "schedule_id": "uuid",
  "expected_amount": 10000.00,
  "actual_amount": 8500.00,
  "variance_amount": -1500.00,
  "variance_percent": 15.0,
  "payment_date": "2024-01-20"
}
```

### Deduplication
One active alert per `payment_id`.

---

## 3. Client Churn Detection

**Detection Type:** `CLIENT_CHURN`

### Purpose
Flag revenue at risk from client cancellations, non-renewals, or deteriorating payment behavior.

### Data Sources
- `Client`

### Field Requirements

**Client** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `= "active"` | Only monitor active clients |
| `churn_risk` | `= "high"` OR any | High triggers immediately |
| `avg_payment_delay_days` | `> 30` triggers | Days late on average |
| `risk_level` | `= "critical"` triggers | Overall risk assessment |
| `revenue_percent` | `>= threshold` | Revenue concentration |
| `name` | NOT NULL | For alert context |
| `relationship_type` | Any | Used for retention strategy |

### Trigger Logic
```
IF client.status = "active"
   AND (
     client.churn_risk = "high"
     OR client.avg_payment_delay_days > 30
     OR client.risk_level = "critical"
   )
   AND (client.revenue_percent >= revenue_at_risk_percent OR client.churn_risk = "high")
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `revenue_at_risk_percent` | 5% | Minimum revenue % to flag |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≥15% of revenue at risk | EMERGENCY |
| <15% of revenue at risk | THIS_WEEK |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "client_id": "uuid",
  "client_name": "Acme Corp",
  "revenue_percent": 12.5,
  "churn_risk": "high",
  "avg_payment_delay_days": 45,
  "reasons": [
    "High churn risk flagged",
    "Payments averaging 45 days late"
  ]
}
```

### Deduplication
One active alert per `client_id`.

---

## 4. Statutory Deadline Monitoring

**Detection Type:** `STATUTORY_DEADLINE`

### Purpose
Track upcoming tax and regulatory deadlines to ensure timely compliance.

### Data Sources
- `ObligationSchedule` (where obligation_type = "tax_obligation")
- `ObligationAgreement`

### Field Requirements

**ObligationSchedule** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Must be pending |
| `due_date` | `>= today AND <= today + 14` | Within alert window |
| `estimated_amount` | `> 0` | Tax amount due |
| `obligation_id` | NOT NULL | Links to agreement |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `= "tax_obligation"` | Must be tax/statutory |
| `vendor_name` | Any | Tax authority name |

### Trigger Logic
```
IF obligation.obligation_type = "tax_obligation"
   AND schedule.status IN ("scheduled", "due")
   AND schedule.due_date >= today
   AND schedule.due_date <= (today + max(alert_days_before))
   AND days_until IN alert_windows (14, 7, 3)
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `alert_days_before` | [14, 7, 3] | Days before deadline to send alerts |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≤3 days until deadline | EMERGENCY |
| >3 days until deadline | THIS_WEEK |

### Schedule
- **Frequency:** Daily at 6:00 AM
- **Category:** DAILY_DETECTIONS

### Output
```json
{
  "schedule_id": "uuid",
  "obligation_id": "uuid",
  "obligation_name": "Q4 VAT Payment",
  "amount": 15000.00,
  "due_date": "2024-01-31",
  "days_until_due": 7
}
```

### Deduplication
One active alert per `schedule_id` + `days_bucket` (week grouping).

---

## 5. Unexpected Expense Detection

**Detection Type:** `UNEXPECTED_EXPENSE`

### Purpose
Flag abnormal expense spikes compared to historical averages.

### Data Sources
- `PaymentEvent`
- `ExpenseBucket`
- `ObligationAgreement`

### Field Requirements

**ExpenseBucket** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `id` | NOT NULL | Bucket identifier |
| `name` | NOT NULL | For alert context |
| `category` | Any | Expense category |
| `monthly_amount` | `> 0` | Expected monthly amount |

**PaymentEvent** (Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `payment_date` | `>= today - 90 days` | For historical average |
| `amount` | `> 0` | Payment amount |
| `obligation_id` | NOT NULL | Links to expense bucket |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `expense_bucket_id` | NOT NULL | Links payment to bucket |
| `obligation_type` | `!= "revenue"` | Must be expense type |

### Trigger Logic
```
FOR EACH expense_bucket:
  historical_avg = AVG(payments) for (today - lookback_months*30) to (today - 30)
  recent_total = SUM(payments) for last 30 days

  IF historical_avg > 0
     AND ((recent_total - historical_avg) / historical_avg * 100) >= variance_percent
  THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `variance_percent` | 20% | Spike above average to trigger |
| `lookback_months` | 3 | Months of history for baseline |

### User Configurable
- `UserConfiguration.unexpected_expense_threshold_pct`
- Rule-level threshold overrides

### Safety Mode Multiplier
Threshold is adjusted by safety mode:
- Conservative (0.7x): Triggers at 14% spike
- Normal (1.0x): Triggers at 20% spike
- Aggressive (1.3x): Triggers at 26% spike

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≥50% spike | EMERGENCY |
| <50% spike | THIS_WEEK |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "bucket_id": "uuid",
  "bucket_name": "Software Subscriptions",
  "category": "operations",
  "month": "2024-01",
  "recent_total": 12000.00,
  "historical_avg": 8000.00,
  "variance_percent": 50.0
}
```

### Deduplication
One active alert per `bucket_id` + `month`.

---

## 6. Payment Timing Conflicts

**Detection Type:** `PAYMENT_TIMING_CONFLICT`

### Purpose
Detect weeks where obligation clustering strains available cash.

### Data Sources
- `ObligationSchedule` (expense types)
- `CashAccount`

### Field Requirements

**ObligationSchedule** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Pending payments |
| `due_date` | `>= today AND <= today + 28` | Next 4 weeks |
| `estimated_amount` | `> 0` | Payment amount |
| `obligation_id` | NOT NULL | Links to agreement |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `!= "revenue"` | Expense obligations only |

**CashAccount** (Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `balance` | `> 0` | Current cash balance |
| `user_id` | = current user | User's accounts only |

### Trigger Logic
```
total_cash = SUM(cash_accounts.balance)

FOR EACH week in next 4 weeks:
  week_obligations = SUM(expense schedules due in week)
  week_percent = (week_obligations / total_cash) * 100

  IF week_percent >= max_weekly_percent
  THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_weekly_percent` | 40% | Maximum cash % due in one week |

### User Configurable
- `UserConfiguration.payment_cluster_threshold_pct`
- Rule-level threshold overrides

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≥60% of cash in one week | EMERGENCY |
| <60% of cash in one week | THIS_WEEK |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Lookforward Window
4 weeks from today

### Output
```json
{
  "week": "2024-W05",
  "week_start": "2024-01-29",
  "week_end": "2024-02-04",
  "total_due": 85000.00,
  "total_cash": 150000.00,
  "percent_of_cash": 56.7
}
```

### Deduplication
One active alert per `week` (ISO week format: YYYY-Www).

---

## 7. Vendor Payment Terms Expiring

**Detection Type:** `VENDOR_TERMS_EXPIRING`

### Purpose
Prevent late vendor payments and associated fees/penalties.

### Data Sources
- `ObligationSchedule` (expense types)
- `ExpenseBucket`

### Field Requirements

**ObligationSchedule** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Pending payment |
| `due_date` | `>= today AND <= today + 3` | Within 3 days |
| `estimated_amount` | `> 0` | Payment amount |
| `obligation_id` | NOT NULL | Links to agreement |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `!= "revenue"` | Expense obligations only |
| `vendor_name` | NOT NULL | For alert context |
| `expense_bucket_id` | Any | Links to vendor bucket |

**ExpenseBucket** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `name` | NOT NULL | Vendor/bucket name |
| `payment_terms` | Any | Terms info for context |
| `flexibility_level` | Any | Used for negotiation strategy |
| `delay_history` | Any | Past delay information |

### Trigger Logic
```
IF schedule.status IN ("scheduled", "due")
   AND obligation.obligation_type != "revenue"
   AND schedule.due_date >= today
   AND schedule.due_date <= (today + alert_days_before)
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `alert_days_before` | 3 days | Days before due date to alert |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≤1 day until due | EMERGENCY |
| >1 day until due | THIS_WEEK |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "schedule_id": "uuid",
  "obligation_id": "uuid",
  "vendor_id": "uuid",
  "vendor_name": "AWS",
  "amount": 5000.00,
  "due_date": "2024-01-25",
  "days_until_due": 2
}
```

### Deduplication
One active alert per `schedule_id`.

---

## 8. Headcount Change Detection

**Detection Type:** `HEADCOUNT_CHANGE`

### Purpose
Detect new hires that increase monthly burn rate.

### Data Sources
- `ExpenseBucket` (category = "payroll")
- `AuditLog`

### Field Requirements

**ExpenseBucket** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `category` | `= "payroll"` | Only payroll buckets |
| `employee_count` | NOT NULL | Current headcount |
| `name` | NOT NULL | Team/bucket name |
| `monthly_amount` | `> 0` | Monthly payroll cost |

**AuditLog** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `entity_type` | `= "expense_bucket"` | Bucket changes |
| `entity_id` | = bucket.id | Specific bucket |
| `field_name` | `= "employee_count"` | Headcount field |
| `action` | `= "update"` | Update action |
| `old_value` | Any (numeric) | Previous count |
| `new_value` | `> old_value` | New count (increase) |
| `created_at` | `>= now - 30 days` | Recent changes only |

### Trigger Logic
```
FOR EACH payroll bucket:
  recent_change = AuditLog WHERE
    entity_type = "expense_bucket"
    AND entity_id = bucket.id
    AND field_name = "employee_count"
    AND created_at >= (now - 30 days)

  IF recent_change.new_value > recent_change.old_value
  THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `alert_on_any_change` | true | Alert on any headcount increase |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| Any headcount increase | THIS_WEEK |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "bucket_id": "uuid",
  "bucket_name": "Engineering Team",
  "old_count": 10,
  "new_count": 12,
  "added": 2,
  "change_date": "2024-01-15",
  "estimated_monthly_impact": 15000.00
}
```

### Deduplication
One active alert per `bucket_id` + `change_date`.

---

## 9. Buffer Breach Monitoring

**Detection Type:** `BUFFER_BREACH`

### Purpose
Ensure cash reserves cover obligations plus a safety buffer.

### Data Sources
- `CashAccount`
- `ObligationSchedule`

### Field Requirements

**CashAccount** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `balance` | Any (can be 0) | Current balance |
| `user_id` | = current user | User's accounts |

**ObligationSchedule** (Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Pending payments |
| `due_date` | Current month | This month's obligations |
| `estimated_amount` | `> 0` | Payment amounts |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `!= "revenue"` | Expenses only |

**UserConfiguration** (Read):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligations_buffer_amount` | Any | User's buffer target |
| `runway_buffer_months` | Any | Months of buffer |
| `safety_mode` | Any | Affects thresholds |

### Trigger Logic
```
total_cash = SUM(cash_accounts.balance)
monthly_burn = SUM(expense schedules this month)
target_buffer = monthly_burn * buffer_months

buffer_percent = (total_cash / target_buffer) * 100

# Also check against user's absolute buffer amount
IF config.obligations_buffer_amount > 0:
  buffer_percent = MIN(buffer_percent, (total_cash / config.obligations_buffer_amount) * 100)

IF buffer_percent < critical_percent
THEN trigger EMERGENCY alert
ELSE IF buffer_percent < warning_percent
THEN trigger THIS_WEEK alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `buffer_months` | 3 months | Target buffer in months of burn |
| `warning_percent` | 80% | Warning at this % of target |
| `critical_percent` | 50% | Critical at this % of target |

### User Configurable
- `UserConfiguration.obligations_buffer_amount`
- `UserConfiguration.runway_buffer_months`
- Rule-level threshold overrides

### Severity Logic
| Condition | Severity |
|-----------|----------|
| <50% of target buffer | EMERGENCY |
| <80% of target buffer | THIS_WEEK |

### Schedule
- **Frequency:** Every 5 minutes (critical)
- **Category:** CRITICAL_DETECTIONS

### Output
```json
{
  "severity": "critical",
  "current_cash": 75000.00,
  "target_buffer": 150000.00,
  "buffer_percent": 50.0,
  "monthly_burn": 50000.00,
  "buffer_months": 3
}
```

### Deduplication
One active alert per `severity` level ("critical" or "warning").

---

## 10. Runway Threshold Monitoring

**Detection Type:** `RUNWAY_THRESHOLD`

### Purpose
Track remaining months of operational runway based on net burn rate.

### Data Sources
- `CashAccount`
- `ObligationSchedule` (trailing 90 days)

### Field Requirements

**CashAccount** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `balance` | Any | Current balance |
| `user_id` | = current user | User's accounts |

**ObligationSchedule** (Aggregated - 90 days):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `due_date` | `>= today - 90 days` | Trailing 3 months |
| `estimated_amount` | `> 0` | Payment amounts |
| `status` | Any | For historical tracking |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | Any | Needed to separate revenue vs expense |

**UserConfiguration** (Read):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `runway_buffer_months` | Any | Warning threshold |

### Trigger Logic
```
total_cash = SUM(cash_accounts.balance)

# Calculate trailing 3-month averages
total_expenses = SUM(expense schedules in last 90 days)
total_revenue = SUM(revenue schedules in last 90 days)

monthly_expenses = total_expenses / 3
monthly_revenue = total_revenue / 3
net_burn = monthly_expenses - monthly_revenue

IF net_burn <= 0:
  RETURN (cash flow positive, no alert)

runway_months = total_cash / net_burn

IF runway_months <= critical_months
THEN trigger EMERGENCY alert
ELSE IF runway_months <= warning_months
THEN trigger THIS_WEEK alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `warning_months` | 3 months | Warning threshold |
| `critical_months` | 1 month | Critical/emergency threshold |

### User Configurable
- `UserConfiguration.runway_buffer_months` (for warning)
- Rule-level threshold overrides

### Severity Logic
| Condition | Severity |
|-----------|----------|
| ≤1 month runway | EMERGENCY |
| ≤3 months runway | THIS_WEEK |

### Schedule
- **Frequency:** Daily at 6:00 AM
- **Category:** DAILY_DETECTIONS

### Output
```json
{
  "severity": "warning",
  "runway_months": 2.5,
  "current_cash": 125000.00,
  "monthly_burn": 50000.00,
  "monthly_expenses": 80000.00,
  "monthly_revenue": 30000.00
}
```

### Deduplication
One active alert per `severity` level ("critical" or "warning").

### Note
If the business is cash-flow positive (revenue > expenses), no runway alert is generated.

---

## 11. Payroll Safety

**Detection Type:** `PAYROLL_SAFETY`

### Purpose
Confirm upcoming payroll is fully funded with required buffer, or trigger contingency preparation.

### Data Sources
- `CashAccount`
- `ObligationSchedule` (payroll category)
- `ExpenseBucket` (category = "payroll")

### Field Requirements

**ObligationSchedule** (Primary):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `status` | `IN ("scheduled", "due")` | Pending payroll |
| `due_date` | `>= today AND <= today + 7` | Next 7 days |
| `estimated_amount` | `> 0` | Payroll amount |
| `obligation_id` | NOT NULL | Links to agreement |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `category` | `= "payroll"` | Payroll obligations |
| `expense_bucket_id` | NOT NULL | Links to payroll bucket |

**ExpenseBucket** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `category` | `= "payroll"` | Payroll buckets |
| `employee_count` | Any | For context |
| `name` | NOT NULL | Team/department name |

**CashAccount** (Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `balance` | Any | Current balance |
| `user_id` | = current user | User's accounts |

**UserConfiguration** (Read):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `payroll_check_days_before` | Any | Days ahead to check |
| `payroll_buffer_percent` | Any | Required buffer % |

### Trigger Logic
```
FOR EACH upcoming payroll schedule in next N days:
  payroll_date = schedule.due_date
  payroll_amount = schedule.estimated_amount

  # Calculate obligations due before payroll
  obligations_before = SUM(all schedules due between today and payroll_date, excluding this payroll)

  cash_after_obligations = total_cash - obligations_before
  cash_after_payroll = cash_after_obligations - payroll_amount
  buffer_needed = payroll_amount * min_buffer_after

  IF cash_after_payroll < buffer_needed
  THEN trigger alert with shortfall = buffer_needed - cash_after_payroll
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `days_before_payroll` | 7 days | How far ahead to check |
| `min_buffer_after` | 10% | Required buffer after payroll (as % of payroll) |

### User Configurable
- `UserConfiguration.payroll_check_days_before`
- `UserConfiguration.payroll_buffer_percent`
- Rule-level threshold overrides

### Severity Logic
| Condition | Severity |
|-----------|----------|
| Cash after payroll < 0 | EMERGENCY |
| Cash after payroll < buffer | THIS_WEEK |

### Schedule
- **Frequency:** Every 5 minutes (critical)
- **Category:** CRITICAL_DETECTIONS

### Output
```json
{
  "schedule_id": "uuid",
  "payroll_amount": 85000.00,
  "payroll_date": "2024-01-31",
  "current_cash": 120000.00,
  "obligations_before_payroll": 25000.00,
  "cash_after_payroll": 10000.00,
  "buffer_needed": 8500.00,
  "shortfall": 0
}
```

### Deduplication
One active alert per `schedule_id`.

### Deadline
Alert deadline is set to 2 days before payroll date to allow time for contingency actions.

---

## 12. Revenue Variance

**Detection Type:** `REVENUE_VARIANCE`

### Purpose
Track actual vs expected revenue at the monthly aggregate level.

### Data Sources
- `PaymentEvent` (revenue)
- `ObligationSchedule` (revenue)

### Field Requirements

**PaymentEvent** (Primary - Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `payment_date` | Current month | This month's payments |
| `amount` | `> 0` | Payment amounts |
| `obligation_id` | NOT NULL | Links to revenue obligation |

**ObligationSchedule** (Aggregated):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `due_date` | Current month | This month's expected |
| `estimated_amount` | `> 0` | Expected amounts |
| `status` | Any | All scheduled revenue |

**ObligationAgreement** (Joined):
| Field | Required Value | Description |
|-------|----------------|-------------|
| `obligation_type` | `= "revenue"` | Revenue only |

### Trigger Logic
```
month_start = first day of current month
month_end = last day of current month

expected_revenue = SUM(revenue schedules due this month)
actual_revenue = SUM(revenue payments received this month to date)

variance_pct = ((actual_revenue - expected_revenue) / expected_revenue) * 100

IF ABS(variance_pct) >= variance_percent
THEN trigger alert
```

### Default Thresholds
| Parameter | Default | Description |
|-----------|---------|-------------|
| `variance_percent` | 15% | Variance threshold to trigger |

### User Configurable
- Rule-level threshold overrides only

### Severity Logic
| Condition | Severity |
|-----------|----------|
| Behind target (negative variance) | THIS_WEEK |
| Ahead of target (positive variance) | UPCOMING |

### Schedule
- **Frequency:** Hourly (routine)
- **Category:** ROUTINE_DETECTIONS

### Output
```json
{
  "month": "2024-01-01",
  "expected_revenue": 100000.00,
  "actual_revenue": 82000.00,
  "variance_amount": -18000.00,
  "variance_percent": -18.0
}
```

### Deduplication
One active alert per `month`.

---

## Scheduling Summary

### Critical Detections (Every 5 Minutes)
| Detection | Reason |
|-----------|--------|
| PAYROLL_SAFETY | Payroll failure is catastrophic |
| BUFFER_BREACH | Cash emergency needs immediate attention |

### Routine Detections (Every Hour)
| Detection | Reason |
|-----------|--------|
| LATE_PAYMENT | Payment follow-up timing |
| UNEXPECTED_EXPENSE | Expense monitoring |
| UNEXPECTED_REVENUE | Payment variance tracking |
| CLIENT_CHURN | Revenue risk monitoring |
| REVENUE_VARIANCE | Monthly performance |
| PAYMENT_TIMING_CONFLICT | Cash flow planning |
| VENDOR_TERMS_EXPIRING | Prevent late fees |
| HEADCOUNT_CHANGE | Burn rate changes |

### Daily Detections (6:00 AM)
| Detection | Reason |
|-----------|--------|
| STATUTORY_DEADLINE | Regulatory compliance |
| RUNWAY_THRESHOLD | Strategic runway planning |

---

## Escalation Rules

Alerts can be automatically escalated based on:

1. **Deadline Proximity:** If deadline is within 3 days → escalate to EMERGENCY
2. **Inaction:** If ACTIVE for 2+ days with no acknowledgment → escalate severity
3. **Large Impact:** Late payment >$10k and >14 days overdue → escalate to EMERGENCY
4. **Cascade Effects:** If late payment affects payroll coverage → escalate to EMERGENCY

---

## Safety Mode Multipliers

The `UserConfiguration.safety_mode` affects detection sensitivity:

| Mode | Multiplier | Effect |
|------|------------|--------|
| CONSERVATIVE | 0.7x | Lower thresholds, earlier warnings |
| NORMAL | 1.0x | Default behavior |
| AGGRESSIVE | 1.3x | Higher thresholds, fewer warnings |

Applied to:
- `late_payment_threshold_days`
- `unexpected_expense_threshold_pct`

---

## Alert Lifecycle

```
ACTIVE → ACKNOWLEDGED → PREPARING → RESOLVED
                    ↘ DISMISSED
```

| Status | Description |
|--------|-------------|
| ACTIVE | Newly detected, needs attention |
| ACKNOWLEDGED | User has seen the alert |
| PREPARING | Action is being prepared |
| RESOLVED | Issue resolved successfully |
| DISMISSED | User dismissed without action |

---

## Data Model Field Requirements

This appendix provides the complete field specifications for each data model used by the detection engine.

### ObligationAgreement

```
Table: obligation_agreements
Location: app/data/obligations/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Alert context_data |
| `user_id` | String (FK) | Filter by user |
| `obligation_type` | String | Filter: "revenue", "tax_obligation", expense types |
| `category` | String | Filter: "payroll", "rent", etc. |
| `base_amount` | Numeric | Reference for variance |
| `currency` | String | Multi-currency support |
| `vendor_name` | String | Alert context |
| `client_id` | String (FK) | Link to Client for revenue |
| `expense_bucket_id` | String (FK) | Link to ExpenseBucket for expenses |
| `start_date` | Date | Active period check |
| `end_date` | Date | Active period check |

### ObligationSchedule

```
Table: obligation_schedules
Location: app/data/obligations/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Deduplication key |
| `obligation_id` | String (FK) | Join to agreement |
| `due_date` | Date | Primary trigger condition |
| `estimated_amount` | Numeric | Amount thresholds |
| `status` | String | Filter: "scheduled", "due", "paid", "overdue" |
| `confidence` | String | Risk weighting |

### PaymentEvent

```
Table: payment_events
Location: app/data/obligations/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Deduplication key |
| `user_id` | String (FK) | Filter by user |
| `obligation_id` | String (FK) | Join to agreement |
| `schedule_id` | String (FK) | Join to schedule |
| `amount` | Numeric | Actual payment amount |
| `payment_date` | Date | Recency filter |
| `variance_vs_expected` | Numeric | Revenue variance detection |
| `status` | String | Filter: "completed" |

### Client

```
Table: clients
Location: app/data/clients/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Deduplication key |
| `user_id` | String (FK) | Filter by user |
| `name` | String | Alert context |
| `status` | String | Filter: "active" |
| `churn_risk` | String | Trigger: "high" |
| `avg_payment_delay_days` | Integer | Trigger: > 30 |
| `risk_level` | String | Trigger: "critical" |
| `revenue_percent` | Numeric | Concentration risk |
| `relationship_type` | String | Preparation tone |

### ExpenseBucket

```
Table: expense_buckets
Location: app/data/expenses/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Deduplication key |
| `user_id` | String (FK) | Filter by user |
| `name` | String | Alert context |
| `category` | String | Filter: "payroll" |
| `monthly_amount` | Numeric | Variance baseline |
| `employee_count` | Integer | Headcount tracking |
| `payment_terms` | String | Vendor terms context |
| `flexibility_level` | String | Delay negotiation |
| `delay_history` | JSONB | Past delays |

### CashAccount

```
Table: cash_accounts
Location: app/data/balances/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Account identifier |
| `user_id` | String (FK) | Filter by user |
| `account_name` | String | Alert context |
| `balance` | Numeric | Cash position aggregation |
| `currency` | String | Multi-currency support |
| `as_of_date` | Date | Balance freshness |

### AuditLog

```
Table: audit_logs
Location: app/audit/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `id` | String (PK) | Log identifier |
| `entity_type` | String | Filter: "expense_bucket" |
| `entity_id` | String | Match to bucket ID |
| `action` | String | Filter: "update" |
| `field_name` | String | Filter: "employee_count" |
| `old_value` | JSONB | Previous value |
| `new_value` | JSONB | New value |
| `created_at` | DateTime | Recency filter |

### UserConfiguration

```
Table: user_configurations
Location: app/data/user_config/models.py
```

| Field | Type | Detection Usage |
|-------|------|-----------------|
| `user_id` | String (PK) | One per user |
| `obligations_buffer_amount` | Numeric | Buffer target |
| `runway_buffer_months` | Integer | Runway warning |
| `late_payment_threshold_days` | Integer | Overdue threshold |
| `unexpected_expense_threshold_pct` | Numeric | Expense spike % |
| `safety_mode` | Enum | Threshold multiplier |
| `payroll_check_days_before` | Integer | Payroll lookahead |
| `payroll_buffer_percent` | Numeric | Payroll buffer % |
| `payment_cluster_threshold_pct` | Numeric | Weekly concentration % |

---

## Minimum Data Requirements for Alerts

For each detection rule to function, the following minimum data must exist:

### LATE_PAYMENT
```
✓ At least 1 ObligationAgreement with obligation_type = "revenue" and client_id set
✓ At least 1 ObligationSchedule with status IN ("scheduled", "due") and due_date in the past
✓ Client record exists with name populated
```

### UNEXPECTED_REVENUE
```
✓ At least 1 PaymentEvent with variance_vs_expected populated
✓ Linked ObligationSchedule with estimated_amount
```

### CLIENT_CHURN
```
✓ At least 1 Client with status = "active"
✓ Client has churn_risk = "high" OR avg_payment_delay_days > 30 OR risk_level = "critical"
✓ revenue_percent populated for concentration check
```

### STATUTORY_DEADLINE
```
✓ At least 1 ObligationAgreement with obligation_type = "tax_obligation"
✓ At least 1 ObligationSchedule with due_date within 14 days
```

### UNEXPECTED_EXPENSE
```
✓ At least 1 ExpenseBucket
✓ At least 90 days of PaymentEvent history for baseline
✓ ObligationAgreement linking payments to bucket
```

### PAYMENT_TIMING_CONFLICT
```
✓ At least 1 CashAccount with balance > 0
✓ ObligationSchedule entries with due_date in next 28 days
✓ Expense obligations totaling > 40% of cash in any week
```

### VENDOR_TERMS_EXPIRING
```
✓ At least 1 ObligationSchedule with due_date within 3 days
✓ ObligationAgreement with obligation_type != "revenue"
```

### HEADCOUNT_CHANGE
```
✓ At least 1 ExpenseBucket with category = "payroll" and employee_count set
✓ AuditLog entry showing employee_count increase in last 30 days
```

### BUFFER_BREACH
```
✓ At least 1 CashAccount
✓ ObligationSchedule entries for current month expenses
✓ UserConfiguration with obligations_buffer_amount or runway_buffer_months
```

### RUNWAY_THRESHOLD
```
✓ At least 1 CashAccount
✓ 90 days of ObligationSchedule history (expenses and revenue)
✓ Net burn > 0 (expenses > revenue)
```

### PAYROLL_SAFETY
```
✓ At least 1 CashAccount
✓ ObligationSchedule with category = "payroll" in next 7 days
✓ ExpenseBucket with category = "payroll"
```

### REVENUE_VARIANCE
```
✓ PaymentEvent entries for current month (revenue)
✓ ObligationSchedule entries for current month (revenue)
✓ Variance >= 15% threshold
```

---

## Data Seeding Checklist

When setting up demo data or testing detection rules, ensure:

1. **Cash Position**
   - [ ] Create CashAccount(s) with realistic balances
   - [ ] Set as_of_date to current date

2. **Revenue Pipeline**
   - [ ] Create Client records with risk indicators
   - [ ] Create revenue ObligationAgreements linked to clients
   - [ ] Create ObligationSchedules with various statuses and due dates
   - [ ] Create some overdue schedules (due_date < today)

3. **Expense Obligations**
   - [ ] Create ExpenseBucket records (include payroll category)
   - [ ] Set employee_count on payroll buckets
   - [ ] Create expense ObligationAgreements linked to buckets
   - [ ] Create ObligationSchedules for next 30 days

4. **Payment History**
   - [ ] Create PaymentEvent records for last 90 days
   - [ ] Include some with variance_vs_expected populated
   - [ ] Link to ObligationSchedules and Agreements

5. **Configuration**
   - [ ] Create UserConfiguration record
   - [ ] Set thresholds appropriate for demo data

6. **Audit Trail**
   - [ ] Create AuditLog entries for headcount changes
   - [ ] Ensure field_name = "employee_count" with old/new values
