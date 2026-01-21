# Tamio Data Architecture

This document describes the canonical data architecture for Tamio's cash flow forecasting system.

**Last Updated**: 2026-01-10 (V4 Architecture Alignment)

## Architecture Principles

1. **Single Source of Truth**: ObligationAgreement is the canonical source for all committed cash flows
2. **Separation of Concerns**: User input (Client/ExpenseBucket) → Obligation → Forecast
3. **Audit Trail**: All changes are logged for debugging and compliance
4. **Gradual Migration**: Feature flags enable safe transition between old and new systems
5. **Integration Agnostic**: IntegrationMapping decouples entities from specific integrations
6. **V4 Alignment**: Data model supports the 4-stage Tamio loop (Vigilance → Preparation → Approval → Execution)

## Entity Relationship Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            USER INPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────┐                         ┌──────────────────┐             │
│   │    Client    │                         │  ExpenseBucket   │             │
│   │  (Revenue)   │                         │   (Expenses)     │             │
│   └──────┬───────┘                         └────────┬─────────┘             │
│          │                                          │                       │
│          │  One-to-Many                             │  One-to-Many          │
│          ▼                                          ▼                       │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                           │
                    ▼                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OBLIGATION LAYER (Source of Truth)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                     ┌────────────────────────┐                              │
│                     │  ObligationAgreement   │  ← WHY: Contract/Agreement   │
│                     │  - client_id (FK)      │                              │
│                     │  - expense_bucket_id   │                              │
│                     │  - obligation_type     │                              │
│                     │  - base_amount         │                              │
│                     │  - frequency           │                              │
│                     └───────────┬────────────┘                              │
│                                 │                                           │
│                                 │  One-to-Many                              │
│                                 ▼                                           │
│                     ┌────────────────────────┐                              │
│                     │  ObligationSchedule    │  ← WHEN: Payment schedule    │
│                     │  - due_date            │                              │
│                     │  - estimated_amount    │                              │
│                     │  - status              │                              │
│                     └───────────┬────────────┘                              │
│                                 │                                           │
│                                 │  One-to-Many                              │
│                                 ▼                                           │
│                     ┌────────────────────────┐                              │
│                     │    PaymentEvent        │  ← REALITY: Actual payment   │
│                     │  - amount              │                              │
│                     │  - payment_date        │                              │
│                     │  - status              │                              │
│                     └────────────────────────┘                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OUTPUT LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────┐                    ┌────────────────────────────┐   │
│   │    CashEvent     │                    │     ForecastEvent          │   │
│   │ (Stored, Audit)  │ ◄──────────────►   │ (Computed on-the-fly)      │   │
│   │ - schedule_id FK │                    │ - From ObligationSchedule  │   │
│   └──────────────────┘                    └────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Creating a Client/Expense

```
1. User creates Client or ExpenseBucket via API
2. Routes call ObligationService.create_obligation_from_*()
3. ObligationService creates ObligationAgreement with client_id or expense_bucket_id FK
4. ObligationService generates ObligationSchedules for next 3 months
5. (Optional) CashEvents generated from schedules for audit trail
```

### Computing a Forecast

```
1. API calls calculate_forecast_v2()
2. If USE_OBLIGATION_FOR_FORECAST=True:
   - Query ObligationSchedules in date range
   - Convert to ForecastEvents on-the-fly
3. If USE_OBLIGATION_FOR_FORECAST=False (legacy):
   - Query Clients and ExpenseBuckets
   - Compute ForecastEvents from billing_config
4. Build weekly forecast with confidence scoring
```

### Syncing with Xero

```
1. Push: SyncService.push_client_to_xero()
   - Update Client.xero_contact_id (legacy field)
   - Create/update IntegrationMapping (new architecture)
   - Log sync to AuditLog

2. Pull: SyncService.pull_clients_from_xero()
   - Create/update Client records
   - Set source="xero", locked_fields=["name"]
   - Create IntegrationMapping
```

## Feature Flags

Located in `app/config.py`:

| Flag | Default | Description |
|------|---------|-------------|
| `USE_OBLIGATION_SYSTEM` | `True` | Create ObligationAgreements from Clients/ExpenseBuckets |
| `USE_OBLIGATION_FOR_FORECAST` | `False` | Use ObligationSchedules for forecast computation |
| `DEPRECATE_DIRECT_CASH_EVENTS` | `False` | Stop generating CashEvents directly from Client/ExpenseBucket |

