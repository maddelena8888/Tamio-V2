# Tamio Product Architecture

## Overview

Tamio is a treasury operator that removes the constant vigilance required to manage cash flow. It watches what's happening, detects problems before they become crises, prepares the work, and executes when you're ready.

### Target Users

Finance managers at SMEs ($3-50M ARR) with unpredictable cash flow - particularly service providers, agencies, and construction firms operating on projects, retainers, or usage-based pricing.

### Problem Statement

**Deep Pain**: Not being able to make payroll or essential expenses, causing the entire operation to halt.

**Root Causes**:

1. **Structural**: Cash enters the business in irregular, delayed, and uncertain lumps, while cash leaves on fixed, non-negotiable schedules. Timing gaps determine survival. Revenue is probabilistic. Obligations are deterministic.

2. **Operational (Human)**: Treasury depends on people to continuously monitor, prioritize, and intervene - introducing bias, inconsistency, and a human control loop that breaks as decision frequency and complexity increase. Cash is managed episodically in a continuous-risk environment.

3. **Fragmentation**: Insight, decision, and execution live in different places. Forecasts in spreadsheets, AR/AP in accounting tools, decisions in Slack, email, or memory. By the time action happens, conditions have already changed.

---

## Technology Stack

### Frontend
- React with TypeScript
- Vite build system
- TailwindCSS + shadcn/ui components
- Chart.js for data visualization

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with AsyncPG
- **ORM**: SQLAlchemy (Async)
- **Migrations**: Alembic
- **Authentication**: JWT tokens
- **Task Scheduling**: APScheduler
- **AI/LLM**: Anthropic Claude (Haiku for fast responses, Opus for complex reasoning)

### External Integrations
- **Xero API**: Accounting data synchronization (EU)
- **Open Banking**: Bank balance feeds (Yapily for EU, planned)
- **Exchange Rates**: ECB API for currency conversion

---

## Core Architecture: The Continuous Loop

Tamio operates as a continuous loop with four stages:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CONTINUOUS LOOP                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────┐ │
│   │   STAGE 1    │     │   STAGE 2    │     │   STAGE 3    │     │STAGE 4 │ │
│   │  VIGILANCE   │────▶│ PREPARATION  │────▶│   APPROVAL   │────▶│EXECUTE │ │
│   │              │     │              │     │              │     │        │ │
│   │ • Data Sync  │     │ • Generate   │     │ • Action     │     │ • Send │ │
│   │ • Normalize  │     │   Options    │     │   Queue      │     │ • Pay  │ │
│   │ • Forecast   │     │ • Draft Work │     │ • Review     │     │ • Mark │ │
│   │ • Detect     │     │ • Score Risk │     │ • Approve    │     │   Done │ │
│   └──────────────┘     └──────────────┘     └──────────────┘     └────────┘ │
│         │                                                              │     │
│         └──────────────────────────────────────────────────────────────┘     │
│                              Feedback Loop                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Continuous Vigilance

### 1.1 Data Integration

**Location**: `tamio-backend/app/xero/`, `tamio-backend/app/integrations/`

| Data Source | Region | Integration |
|-------------|--------|-------------|
| Bank Balances | EU | Yapily (Open Banking, planned) |
| Bank Balances | UAE | Manual entry |
| AR/AP | EU | Xero |
| AR/AP | UAE | Odoo, Zoho (planned) |
| Payroll Schedule | All | Manual / Integration |
| Obligation Registry | All | Manual entry |
| Exchange Rates | All | ECB API (automated) |

### 1.2 Data Normalization

Raw data from bank feeds, accounting systems, and payroll arrives in different formats. The normalization layer transforms everything into a single, consistent canonical structure.

**Location**: `tamio-backend/app/xero/sync_service.py`, `tamio-backend/app/data/`

#### Normalization Agents

