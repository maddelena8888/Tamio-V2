# Tamio V4 Architecture

## Overview

Tamio V4 is a treasury operator that removes the constant vigilance required to manage cash flow. It operates as a continuous loop with four stages:

1. **Continuous Vigilance** - Data integration, normalisation, forecast, detection
2. **Preparation** - Turn detected problems into actionable solutions
3. **Approval** - Action Queue for user review and decision
4. **Execution** - Execute approved actions (manual V1, automated V2)

## Project Structure

```
tamio-backend/
├── app/
│   ├── auth/                 # Authentication (JWT, password reset, demo)
│   ├── data/                 # Core domain entities
│   │   ├── clients/          # Revenue sources
│   │   ├── expenses/         # Expense buckets
│   │   ├── obligations/      # 3-layer obligation architecture
│   │   ├── balances/         # Cash accounts
│   │   ├── users/            # User profiles
│   │   ├── events/           # Cash events
│   │   └── exchange_rates/   # Multi-currency support
│   │
│   ├── detection/            # [V4 NEW] Stage 1.3 - Detection Monitoring
│   │   ├── models.py         # DetectionRule, DetectionAlert
│   │   ├── engine.py         # DetectionEngine - runs detection rules
│   │   └── rules.py          # Default detection rule configurations
│   │
│   ├── preparation/          # [V4 NEW] Stage 2 - Work Preparation
│   │   ├── models.py         # PreparedAction, ActionOption, LinkedAction
│   │   └── engine.py         # PreparationEngine - creates prepared actions
│   │
│   ├── actions/              # [V4 NEW] Stage 3 - Action Queue API
│   │   ├── routes.py         # API endpoints for action queue
│   │   └── schemas.py        # Pydantic schemas
│   │
│   ├── execution/            # [V4 NEW] Stage 4 - Execution
│   │   ├── models.py         # ExecutionRecord
│   │   └── service.py        # ExecutionService - handles action execution
│   │
│   ├── normalisation/        # [V4 NEW] Stage 1.2 - Data Normalisation
│   │   └── __init__.py       # Placeholder for normalisation agents
│   │
│   ├── forecast/             # [FROM V3] 13-week cash flow engine
│   ├── scenarios/            # [FROM V3] What-if analysis
│   ├── integrations/         # [FROM V3] Integration mapping
│   └── xero/                 # [FROM V3] Xero OAuth & sync
│
tamio-frontend/
├── src/
│   ├── pages/
│   │   ├── ActionQueue.tsx   # [V4 NEW] Primary interface
│   │   ├── Dashboard.tsx     # [MOVED] Secondary, shows stats + forecast
│   │   └── ...               # Other pages retained from V3
│   │
│   ├── lib/api/
│   │   ├── actions.ts        # [V4 NEW] Action queue API client
│   │   └── ...               # Other API modules from V3
```

## V4 Data Model

### Detection Layer

```
DetectionRule
├── id, user_id
├── detection_type (enum)
├── name, description
├── thresholds (JSON)
└── enabled

DetectionAlert
├── id, user_id, rule_id
├── detection_type, severity (emergency/this_week/upcoming)
├── status (active/acknowledged/preparing/resolved/dismissed)
├── title, description, context_data (JSON)
├── cash_impact, urgency_score
├── deadline, escalation_count
└── → PreparedAction[]
```

### Preparation Layer

```
PreparedAction
├── id, user_id, alert_id
├── action_type (enum)
├── status (pending_approval/approved/edited/overridden/skipped/executed)
├── problem_summary, problem_context
├── deadline
└── → ActionOption[]

ActionOption
├── id, action_id
├── title, description
├── risk_level (low/medium/high)
├── is_recommended
├── reasoning (JSON array)
├── risk_score, relationship_risk, operational_risk, financial_cost
├── cash_impact, impact_description
├── prepared_content (JSON)
└── success_probability

LinkedAction
├── action_id, linked_action_id
├── link_type (resolves/conflicts/sequence)
└── link_reason
```

### Execution Layer

```
ExecutionRecord
├── id, user_id, action_id, option_id
├── method (manual/automated)
├── result (success/partial/failed/pending)
├── executed_content (JSON)
├── external_reference, external_system
└── notes
```