### Migration Path

1. **Phase 1** (Current): `USE_OBLIGATION_SYSTEM=True`
   - Dual-write: Both legacy CashEvents AND ObligationSchedules created
   - Forecasts still use legacy Client/ExpenseBucket data

2. **Phase 2**: `USE_OBLIGATION_FOR_FORECAST=True`
   - Forecasts now read from ObligationSchedules
   - Legacy CashEvent generation continues for audit

3. **Phase 3**: `DEPRECATE_DIRECT_CASH_EVENTS=True`
   - Stop generating legacy CashEvents
   - All forecasts from ObligationSchedules
   - CashEvents only from schedule-to-event generator

## Key Tables

### Core Domain

| Table | Purpose |
|-------|---------|
| `users` | User accounts with base_currency preference |
| `clients` | Revenue sources (customers) with V4 fields for payment behavior |
| `expense_buckets` | Expense categories (Vendor equivalent) with V4 flexibility fields |
| `cash_accounts` | Bank accounts with balances |

### Obligation System

| Table | Purpose |
|-------|---------|
| `obligation_agreements` | Contracts/agreements (source of truth) |
| `obligation_schedules` | Expected payment dates |
| `payment_events` | Actual payments with variance tracking |
| `cash_events` | Materialized forecast events (audit trail) |

### Detection & Action System (V4)

| Table | Purpose |
|-------|---------|
| `detection_rules` | User-configurable detection thresholds |
| `detection_alerts` | Active alerts from detection engine |
| `prepared_actions` | Work prepared by agents for approval |
| `action_options` | Multiple options per prepared action |
| `execution_records` | Audit trail of executed actions |
| `execution_automation_rules` | V2 auto-execution configuration |

### Integration System

| Table | Purpose |
|-------|---------|
| `integration_mappings` | Links entities to external IDs |
| `integration_connections` | OAuth tokens per user/integration |
| `xero_connections` | (Legacy) Xero-specific connections |
| `xero_sync_logs` | (Legacy) Xero sync history |

### Support Tables

| Table | Purpose |
|-------|---------|
| `exchange_rates` | Currency conversion rates |
| `audit_logs` | All data changes |

## Currency Handling

### Multi-Currency Support

- Each entity stores both `currency` and `base_currency_amount`
- `base_currency_amount` = amount converted to user's base currency
- `exchange_rate_used` = rate at time of conversion
- Forecasts aggregate using `base_currency_amount` for consistency

### Conversion Flow

```python
# When creating/updating with non-base currency:
if entity.currency != user.base_currency:
    converted, rate, date = await convert_amount(
        db, amount, entity.currency, user.base_currency
    )
    entity.base_currency_amount = converted
    entity.exchange_rate_used = rate
    entity.exchange_rate_date = date
```

## IntegrationMapping vs Legacy Fields

### Legacy Approach (Deprecated)
```python
class Client:
    xero_contact_id = Column(String)  # Scattered across entities
    quickbooks_customer_id = Column(String)
```

### New Approach
```python
class IntegrationMapping:
    entity_type = "client"
    entity_id = "client_abc123"
    integration_type = "xero"
    external_id = "xero_contact_xyz"
    external_type = "contact"
    sync_status = "synced"
```

### Benefits
- Add new integrations without schema changes
- Query entities by external ID efficiently
- Centralized sync status tracking
- Support multiple mappings per entity

## Audit Trail

All data changes are logged to `audit_logs`:

```python
# Example: Creating a client
audit = AuditService(db, user_id=current_user.id)
await audit.log_create("client", client.id, {"name": "Acme Corp"})

# Example: Updating a client
await audit.log_update("client", client.id, {
    "name": ("Old Name", "New Name"),
    "status": ("active", "paused")
})

# Example: Sync operation
await audit.log_sync("client", client.id, "xero", "push", {
    "contact_id": result["contact_id"]
})
```

## Common Queries

### Get all obligations for a client
```python
obligations = await db.execute(
    select(ObligationAgreement)
    .where(ObligationAgreement.client_id == client_id)
)
```

### Get upcoming payments
```python
schedules = await db.execute(
    select(ObligationSchedule)
    .join(ObligationAgreement)
    .where(
        ObligationAgreement.user_id == user_id,
        ObligationSchedule.due_date >= date.today(),
        ObligationSchedule.status == "scheduled"
    )
    .order_by(ObligationSchedule.due_date)
)
```