| Workflow | Approach | Purpose |
|----------|----------|---------|
| Transaction categorization | AI/LLM | Classify transactions as revenue, expense, transfer, or internal |
| Vendor/client name matching | AI/LLM | Standardize entity names across systems via fuzzy matching |
| Invoice/bill parsing | AI/LLM (OCR) | Extract structured data from invoices and bills |
| Payment term extraction | Hybrid | Identify payment deadlines and grace periods |
| Duplicate detection | Automation | Prevent double-counting transactions |
| Currency normalization | Automation | Convert multi-currency to base currency |
| Date/amount standardization | Automation | Ensure consistent formats |

#### Canonical Data Model

The normalized data is organized around three core questions:
- **WHY** → Agreements define why cash is expected or required
- **WHEN** → Schedules define when it should occur
- **REALITY** → Executions record what actually happened

**Core Entities**:

| Entity | Purpose | Key Fields |
|--------|---------|------------|
| `CashEvent` | Single time-based cash movement (forecast unit) | direction, date, amount, currency, confidence, category, account |
| `Client` | Revenue origin + payment behavior | name, avg_payment_delay_days, relationship_type, revenue_percent, risk_level |
| `ExpenseBucket` (Vendor) | Payee + flexibility context | name, payment_terms, flexibility_level, criticality, delay_history |
| `ObligationAgreement` | Why cash is expected/required | type, amount_model, payment_terms, start/end_date |
| `ObligationSchedule` | When payment is due | due_date, amount, status, days_overdue |
| `PaymentEvent` | Actual cash movement executed | amount, payment_date, account, variance_vs_expected |
| `DetectionRule` | User-defined thresholds for triggers | rule_type, thresholds, enabled |
| `DetectionAlert` | Triggered alerts with severity | alert_type, severity, context_data, status |
| `PreparedAction` | Work prepared by agents | action_type, status, content, risk_score, reasoning |
| `ActionOption` | Solution options with risk scores | action_id, risk_level, prepared_content |
| `ExecutionRecord` | Audit trail of executed actions | action_id, method, result, executed_at |
| `AuditLog` | Field-level change tracking | entity_type, field_name, old_value, new_value |
| `ExchangeRate` | Currency conversion rates | from_currency, to_currency, rate, effective_date |

### 1.3 Forecast Engine

**Location**: `tamio-backend/app/forecast/engine_v2.py`

Tamio generates a rolling 13-week cash flow forecast computed on-the-fly from three core inputs:

1. **Starting Cash** — Sum of all connected cash account balances
2. **Cash In** — Revenue from clients (retainers, projects, usage-based, outstanding invoices)
3. **Cash Out** — Recurring expenses (payroll, subscriptions, rent, etc.)

#### Calculation Logic

For each week, the engine:
- Calculates invoice timing (e.g., invoice on the 1st)
- Applies payment terms (e.g., Net 30)
- Considers client type (retainer = predictable; project = milestone-based; usage = variable)
- Factors expense due day and frequency

**Output per week**:
- Cash in / Cash out
- Net change
- Running balance

#### Confidence Scoring

Every forecast line item receives a confidence rating:

| Level | Weight | Criteria |
|-------|--------|----------|
| **HIGH** | 100% | Linked to repeating invoice/bill in Xero |
| **MEDIUM** | 80% | Synced contact exists in accounting system |
| **LOW** | 50% | Manual entry with no integration validation |

```
weighted_score = (high_amount × 1.0 + medium_amount × 0.8 + low_amount × 0.5) / total_amount
```

#### Scenario Analysis

Users can model what-if scenarios that modify the base forecast:
- **Revenue scenarios**: Payment delays, client loss/gain, upsells/downsells
- **Expense scenarios**: New hires, terminations, cost increases/decreases

Scenarios create a modification layer over the base forecast, showing the delta impact on cash position.

#### Scenario Overlay System

**Location**: `tamio-backend/app/scenarios/overlay.py`, `tamio-backend/app/scenarios/commit.py`

Scenarios use a virtual overlay system for "what-if" analysis:

**Key Principles**:
- Scenarios never directly modify canonical data
- All changes are virtual overlays computed on-the-fly
- Only on explicit user confirmation does `commit.py` create actual records

**Overlay Flow**:
```
Base Canonical Data
    ↓
Apply Virtual Deltas (payment delays, amount changes)
    ↓
Compute Modified Forecast
    ↓
User Reviews Impact
    ↓
[If Confirmed] → commit.py creates real ObligationAgreements/Schedules
```