## Detection Types

| Type | Description | Default Threshold |
|------|-------------|-------------------|
| `late_payment` | Invoices overdue | 7 days |
| `unexpected_revenue` | Payment variance vs invoice | 10% |
| `unexpected_expense` | Expense spike vs average | 20% |
| `client_churn` | Revenue at risk | 5% |
| `payment_timing_conflict` | Obligation clustering | 40% of cash |
| `vendor_terms_expiring` | Payment terms near due | 3 days |
| `statutory_deadline` | Tax/regulatory deadlines | 14/7/3 days |
| `buffer_breach` | Cash below target buffer | 80%/50% warning/critical |
| `runway_threshold` | Runway below threshold | 6/3 months |
| `payroll_safety` | Payroll coverage at risk | 7 days before |

## Action Types

| Type | Description |
|------|-------------|
| `invoice_follow_up` | Collection email for overdue invoice |
| `payment_reminder` | Soft reminder before due date |
| `collection_escalation` | Formal demand letter |
| `payment_batch` | Vendor payment batch |
| `vendor_delay` | Request payment extension |
| `payment_prioritization` | Resequence clustered payments |
| `payroll_contingency` | Options when payroll at risk |
| `payroll_confirmation` | Confirm payroll is covered |
| `excess_cash_allocation` | Allocate surplus cash |
| `credit_line_draw` | Draw from credit facility |
| `invoice_generation` | Prepare invoice draft |
| `statutory_payment` | Prepare statutory payment |

## API Endpoints

### Action Queue (V4 New)

```
GET    /api/actions/queue              # Get full queue by urgency
GET    /api/actions/{id}               # Get single action
POST   /api/actions/{id}/approve       # Approve with selected option
POST   /api/actions/{id}/execute       # Mark as executed
POST   /api/actions/{id}/skip          # Skip (defer)
POST   /api/actions/{id}/override      # Override (handle manually)
GET    /api/actions/{id}/artifacts     # Get execution artifacts
GET    /api/actions/execution/queue    # Get approved actions pending execution
GET    /api/actions/execution/activity # Get recent execution history
```

## UI Flow

### V4 Primary Flow

```
User logs in
    ↓
Action Queue (landing page)
    ├── Emergency actions (red) - Must act today
    ├── This Week actions (yellow) - Needs attention soon
    └── Upcoming actions (green) - Monitoring only
    ↓
User reviews action card
    ├── Problem summary + context
    ├── Options with reasoning
    │   ├── Option 1 (Recommended) - View prepared content
    │   ├── Option 2 - View prepared content
    │   └── Option 3 - View prepared content
    └── Actions: Approve / Edit / Skip / Override
    ↓
Approved action → Execution Queue
    ├── Copy prepared content (email, CSV)
    ├── Execute externally (V1)
    └── Mark as executed
```

### Navigation

```
[V4 Navigation]
├── Action Queue (/)          ← PRIMARY
├── Dashboard (/dashboard)    ← Stats, forecast chart, flags
├── Forecast (/scenarios)     ← What-if analysis
├── Clients & Expenses        ← Data management
└── Settings
```

## Reused from V3

| Component | Status | Notes |
|-----------|--------|-------|
| Auth system | ✅ Reused | JWT + demo accounts |
| 3-layer obligations | ✅ Reused | Agreement → Schedule → Event |
| Forecast engine | ✅ Reused | 13-week with confidence |
| Scenario pipeline | ✅ Reused | Can power "options" |
| Integration mapping | ✅ Reused | Xero extensible |
| Xero sync | ✅ Reused | Bi-directional |
| Frontend API client | ✅ Reused | Type-safe |
| shadcn/ui components | ✅ Reused | All UI components |

## Next Steps

1. **Create Alembic migration** for V4 tables (detection_rules, detection_alerts, prepared_actions, action_options, linked_actions, execution_records)

2. **Wire up detection engine** to run:
   - On schedule (daily)
   - After data sync
   - On dashboard load

3. **Connect preparation engine** to create PreparedActions when DetectionAlerts fire

4. **Connect Action Queue UI** to real API (currently uses mock data)

5. **Add notification system** for emergency alerts

6. **Implement V2 automated execution** with user-defined rules