### Find entity by Xero ID
```python
mapping = await db.execute(
    select(IntegrationMapping)
    .where(
        IntegrationMapping.integration_type == "xero",
        IntegrationMapping.external_id == xero_contact_id,
        IntegrationMapping.external_type == "contact"
    )
)
entity_type = mapping.entity_type  # "client" or "expense_bucket"
entity_id = mapping.entity_id
```

## File Structure

```
tamio-backend/
├── app/
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── models.py          # AuditLog model
│   │   └── services.py        # AuditService
│   │
│   ├── data/
│   │   ├── clients/           # Client model & routes (V4 fields added)
│   │   ├── expenses/          # ExpenseBucket model & routes (V4 fields added)
│   │   ├── obligations/       # 3-layer obligation models (V4 variance added)
│   │   ├── events/            # CashEvent model
│   │   ├── exchange_rates/    # ExchangeRate model & routes
│   │   └── event_generator.py # CashEvent generation
│   │
│   ├── detection/             # V4 Stage 1.3: Detection Monitoring
│   │   ├── models.py          # DetectionRule, DetectionAlert
│   │   ├── engine.py          # DetectionEngine
│   │   └── rules.py           # Default rule configurations
│   │
│   ├── preparation/           # V4 Stage 2: Work Preparation
│   │   ├── models.py          # PreparedAction, ActionOption, LinkedAction
│   │   └── engine.py          # PreparationEngine
│   │
│   ├── actions/               # V4 Stage 3: Approval Queue
│   │   ├── routes.py          # Action queue API endpoints
│   │   └── schemas.py         # Pydantic schemas
│   │
│   ├── execution/             # V4 Stage 4: Execution
│   │   ├── models.py          # ExecutionRecord, ExecutionAutomationRule
│   │   └── service.py         # ExecutionService
│   │
│   ├── forecast/
│   │   └── engine_v2.py       # Forecast computation
│   │
│   ├── integrations/
│   │   ├── models.py          # IntegrationMapping, IntegrationConnection
│   │   ├── services.py        # IntegrationMappingService
│   │   ├── base.py            # IntegrationAdapter interface
│   │   └── confidence.py      # Confidence scoring
│   │
│   ├── services/
│   │   ├── obligations.py     # ObligationService
│   │   └── exchange_rates.py  # Currency conversion
│   │
│   ├── xero/                  # Xero-specific integration
│   └── config.py              # Feature flags
│
└── migrations/versions/
    ├── 20260105_0001-add_client_expense_fks_to_obligations.py
    ├── 20260105_0002-add_schedule_fk_to_cash_events.py
    ├── 20260105_0003-add_integration_mappings_table.py
    ├── 20260105_0004-add_base_currency_amounts.py
    ├── 20260105_0005-add_audit_logs_table.py
    └── 20260110_0001-add_v4_data_model_fields.py   # V4 schema additions
```

## Common Pitfalls

1. **Forgetting to create obligations**: Always call `ObligationService` when creating/updating clients or expenses

2. **Using wrong forecast flag**: Check `USE_OBLIGATION_FOR_FORECAST` when debugging forecast discrepancies

3. **Currency conversion timing**: Convert at write-time, not read-time, to ensure consistent exchange rates

4. **IntegrationMapping vs legacy fields**: Both are written during transition - read from IntegrationMapping, write to both

5. **Audit log transactions**: Don't commit inside AuditService - let the caller manage the transaction

---

## V4 Canonical Data Model

The V4 architecture defines a canonical data model that maps to the 4-stage Tamio loop.

### V4 Entity Mapping

| V4 Entity | Tamio Table | Notes |
|-----------|-------------|-------|
| Cash_Event | `cash_events` | Fully implemented |
| Client | `clients` | V4 fields added (see below) |
| Vendor | `expense_buckets` | V4 fields added (see below) |
| Revenue_Agreement | `obligation_agreements` | Via client_id FK |
| AR_Invoice | `obligation_schedules` | Implied by schedule status |
| Payment_Receipt | `payment_events` | V4 variance field added |
| Obligation | `obligation_agreements` | Via expense_bucket_id FK |
| Payment_Event | `payment_events` | Fully implemented |
| Payroll | `obligation_agreements` + `expense_buckets` | category="payroll" |
| Detection_Rule_Config | `detection_rules` | Fully implemented |
| Prepared_Action | `prepared_actions` + `action_options` | Fully implemented |