### 1.4 Detection Monitoring

**Location**: `tamio-backend/app/detection/`

The system watches for specific moments when cash problems require action.

#### Detection Types (12 Total)

| Detection Type | Purpose | Default Threshold |
|----------------|---------|-------------------|
| `late_payment` | Detect invoices overdue | 7+ days late |
| `unexpected_revenue` | Identify payment variances | >10% variance |
| `unexpected_expense` | Flag abnormal expense spikes | >20% above 3-month avg |
| `client_churn` | Flag revenue loss from cancellations | Any cancellation |
| `revenue_variance` | Actual vs forecast variance | >15% variance |
| `payment_timing_conflict` | Detect obligation clustering | >40% of cash in one week |
| `vendor_terms_expiring` | Alert before payment due | 3 days before |
| `statutory_deadline` | Tax and regulatory deadlines | 14/7/3 day alerts |
| `buffer_breach` | Cash below threshold | Below buffer amount |
| `runway_threshold` | Months of runway warning | <3 months |
| `payroll_safety` | Payroll coverage check | 7 days before payroll |
| `headcount_change` | New hire detection | Any new payroll entry |

#### Detection Scheduler

**Location**: `tamio-backend/app/detection/scheduler.py`

| Cadence | Detection Types | Frequency |
|---------|-----------------|-----------|
| Critical | payroll_safety, buffer_breach | Every 5 minutes |
| Routine | late_payments, expenses, revenue | Every hour |
| Daily | statutory_deadlines, runway | 6am daily |

#### Alert Severity Levels

| Severity | Definition | User Expectation |
|----------|------------|------------------|
| `critical` | Must act today to prevent failure | Review immediately |
| `high` | Needs attention soon | Review within 2-3 days |
| `medium` | Scheduled for future | Awareness only |
| `low` | Informational | No action needed |

#### Escalation Logic

**Location**: `tamio-backend/app/detection/escalation.py`

Alerts can escalate based on:
- Time proximity to deadline (within 3 days → Emergency)
- Duration without action (2+ days unactioned)
- Late payments affecting payroll (cascade checking)
- Large cash impacts
- Related alert clustering

---

## Stage 2: Work Preparation

**Location**: `tamio-backend/app/preparation/`

When a detection triggers, agents immediately calculate options, rank by risk, draft messages, and queue everything for approval.

### 2.1 Preparation Engine

**Location**: `tamio-backend/app/preparation/engine.py`

The preparation engine uses a 3-step hybrid approach:
1. **Rule-based triggers** activate workflows (deterministic)
2. **Context-aware agents** prepare optimal actions (intelligent)
3. **Priority queue** sequences actions for user (smart ordering)

#### Context Gathering

**Location**: `tamio-backend/app/preparation/context.py`

Every agent receives:

**Core context**:
- Trigger source (which rule fired)
- Current cash position (all accounts)
- Forecast snapshot (next 30 days)
- All pending PreparedActions (conflict detection)

**Entity-specific context**:
- If invoice-related: Client entity (payment pattern, relationship type, revenue %)
- If obligation-related: Vendor entity (flexibility, criticality, past delays)
- If cash-related: UserConfiguration (buffer thresholds, safety mode)

#### Agent Decision Framework

```python
1. Assess severity
   - Calculate impact ($ amount, obligations affected, runway change)
   - Calculate imminence (days until consequence)
   - Calculate criticality (payroll=10, vendor=3)

2. Generate options
   - If shortfall: identify delayable obligations, calculate coverage
   - If overdue: draft message based on relationship context
   - If routine: prepare standard workflow output

3. Rank options (if multiple)
   - Composite risk score = (relationship_risk × 0.4) + (operational_risk × 0.3) + (financial_cost × 0.3)
   - Sort: lowest risk first

4. Prepare content
   - Draft messages using LLM (relationship-appropriate tone)
   - Generate calculations (shortfall amounts, runway impact)
   - Provide reasoning (why this option recommended)

5. Assign urgency
   - Apply escalation rules
   - Create PreparedAction entity
```