### V4 Client Fields

Added to support detection and preparation agents:

```python
class Client:
    # ... existing fields ...

    # V4 Required Fields
    avg_payment_delay_days = Column(Integer)       # Payment pattern (0 = on time)
    relationship_type = Column(String)             # "strategic" | "transactional" | "managed"
    revenue_percent = Column(Numeric(5,2))         # Concentration risk (e.g., 15.50%)
    risk_level = Column(String)                    # "low" | "medium" | "high" | "critical"
```

**Usage in V4 stages:**
- **Detection**: `avg_payment_delay_days` used to flag unusual late payments
- **Preparation**: `relationship_type` determines message tone (soft/professional/firm)
- **Preparation**: `revenue_percent` influences risk scoring (high % = more careful)

### V4 ExpenseBucket (Vendor) Fields

Added to support vendor delay triage:

```python
class ExpenseBucket:
    # ... existing fields ...

    # V4 Required Vendor Fields
    payment_terms = Column(String)                 # "net_30" | "net_60" | "due_on_receipt"
    payment_terms_days = Column(Integer)           # Actual days (for calculation)
    flexibility_level = Column(String)             # "can_delay" | "negotiable" | "cannot_delay"
    criticality = Column(String)                   # "critical" | "important" | "flexible"
    delay_history = Column(JSONB)                  # Past delay events
```

**Usage in V4 stages:**
- **Detection**: `payment_terms_days` used to calculate overdue status
- **Preparation**: `flexibility_level` determines if vendor is a delay candidate
- **Preparation**: `criticality` affects risk scoring (critical = higher risk to delay)
- **Preparation**: `delay_history` informs whether we've delayed before

### V4 PaymentEvent Fields

Added for variance tracking:

```python
class PaymentEvent:
    # ... existing fields ...

    # V4 Required Field
    variance_vs_expected = Column(Numeric(15,2))   # Actual - Expected (positive = overpaid)
```

**Usage in V4 stages:**
- **Detection**: Flags unexpected revenue/expense variances
- **Preparation**: Informs follow-up actions for underpayments

### V4 Execution Automation Rules

New table for V2 auto-execution configuration:

```python
class ExecutionAutomationRule:
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"))

    action_type = Column(Enum)                     # invoice_follow_up, payment_batch, etc.
    auto_execute = Column(Boolean, default=False)  # Enable auto-execution

    # Conditions
    threshold_amount = Column(Float)               # Max amount for auto (e.g., $10,000)
    threshold_currency = Column(String)            # Currency for threshold
    excluded_tags = Column(JSON)                   # Tags to exclude (e.g., ["strategic"])
    included_tags = Column(JSON)                   # Tags to include (optional)

    require_approval = Column(Boolean)             # Require approval first?
    is_locked = Column(Boolean)                    # Cannot be changed (payroll)
```

**Default rules (created on user signup):**

| Action Type | Auto-Execute | Threshold | Notes |
|-------------|--------------|-----------|-------|
| invoice_follow_up | False | - | Exclude strategic clients |
| payment_batch | False | $10,000 | Below threshold only |
| vendor_delay | False | - | Only "flexible" vendors |
| statutory_payment | False | - | Always manual |
| payroll | False | - | LOCKED - never auto |
| excess_allocation | False | - | Always manual |

### V4 Detection Types

Implemented in `app/detection/models.py`:

```python
class DetectionType(str, Enum):
    LATE_PAYMENT = "late_payment"                  # Invoice overdue
    UNEXPECTED_REVENUE = "unexpected_revenue"      # Payment variance
    UNEXPECTED_EXPENSE = "unexpected_expense"      # Expense spike
    CLIENT_CHURN = "client_churn"                  # Revenue at risk
    REVENUE_VARIANCE = "revenue_variance"          # Actual vs expected
    PAYMENT_TIMING_CONFLICT = "payment_timing_conflict"  # Obligation clustering
    VENDOR_TERMS_EXPIRING = "vendor_terms_expiring"      # Payment deadline
    STATUTORY_DEADLINE = "statutory_deadline"      # Tax/regulatory
    BUFFER_BREACH = "buffer_breach"                # Cash below threshold
    RUNWAY_THRESHOLD = "runway_threshold"          # Runway warning
    PAYROLL_SAFETY = "payroll_safety"              # Payroll at risk
    HEADCOUNT_CHANGE = "headcount_change"          # New hire detected
```