### 2.2 Risk Scoring

**Location**: `tamio-backend/app/preparation/risk_scoring.py`

Each action option receives a composite risk score:

```
composite_risk = (relationship_risk × 0.4) + (operational_risk × 0.3) + (financial_cost × 0.3)
```

**Components**:
- **Relationship risk**: Client type, revenue concentration, churn probability
- **Operational risk**: Action type severity, vendor criticality
- **Financial cost**: Interest charges, late fees, potential revenue loss

### 2.3 Action Types (12 Total)

| Action Type | Trigger | Output |
|-------------|---------|--------|
| `invoice_follow_up` | Overdue invoice | Draft email with tone selection |
| `invoice_generation` | Invoice due date | Invoice draft for approval |
| `payment_batch` | Vendor payments due | Optimized payment CSV |
| `vendor_delay` | Cash shortfall | Delay request messages |
| `payroll_contingency` | Payroll at risk | Mitigation options |
| `buffer_response` | Buffer breach | Recovery plan |
| `expense_reduction` | Negative burn | Reduction recommendations |
| `client_risk_response` | Client churn detected | Retention actions |
| `statutory_payment` | Tax deadline | Payment instructions |
| `cash_allocation` | Excess cash | Allocation suggestions |
| `collection_escalation` | Severely overdue | Escalated collection |
| `payment_sequencing` | Clustered obligations | Optimized sequence |

### 2.4 Urgency Tiers

| Tier | Definition | Deadline |
|------|------------|----------|
| Emergency (Red) | Must act today to prevent failure | Within 8 hours |
| This Week (Yellow) | Needs attention soon | Within 7 days |
| Upcoming (Green) | Monitoring, no action needed yet | 7+ days out |

---

## Stage 3: Approval (Action Queue)

**Location**: `tamio-backend/app/actions/`

The Action Queue is the central interface where all prepared work lands for user review.

### 3.1 Queue Structure

Actions are organized by urgency:
- **Emergency** — Must act today
- **This Week** — Review soon
- **Upcoming** — Monitoring only

### 3.2 Action Card Anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│ [Urgency Icon] [Action Type]: [Entity]                           │
│ Deadline: [Time remaining] | Status: Pending                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ PROBLEM                                                          │
│ [Clear 1-2 sentence summary]                                     │
│ [Key context: $ impact, relationships, dependencies]             │
│                                                                   │
│ ─────────────────────────────────────────────────────────────    │
│                                                                   │
│ OPTION 1 (RECOMMENDED)                          [Risk: Low]      │
│ [Action description]                                             │
│ • [Reasoning bullet 1]                                           │
│ • [Reasoning bullet 2]                                           │
│ [Prepared content preview]                                       │
│                                                                   │
│ [View Full Details]  [Approve Option 1]                          │
│                                                                   │
│ ─────────────────────────────────────────────────────────────    │
│                                                                   │
│ OPTION 2                                        [Risk: Medium]   │
│ [Action description]                                             │
│ [View Details]                                                   │
│                                                                   │
│ ─────────────────────────────────────────────────────────────    │
│                                                                   │
│ [Edit] [Override All] [Skip] [Mark Resolved]                     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 3.3 User Actions

| Action | Status Change | What Happens |
|--------|---------------|--------------|
| Approve | pending → approved | Moves to execution queue |
| Edit + Approve | pending → approved | Modified version moves to execution |
| Override | pending → overridden | User handles manually outside Tamio |
| Skip | pending → skipped | Deferred, action archived |
| Deadline expires | pending → expired | Critical actions auto-escalate; routine auto-archive |

### 3.4 Linked Actions

When actions are connected (e.g., invoice chase solves payroll shortage):
- Visually grouped in the queue
- Approving one can resolve the other automatically
- System warns if approving both would conflict

---

## Stage 4: Execution

**Location**: `tamio-backend/app/execution/`

The final stage where approved actions get executed.

### 4.1 V1: Manual Execution

In V1, users execute manually (Tamio prepares, user acts):