### V4 Action Types

Implemented in `app/preparation/models.py`:

```python
class ActionType(str, Enum):
    INVOICE_FOLLOW_UP = "invoice_follow_up"
    PAYMENT_REMINDER = "payment_reminder"
    COLLECTION_ESCALATION = "collection_escalation"
    PAYMENT_BATCH = "payment_batch"
    VENDOR_DELAY = "vendor_delay"
    PAYMENT_PRIORITIZATION = "payment_prioritization"
    PAYROLL_CONTINGENCY = "payroll_contingency"
    PAYROLL_CONFIRMATION = "payroll_confirmation"
    EXCESS_CASH_ALLOCATION = "excess_cash_allocation"
    CREDIT_LINE_DRAW = "credit_line_draw"
    INVOICE_GENERATION = "invoice_generation"
    STATUTORY_PAYMENT = "statutory_payment"
```

### V4 Alert Severity

Maps to urgency tiers in UI:

```python
class AlertSeverity(str, Enum):
    EMERGENCY = "emergency"      # Red - Must act today
    THIS_WEEK = "this_week"      # Yellow - Review within 2-3 days
    UPCOMING = "upcoming"        # Green - Monitoring only
```

---

## Migration: 20260110_0001-add_v4_data_model_fields

This migration adds all V4 required fields:

```sql
-- Client V4 fields
ALTER TABLE clients ADD COLUMN avg_payment_delay_days INTEGER DEFAULT 0;
ALTER TABLE clients ADD COLUMN relationship_type VARCHAR;
ALTER TABLE clients ADD COLUMN revenue_percent NUMERIC(5,2);
ALTER TABLE clients ADD COLUMN risk_level VARCHAR;

-- ExpenseBucket V4 fields
ALTER TABLE expense_buckets ADD COLUMN payment_terms VARCHAR;
ALTER TABLE expense_buckets ADD COLUMN payment_terms_days INTEGER;
ALTER TABLE expense_buckets ADD COLUMN flexibility_level VARCHAR;
ALTER TABLE expense_buckets ADD COLUMN criticality VARCHAR;
ALTER TABLE expense_buckets ADD COLUMN delay_history JSONB DEFAULT '[]';

-- PaymentEvent V4 fields
ALTER TABLE payment_events ADD COLUMN variance_vs_expected NUMERIC(15,2);

-- New table: execution_automation_rules
CREATE TABLE execution_automation_rules (...);

-- New table: user_configurations
CREATE TABLE user_configurations (...);
```

---

## V4 Detection Engine

The Detection Engine monitors the user's financial data and generates alerts when problems are detected.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DETECTION ENGINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  UserConfiguration ──► 12 Detection Types ──► DetectedAlert             │
│   (thresholds)         (rule-based checks)    (severity + context)      │
│                                                                          │
│  Safety Modes:                                                           │
│  - conservative: 1.25x thresholds (stricter)                            │
│  - normal: baseline thresholds                                          │
│  - aggressive: 0.75x thresholds (relaxed)                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Detection Types

| Type | Severity Logic | Entity Type |
|------|---------------|-------------|
| `LATE_PAYMENT` | 30+ days = EMERGENCY, 14+ = THIS_WEEK | client |
| `BUFFER_BREACH` | Always EMERGENCY | system |
| `PAYROLL_SAFETY` | <5 days = EMERGENCY | system |
| `RUNWAY_THRESHOLD` | <3 months = EMERGENCY | system |
| `STATUTORY_DEADLINE` | <3 days = EMERGENCY | obligation |
| `UNEXPECTED_EXPENSE` | >threshold% = THIS_WEEK | expense |
| `UNEXPECTED_REVENUE` | Variance detected = THIS_WEEK | client |
| `CLIENT_CHURN` | Strategic = EMERGENCY, other = THIS_WEEK | client |
| `REVENUE_VARIANCE` | >20% variance = THIS_WEEK | metric |
| `PAYMENT_TIMING_CONFLICT` | Cluster detected = THIS_WEEK | system |
| `VENDOR_TERMS_EXPIRING` | <7 days = THIS_WEEK | expense |
| `HEADCOUNT_CHANGE` | New hire = THIS_WEEK | system |

### Running Detections

```python
from app.detection import DetectionEngine

engine = DetectionEngine(db, user_id)

# Run all 12 detection types
alerts = await engine.run_all_detections()

# Run only critical checks (fast)
alerts = await engine.run_critical_detections()

# Alerts sorted by severity (EMERGENCY first)
for alert in alerts:
    print(f"{alert.severity}: {alert.type} - {alert.entity_name}")
```

### Scheduling

Detection runs are scheduled via APScheduler:

| Schedule | Detections | Frequency |
|----------|------------|-----------|
| Critical | buffer_breach, payroll_safety, statutory | Every 5 min |
| Routine | All 12 types | Hourly |
| Daily | Historical variance analysis | 6 AM daily |

```python
from app.detection.scheduler import setup_apscheduler

scheduler = await setup_apscheduler(app)
# Automatically runs all user detections on schedule
```

---

## V4 Preparation Engine

The Preparation Engine converts detected alerts into actionable recommendations.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       PREPARATION ENGINE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  DetectedAlert ──► Agent Selection ──► Context Gather ──► Options       │
│                                                                          │
│  Components:                                                             │
│  ├─ context.py       - Fetch client/vendor/cash context                 │
│  ├─ risk_scoring.py  - Composite risk calculation                       │
│  ├─ message_drafting.py - Template-based message generation             │
│  └─ engine.py        - Agent workflows                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Agent Workflows

Each detection type maps to a specific agent workflow:

| Detection Type | Agent | Output |
|---------------|-------|--------|
| `LATE_PAYMENT` | `_invoice_followup_agent` | Collection emails (soft/professional/firm) |
| `PAYROLL_SAFETY` | `_payroll_safety_agent` | Contingency plans |
| `BUFFER_BREACH` | `_buffer_response_agent` | Delay/accelerate options |
| `VENDOR_TERMS_EXPIRING` | `_vendor_payment_agent` | Payment batch/delay |
| `STATUTORY_DEADLINE` | `_statutory_payment_agent` | Payment preparation |
| `CLIENT_CHURN` | `_client_retention_agent` | Retention actions |
| `UNEXPECTED_EXPENSE` | `_expense_review_agent` | Review/approval |
| `REVENUE_VARIANCE` | `_revenue_variance_agent` | Forecast adjustment |
| `RUNWAY_THRESHOLD` | `_runway_response_agent` | Cost reduction options |
| `HEADCOUNT_CHANGE` | `_headcount_review_agent` | Payroll update |

### Risk Scoring

Actions are scored using a composite risk formula:

```python
composite_risk = (relationship_risk × 0.4) + (operational_risk × 0.3) + (financial_cost × 0.3)
```

Where:
- **relationship_risk**: Client importance, payment history, revenue concentration
- **operational_risk**: Action reversibility, time sensitivity, complexity
- **financial_cost**: Amount at risk relative to available cash

### Message Drafting

Template-based message generation (designed for future OpenAI integration):

```python
from app.preparation.message_drafting import draft_collection_email

message = draft_collection_email(
    client_name="Acme Corp",
    invoice_number="INV-001",
    amount=5000.00,
    due_date="2026-01-01",
    days_overdue=14,
    tone="professional",
    relationship_type="strategic",  # Softens tone automatically
)
# Returns: {"subject": "...", "body": "...", "tone": "professional"}
```

### Linked Actions

The engine detects relationships between prepared actions:

| Link Type | Meaning |
|-----------|---------|
| `resolves` | One action addresses another (e.g., credit draw resolves buffer breach) |
| `conflicts` | Actions are mutually exclusive (e.g., delay vs pay same vendor) |
| `sequence` | Actions must be ordered (e.g., prepare then execute payroll) |

---

## V4 Detection → Preparation Pipeline

The pipeline orchestrates the flow from detection to prepared actions.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Config ──► Detection Engine ──► Filter/Prioritize ──► Preparation      │
│                                                                          │
│  Modes:                                                                  │
│  - FULL: All 12 detection types                                         │
│  - CRITICAL: Only buffer_breach, payroll_safety, statutory              │
│  - TARGETED: Specific detection types only                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Running the Pipeline