```
Approved Action
    ↓
Execution queue (organized by deadline)
    ↓
System provides execution artifacts:
  • Draft messages (copy-paste ready)
  • Payment instructions (ready to upload to bank)
  • Transfer details (amount, account, reference)
    ↓
User executes manually:
  • Sends emails via their email client
  • Uploads payment batch to bank portal
  • Initiates transfers in accounting system
    ↓
User marks complete in Tamio
    ↓
System updates entities
```

### 4.2 V2: Autonomous Execution (Future)

**Location**: `tamio-backend/app/execution/models.py` (ExecutionAutomationRule)

In V2, Tamio can execute autonomously within user-defined rules:

| Action Type | Auto-Execute Option | Notes |
|-------------|---------------------|-------|
| Invoice follow-ups | Auto-send after approval | Exclude strategic clients |
| Payment batches | Auto-submit if < threshold | e.g., < $10,000 |
| Vendor delays | Auto-send to "flexible" vendors | Based on flexibility tag |
| Tax/Statutory | Always manual | Require explicit approval |
| **Payroll** | **LOCKED - Never auto** | Always manual |

### 4.3 Execution Artifacts

**Location**: `tamio-backend/app/execution/service.py`

For each approved action, the system provides:

| Artifact Type | Content |
|---------------|---------|
| Draft Email | Copy-paste ready message with tone |
| Payment CSV | Bank upload format |
| Payment Instructions | Amount, account, reference |
| Talking Points | For phone calls |
| Calculations | Shortfall analysis, runway impact |

---

## TAMI: AI Treasury Assistant

**Location**: `tamio-backend/app/tami/`

TAMI is Tamio's conversational AI assistant that provides natural language access to treasury insights and actions.

### Architecture

**Components**:
- `agent2_responder.py` - Main responder using Anthropic Claude API with function calling
- `context.py` - Loads deterministic context (cash position, alerts, forecast)
- `tools.py` - Function definitions for Claude tool use
- `schemas.py` - Response models

**Model Selection**:
| Model | Use Case |
|-------|----------|
| Claude Haiku | Fast responses, simple queries |
| Claude Opus | Complex reasoning, multi-step analysis |

### Context Payload

Every TAMI response includes:
- Current cash position (all accounts)
- Active detection alerts
- Prepared actions awaiting approval
- 13-week forecast summary
- Recent execution activity

### Capabilities

- Answer questions about cash position and runway
- Explain detection alerts and their implications
- Summarize prepared actions and options
- Provide context for decision-making
- Navigate users to relevant actions

---

## Audit & Compliance

**Location**: `tamio-backend/app/audit/`

Comprehensive audit logging for all data changes.

### Audit Log Structure

| Field | Purpose |
|-------|---------|
| `entity_type` | Table/model being modified |
| `entity_id` | ID of the modified record |
| `field_name` | Specific field changed |
| `old_value` | Previous value |
| `new_value` | New value |
| `source` | api, xero_sync, system, migration, admin |
| `user_id` | Who made the change |
| `extra_data` | IP address, user agent, request ID |

### Use Cases

- Debugging data discrepancies
- Compliance reporting
- Data provenance tracking
- Change attribution

---

## Notifications

**Location**: `tamio-backend/app/notifications/`

Multi-channel notification delivery for alerts and actions.

### Notification Types

| Type | Trigger |
|------|---------|
| `ALERT_EMERGENCY` | Critical detection alert |
| `ALERT_THIS_WEEK` | High-priority alert |
| `ALERT_ESCALATED` | Alert escalated due to inaction |
| `ACTION_READY` | New prepared action available |
| `ACTION_DEADLINE` | Action deadline approaching |
| `ACTION_EXECUTED` | Action completed |
| `SYNC_COMPLETED` | Data sync finished |
| `SYNC_FAILED` | Data sync error |
| `DAILY_DIGEST` | Batched daily summary |

### Channels

| Channel | Status |
|---------|--------|
| Email | Implemented |
| SMS | Planned |
| Push | Planned |
| Slack | Planned |

### User Preferences

- Per-notification-type preferences
- Batch into daily digest option
- Quiet hours support (user's timezone)

---

## Demo & Seed Data

**Location**: `tamio-backend/app/seed/`

### AgencyCo Demo Dataset

Pre-configured demo environment for testing and demonstrations.

**Demo Credentials**:
- Email: `demo@agencyco.com`
- Password: `demo2026`

**Dataset Contents**:
- 15 active clients (mix of retainers and projects)
- $487K cash across 3 bank accounts
- Bi-weekly payroll ($85K)
- 12 vendor obligations (due this/next week)
- 5 overdue invoices (3-14 days late)
- Upcoming tax payment ($22K)
- Pre-configured detection alerts
- Sample prepared actions

### Demo Guard Middleware

**Location**: `tamio-backend/app/middleware/demo_guard.py`

Protects demo accounts from data mutations:
- Allows GET requests
- Allows TAMI chat interactions
- Blocks all create/update/delete operations
- Returns 403 with demo flag explanation

---

## API Endpoints

### Authentication (`/api/v1/auth`)
- POST `/register` - User registration
- POST `/login` - User authentication
- POST `/refresh` - Token refresh
- POST `/forgot-password` - Request password reset
- POST `/reset-password` - Complete password reset

### Data Management (`/api/v1/data`)
- Clients, Employees, Contractors CRUD
- Invoices and Expenses management
- Recurring obligations tracking

### Forecasting (`/api/v1/forecast`)
- GET `/` - Generate 13-week forecast
- GET `/summary` - Forecast summary statistics

### Scenarios (`/api/v1/scenarios`)
- GET `/` - List scenarios
- POST `/` - Create scenario
- POST `/pipeline/run` - Execute scenario pipeline
- GET `/{id}/forecast` - Get scenario forecast

### Detection (`/api/v1/detection`)
- GET `/rules` - List detection rules
- PUT `/rules/{id}` - Update rule thresholds
- GET `/alerts` - List active alerts
- POST `/alerts/{id}/acknowledge` - Acknowledge alert

### Actions (`/api/v1/actions`)
- GET `/queue` - Get action queue (by urgency)
- GET `/{id}` - Get action details with options
- POST `/{id}/approve` - Approve with option selection
- POST `/{id}/execute` - Mark as executed (V1)
- POST `/{id}/skip` - Defer decision
- POST `/{id}/override` - Reject and handle manually
- GET `/{id}/artifacts` - Get execution artifacts
- GET `/execution/queue` - Approved actions pending execution
- GET `/execution/activity` - Recent execution history

### User Configuration (`/api/v1/user-config`)
- GET `/{user_id}` - Get user settings
- PUT `/{user_id}` - Update settings

### Xero Integration (`/api/v1/xero`)
- GET `/auth/url` - Get OAuth URL
- POST `/auth/callback` - OAuth callback
- POST `/sync` - Trigger data sync
- GET `/status` - Sync status

### TAMI (`/api/v1/tami`)
- POST `/chat` - Send message, receive streaming response
- GET `/conversations` - List conversation history
- GET `/conversations/{id}` - Get conversation details

### Notifications (`/api/v1/notifications`)
- GET `/preferences` - Get notification preferences
- PUT `/preferences` - Update preferences
- GET `/history` - Get notification history

### Exchange Rates (`/api/v1/exchange-rates`)
- GET `/` - Get current rates
- GET `/convert` - Convert amount between currencies

### Seed (`/api/v1/seed`)
- POST `/agencyco` - Seed AgencyCo demo data (admin only)

---

## Database Schema

### Core Models

**User & Auth**:
- `User`: Authentication, profile, business settings
- `UserConfiguration`: Detection thresholds, safety mode, buffer settings

**Financial Data**:
- `Client`: Revenue sources with payment behavior
- `ExpenseBucket`: Recurring costs with vendor context
- `ObligationAgreement`: Why cash is expected/required
- `ObligationSchedule`: When payments are due
- `PaymentEvent`: Actual cash movements
- `CashAccount`: Bank account balances

**Detection & Actions**:
- `DetectionRule`: User-configurable detection thresholds
- `DetectionAlert`: Triggered alerts with severity and context
- `PreparedAction`: Work prepared for approval
- `ActionOption`: Multiple options per action with risk scores
- `LinkedAction`: Relationships between actions

**Execution & Audit**:
- `ExecutionRecord`: Audit trail of executed actions
- `ExecutionAutomationRule`: V2 automation configuration
- `AuditLog`: Comprehensive change tracking

**Notifications**:
- `NotificationPreference`: Per-user, per-type delivery preferences
- `NotificationLog`: Sent notification audit trail

**TAMI**:
- `TamiConversation`: Conversation sessions
- `TamiMessage`: Individual messages within conversations

**Integration**:
- `IntegrationMapping`: External system ID mappings
- `ExchangeRate`: Currency conversion rates

### Key Relationships

```
User
 ├── UserConfiguration (1:1)
 ├── Client (1:N)
 │    └── ObligationAgreement (1:N)
 │         └── ObligationSchedule (1:N)
 ├── ExpenseBucket (1:N)
 │    └── ObligationAgreement (1:N)
 │         └── ObligationSchedule (1:N)
 ├── DetectionRule (1:N)
 ├── DetectionAlert (1:N)
 │    └── PreparedAction (1:1)
 │         ├── ActionOption (1:N)
 │         └── ExecutionRecord (1:1)
 ├── NotificationPreference (1:N)
 ├── NotificationLog (1:N)
 ├── TamiConversation (1:N)
 │    └── TamiMessage (1:N)
 └── AuditLog (1:N)
```

---

## User Configuration

**Location**: `tamio-backend/app/data/user_config/`

Users can configure detection sensitivity and thresholds:

| Setting | Default | Description |
|---------|---------|-------------|
| `obligations_buffer_amount` | 3 months | Target cash buffer |
| `runway_buffer_months` | 3 | Minimum runway warning |
| `late_payment_threshold_days` | 7 | Days before flagging overdue |
| `unexpected_expense_threshold_pct` | 20 | % above average to flag |
| `safety_mode` | normal | conservative (0.7x), normal (1.0x), aggressive (1.3x) |
| `payroll_check_days_before` | 7 | Days before payroll to check safety |
| `payroll_buffer_percent` | 10 | Extra buffer for payroll |
| `payment_cluster_threshold_pct` | 40 | % of cash clustering warning |

---

## Security Considerations

- JWT token authentication with refresh
- Secure password hashing (bcrypt)
- CORS configuration for allowed origins
- OAuth 2.0 for Xero integration
- Environment-based configuration
- Database connection pooling with pre-ping
- Audit logging for all changes
- Role-based access (future)

---

## Deployment

- FastAPI ASGI server (Uvicorn)
- PostgreSQL database
- Environment variables for configuration
- Database migrations via Alembic
- Static frontend deployment
- APScheduler for detection jobs

---

## Implementation Status

### Fully Implemented
- Detection Engine (all 12 types)
- Detection Scheduler (critical/routine/daily cadences)
- Alert Escalation Logic
- Preparation Engine (11 action types)
- Risk Scoring System
- Action Queue API
- Execution Service (V1 manual)
- Audit Logging
- User Configuration
- TAMI AI Assistant (Anthropic Claude integration)
- Notification Models & Preferences
- Exchange Rate Service (ECB API)
- Scenario Overlay System
- Scenario Commit Service
- Demo Guard Middleware
- AgencyCo Seed Data
- Password Reset Flow
- Business Profile Onboarding

### Partially Implemented
- Frontend Action Monitor page (functional, needs polish)
- Email notification delivery
- Preparation agents for remaining action types (using generic fallback)

### Not Yet Implemented
- V2 automation execution (auto-send emails, auto-submit payments)
- Open Banking integration (Yapily)
- AI/LLM-based normalization agents
- SMS/Push/Slack notifications
- Role-based access control

---

## Frontend Pages

**Location**: `tamio-frontend/src/pages/`

### Home (`/`)
The primary dashboard combining TAMI chat with urgent actions and KPIs.

**Layout**:
- 60% left: Chat panel with TAMI
- 40% right: Sidebar with urgent actions, KPIs, mini forecast

**Features**:
- Streaming chat responses
- Contextual quick actions from urgent problems
- Inline response cards
- Mini 13-week forecast chart

### Action Monitor (`/action-monitor`)
Kanban-style action workflow interface for Stage 3 of the pipeline.

**Layout**:
- Problem Carousel: Horizontal scrolling problem cards
- Action Kanban Board: 3 columns (Queued | Executing | Completed)

**Features**:
- Drag-and-drop action status management
- Action detail modals with option selection
- Email/payment batch preview
- Execution artifacts display
- Recent activity log

### Dashboard (`/dashboard`)
Traditional dashboard with cash position, forecast chart, and summary metrics.

### Clients & Expenses (`/clients-expenses`)
Data management for clients and expense buckets with obligation tracking.

### Scenarios (`/scenarios`)
What-if scenario modeling with overlay visualization and commit functionality.

### Settings (`/settings`)
User preferences, detection thresholds, and integration management.

### Onboarding Flow

| Step | Page | Purpose |
|------|------|---------|
| 1 | `/onboarding/business-profile` | Company profile collection |
| 2 | `/onboarding` | Data source connection (Xero) |

---

## Demo Scenarios

### Prototype Company: AgencyCo
$8M ARR marketing agency with project-based and retainer revenue

**Pre-loaded data**:
- 15 active clients (mix of retainers and projects)
- $487K cash across 3 bank accounts
- Bi-weekly payroll ($85K, due Friday)
- 12 vendor obligations due this/next week
- 5 overdue invoices (3-14 days late)
- Upcoming tax payment ($22K, due in 18 days)

### Scenario 1: Monday Morning Dashboard
User sees instant clarity:
- Current cash: $487K
- Payroll Friday: Safe ($47K buffer)
- Runway: 4.2 months
- Flags: Client payment delayed, 3 invoices overdue
- Action queue: 2 urgent, 1 this week

**Value**: 45 minutes → 2 minutes

### Scenario 2: Cash Shortfall Alert
Client payment delayed → Payroll at risk

System prepares 3 options:
1. **Delay Vendor B** ($12K) - Low risk, within terms
2. **Chase Client A** early - Medium risk, strategic client
3. **Draw credit line** ($15K) - Low risk, $180 interest

**Value**: 1-2 hours of work → 2 minutes (review + approve)

### Scenario 3: Invoice Follow-Up Queue
3 overdue invoices with context-aware drafts:
- Client X (strategic) → Soft tone
- Client Y (transactional, always late) → Professional tone
- Client Z (small, very late) → Firmer tone

**Value**: 30 minutes drafting → 3 minutes (review + approve)

---

## Module Directory Reference

### Backend (`tamio-backend/app/`)

| Module | Location | Purpose |
|--------|----------|---------|
| Actions | `app/actions/` | Action Queue API endpoints |
| Agents | `app/agents/` | Agent architecture documentation |
| Audit | `app/audit/` | Audit logging service |
| Auth | `app/auth/` | Authentication and user management |
| Data | `app/data/` | Core data models (clients, expenses, obligations) |
| Detection | `app/detection/` | Detection engine, rules, scheduler |
| Execution | `app/execution/` | Execution service and automation |
| Forecast | `app/forecast/` | Forecast engine v2 |
| Integrations | `app/integrations/` | Integration mappings and services |
| Middleware | `app/middleware/` | Request middleware (demo guard) |
| Notifications | `app/notifications/` | Notification service and templates |
| Preparation | `app/preparation/` | Preparation engine and risk scoring |
| Scenarios | `app/scenarios/` | Scenario pipeline, overlay, and commit |
| Seed | `app/seed/` | Demo data generation |
| Services | `app/services/` | Shared business services |
| TAMI | `app/tami/` | AI assistant |
| Xero | `app/xero/` | Xero integration and sync |

### Frontend (`tamio-frontend/src/`)

| Module | Location | Purpose |
|--------|----------|---------|
| Pages | `src/pages/` | Route components |
| Components | `src/components/` | Reusable UI components |
| Contexts | `src/contexts/` | React context providers |
| Lib/API | `src/lib/api/` | API client functions |
| Layouts | `src/layouts/` | Page layout components |