```python
from app.engines.pipeline import run_detection_preparation_cycle, PipelineConfig, PipelineMode

# Full pipeline run
result = await run_detection_preparation_cycle(
    db=db,
    user_id=user_id,
)

# Critical-only (fast)
config = PipelineConfig(mode=PipelineMode.CRITICAL)
result = await run_detection_preparation_cycle(db, user_id, config)

# Detection only (no preparation)
config = PipelineConfig(skip_preparation=True)
result = await run_detection_preparation_cycle(db, user_id, config)
```

### Pipeline Result

```python
result = PipelineResult(
    user_id="user-123",
    run_at=datetime.utcnow(),
    mode=PipelineMode.FULL,
    alerts_detected=5,
    alerts_by_severity={"emergency": 1, "this_week": 3, "upcoming": 1},
    alerts_by_type={"late_payment": 2, "buffer_breach": 1, ...},
    actions_prepared=4,
    actions_by_type={"invoice_follow_up": 2, "payroll_contingency": 1, ...},
    linked_action_groups=1,
    detection_duration_ms=45,
    preparation_duration_ms=120,
    total_duration_ms=165,
    errors=[],
)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/pipeline/run` | POST | Run pipeline with config |
| `/api/v1/pipeline/run-critical` | POST | Run critical detections only |
| `/api/v1/pipeline/health` | GET | Pipeline health metrics |
| `/api/v1/pipeline/actions` | GET | Get action queue |
| `/api/v1/pipeline/actions/{id}/approve` | POST | Approve action |
| `/api/v1/pipeline/actions/{id}/skip` | POST | Skip action |

---

## V4 User Configuration

User-specific thresholds for detection and preparation.

### Model

```python
class UserConfiguration:
    user_id: str                          # Primary key (one config per user)

    # Buffer & Runway
    obligations_buffer_amount: Decimal    # Minimum cash buffer (default: 0)
    runway_buffer_months: int             # Runway warning threshold (default: 6)

    # Late Payment
    late_payment_threshold_days: int      # Days to flag overdue (default: 7)

    # Expense Monitoring
    unexpected_expense_threshold_pct: Decimal  # % spike to flag (default: 20%)

    # Safety Mode
    safety_mode: SafetyMode               # conservative/normal/aggressive

    # Payroll Safety
    payroll_check_days_before: int        # Days before to check (default: 7)
    payroll_buffer_percent: Decimal       # Min buffer after payroll (default: 10%)

    # Payment Clustering
    payment_cluster_threshold_pct: Decimal  # Max % due in one week (default: 40%)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/data/user-config/{user_id}` | GET | Get config (creates default if missing) |
| `/api/v1/data/user-config/` | POST | Create config |
| `/api/v1/data/user-config/{user_id}` | PUT | Update config |
| `/api/v1/data/user-config/{user_id}` | DELETE | Delete config |

### Safety Mode Effects

| Setting | Conservative | Normal | Aggressive |
|---------|-------------|--------|------------|
| Buffer threshold | +25% | baseline | -25% |
| Late payment days | -25% | baseline | +25% |
| Expense spike threshold | -25% | baseline | +25% |
| Runway months | +25% | baseline | -25% |

---

## File Structure (Updated)

```
tamio-backend/
├── app/
│   ├── data/
│   │   ├── user_config/          # NEW: User configuration
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # UserConfiguration, SafetyMode
│   │   │   ├── schemas.py        # Pydantic schemas
│   │   │   └── routes.py         # CRUD endpoints
│   │   └── ...
│   │
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── models.py             # DetectionRule, DetectionAlert
│   │   ├── engine.py             # DetectionEngine (12 types)
│   │   ├── scheduler.py          # NEW: APScheduler integration
│   │   └── escalation.py         # NEW: Alert escalation logic
│   │
│   ├── preparation/
│   │   ├── __init__.py
│   │   ├── models.py             # PreparedAction, ActionOption, LinkedAction
│   │   ├── engine.py             # PreparationEngine (all agents)
│   │   ├── context.py            # NEW: Context gathering
│   │   ├── risk_scoring.py       # NEW: Composite risk calculation
│   │   └── message_drafting.py   # NEW: Template-based messages
│   │
│   ├── engines/                  # NEW: Pipeline orchestration
│   │   ├── __init__.py
│   │   ├── pipeline.py           # Detection → Preparation flow
│   │   └── routes.py             # Pipeline API endpoints
│   │
│   └── ...
│
└── migrations/versions/
    ├── ...
    └── 20260110_0002-add_user_configurations_table.py  # NEW
```
