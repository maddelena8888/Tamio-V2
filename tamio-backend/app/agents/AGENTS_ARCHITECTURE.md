# Tamio Agent Architecture

This document defines the scope, responsibilities, and technical specifications for each agent in the Tamio cash flow management system.

**Last Updated**: 2026-01-12

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent 1: Forecast Engine](#agent-1-forecast-engine)
3. [Agent 2: Cash Flow Vigilance Agent](#agent-2-cash-flow-vigilance-agent)
4. [Agent 3: AR & Invoice Agent](#agent-3-ar--invoice-agent)
5. [Agent 4: Vendor & Payment Agent](#agent-4-vendor--payment-agent)
6. [Agent 5: Payment Batch Sequencer](#agent-5-payment-batch-sequencer)
7. [Agent 6: Excess Cash Allocator](#agent-6-excess-cash-allocator)
8. [Agent Dependencies & Interactions](#agent-dependencies--interactions)
9. [Implementation Priority](#implementation-priority)

---

## Architecture Overview

### Agent System Design

```
                                    ┌─────────────────────────────────────────┐
                                    │           USER DASHBOARD                 │
                                    └─────────────────┬───────────────────────┘
                                                      │
                    ┌─────────────────────────────────┼─────────────────────────────────┐
                    │                                 │                                 │
                    ▼                                 ▼                                 ▼
        ┌───────────────────┐           ┌───────────────────┐           ┌───────────────────┐
        │  FORECAST ENGINE  │           │   VIGILANCE AGENT │           │ EXCESS ALLOCATOR  │
        │   (Agent 1)       │◄─────────►│     (Agent 2)     │           │    (Agent 6)      │
        │                   │           │                   │           │                   │
        │ 13-week forecast  │           │ Monitors for      │           │ Surplus cash      │
        │ Confidence bands  │           │ shortfalls        │           │ allocation        │
        │ Risk periods      │           │ Detects anomalies │           │                   │
        └─────────┬─────────┘           └─────────┬─────────┘           └───────────────────┘
                  │                               │
                  │                               │ Triggers when
                  │                               │ issues detected
                  │                               ▼
                  │               ┌───────────────────────────────────────┐
                  │               │         PREPARATION AGENTS            │
                  │               ├───────────────────────────────────────┤
                  │               │                                       │
                  │               │  ┌─────────────┐  ┌─────────────────┐ │
                  └──────────────►│  │  AR/Invoice │  │ Vendor/Payment  │ │
                                  │  │  (Agent 3)  │  │   (Agent 4)     │ │
                                  │  └─────────────┘  └─────────────────┘ │
                                  │                                       │
                                  │  ┌─────────────────────────────────┐  │
                                  │  │    Payment Batch Sequencer      │  │
                                  │  │          (Agent 5)              │  │
                                  │  └─────────────────────────────────┘  │
                                  │                                       │
                                  └───────────────────────────────────────┘
                                                      │
                                                      ▼
                                          ┌───────────────────┐
                                          │   ACTION QUEUE    │
                                          │ (User Approval)   │
                                          └─────────┬─────────┘
                                                    │
                                                    ▼
                                          ┌───────────────────┐
                                          │    EXECUTION      │
                                          │    SERVICE        │
                                          └───────────────────┘
```

### Agent Categories

| Category | Agents | Purpose |
|----------|--------|---------|
| **Core Intelligence** | Forecast Engine (1) | Continuous cash position projection |
| **Monitoring** | Cash Flow Vigilance (2) | Real-time risk detection |
| **Preparation** | AR/Invoice (3), Vendor/Payment (4), Batch Sequencer (5) | Generate actionable work items |
| **Optimization** | Excess Cash Allocator (6) | Surplus deployment recommendations |

### Intelligence Types

| Type | Description | Used By |
|------|-------------|---------|
| **Rules** | Deterministic logic with configurable thresholds | All agents |
| **Statistical** | Pattern analysis, historical averages, deviation detection | Agents 1, 2 |
| **Optimization** | Constraint-based sequencing and prioritization | Agents 4, 5 |
| **AI/LLM** | Natural language generation for messages/emails | Agents 3, 4, 6 |

---

## Agent 1: Forecast Engine

### Purpose

Projects your 13-week cash position by analyzing all expected inflows and outflows, applying probability weights to uncertain revenue, and flagging weeks where you'll breach your buffer threshold.

### Scope

#### What It Does

1. **Aggregates all cash flow data**
   - Current bank balances across all accounts
   - Scheduled obligations (payroll, vendor payments, tax deadlines)
   - Expected revenue from invoices (with payment delay probabilities)
   - Recurring expenses (subscriptions, rent, salaries)

2. **Applies intelligent forecasting**
   - Uses client payment patterns to adjust expected receipt dates
   - Accounts for seasonal variations in revenue/expenses
   - Applies confidence scores to uncertain inflows (80% likely vs. 50% likely)

3. **Identifies risk periods**
   - Flags weeks where ending balance drops below buffer threshold
   - Highlights obligation clustering (too many payments same week)
   - Shows runway calculation (weeks of cash remaining at current burn)

4. **Updates continuously**
   - Recalculates when new payments arrive
   - Adjusts when invoices are sent or obligations added
   - Responds to actual vs. expected variances

#### What It Prepares

**13-week rolling forecast chart:**
- Projected ending balance per week
- Cash buffer minimum line
- Confidence bands (best case / worst case scenarios)

**Week-by-week breakdown table:**
- Starting balance
- Expected inflows (by category)
- Expected outflows (by category)
- Ending balance

**Risk flags:**
- Weeks breaching buffer threshold
- Runway warning if below 3 months
- Obligation clustering alerts

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Rules + Statistical Models) |
| **Core Calculation** | Deterministic cash flow math |
| **Probability Adjustments** | Based on historical payment patterns |
| **Risk Flagging** | Rule-based thresholds |

### Run Schedule

| Trigger | Frequency |
|---------|-----------|
| Real-time recalculation | When data changes (payment received, invoice sent) |
| Scheduled refresh | Every 6 hours for probability updates |
| On-demand | When user views Dashboard or Forecast page |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Forecast accuracy | Actual vs. predicted variance (%) |
| Confidence level | High (80%+), Medium (60-80%), Low (<60%) |
| Buffer status | Safe / Caution / At Risk |
| Runway | X.X months |
| Next risk period | Week X (if applicable) |
| Last updated | Timestamp |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `CashAccount` | Current balances |
| `ObligationSchedule` | Upcoming inflows/outflows |
| `ObligationAgreement` | Obligation types and base amounts |
| `Client` | Payment pattern data (avg_payment_delay_days) |
| `PaymentEvent` | Historical payment data for pattern analysis |
| `UserConfiguration` | Buffer thresholds, safety mode |

### Integration Points

- **Provides data to**: Vigilance Agent (2), Dashboard UI
- **Receives triggers from**: Data layer (new payments, invoices, obligations)
- **Outputs**: ForecastEvent objects, risk alerts

---

## Agent 2: Cash Flow Vigilance Agent

### Purpose

Continuously monitors your cash position against upcoming obligations and buffer thresholds, detecting potential shortfalls before they become crises.

### Scope

#### What It Does

1. **Monitors buffer health**
   - Tracks daily bank balances vs. minimum buffer threshold
   - Calculates days until buffer breach (forward-looking)
   - Applies payment delay probabilities to expected receipts
   - Flags when buffer will drop below threshold within 7 days

2. **Tracks payroll safety**
   - Runs 7 days before each payroll date
   - Calculates available cash after all pre-payroll obligations
   - Applies client payment delay probabilities to expected receipts
   - Determines green (safe, $50K+ buffer) / yellow (tight, $0-50K) / red (shortfall)

3. **Watches revenue patterns**
   - Tracks invoice payment timing vs. client's historical pattern
   - Flags payments delayed beyond normal range (7+ days late)
   - Detects potential churn (revenue drop >20% from baseline)
   - Monitors concentration risk (single client >20% of revenue)

4. **Detects obligation clustering**
   - Identifies weeks with unusually high payment concentration
   - Calculates if multiple large obligations will breach buffer
   - Flags potential timing conflicts (payroll + tax same week)

#### What It Detects

| Alert Type | Description |
|------------|-------------|
| Buffer breach imminent | 3-7 days ahead |
| Payroll at risk | Insufficient funds for Friday payroll |
| Late payment | Client payment overdue beyond normal pattern |
| Churn risk | Client revenue at risk within 30 days |
| Obligation clustering | Too many payments same week |
| Concentration risk | Single client dependency too high |
| Unexpected expense spike | Expense >30% above forecast |

#### What It Prepares

**Detection alerts with context:**
- Problem description (e.g., "Payroll at risk: $15K shortfall")
- Root cause analysis (e.g., "Client A payment delayed 2 weeks")
- Impact assessment (e.g., "Affects Friday payroll, $85K due")
- Urgency level (Emergency / This Week / Upcoming)
- Deadline (e.g., "Must act by Wednesday 5pm")

**Triggers preparation agents when action needed**

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Rules + Statistical Analysis) |
| **Buffer Calculations** | Rule-based thresholds |
| **Payment Pattern Analysis** | Statistical deviation detection |
| **Probability Weighting** | Historical pattern matching |
| **Risk Scoring** | Composite formula (imminence x impact x likelihood) |

### Run Schedule

| Check Type | Frequency |
|------------|-----------|
| Buffer monitoring | Every 6 hours |
| Payroll check | 7 days before payroll date, then daily until payroll |
| Revenue monitoring | Daily at 6am |
| Obligation clustering | When new obligations added or forecast updated |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Checks performed | Count per week |
| Alerts created | Count per week by type |
| Alert resolution rate | % of alerts that resulted in approved actions |
| False positive rate | % of alerts where no action was needed |
| Average detection lead time | Days before event that alert was raised |
| Last run | Timestamp per check type |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `CashAccount` | Current balances |
| `ObligationSchedule` | Upcoming payments (inflows and outflows) |
| `Client` | Payment patterns, relationship type, revenue % |
| `ExpenseBucket` | Expense categories, criticality |
| `UserConfiguration` | Thresholds, safety mode |
| `DetectionRule` | User-customized detection thresholds |

### Integration Points

- **Receives data from**: Forecast Engine (1)
- **Triggers**: AR/Invoice Agent (3), Vendor/Payment Agent (4)
- **Outputs**: DetectionAlert objects

---

## Agent 3: AR & Invoice Agent

### Purpose

Manages the full invoice lifecycle: calculates amounts owed, generates invoice drafts, and drafts collection emails for overdue payments with tone calibrated to client relationship strength.

### Scope

#### What It Does

1. **Invoice calculation & generation**
   - Triggers when invoice due date arrives (based on contract terms)
   - Calculates amount owed:
     - Retainer contracts: Fixed monthly amount
     - Hourly contracts: Hours tracked x hourly rate
     - Milestone contracts: Agreed milestone amount
   - Generates invoice draft in Xero/QuickBooks with:
     - Correct line items and amounts
     - Payment terms (Net-30, Net-60, etc.)
     - Due date calculated from invoice date + terms
   - Queues draft for finance lead review before sending

2. **Payment tracking**
   - Monitors when invoices are sent vs. when payments arrive
   - Builds client payment pattern profiles (e.g., "pays 5 days late on average")
   - Updates forecast with actual payment date once received
   - Calculates variance: expected vs. actual payment timing

3. **Collection follow-up**
   - Detects overdue invoices (7+ days beyond due date)
   - Retrieves client context:
     - Payment history (average delay days)
     - Relationship type (strategic / managed / transactional)
     - Revenue percentage (what % of your revenue is this client?)
     - Past collection interactions
   - Generates collection email with calibrated tone:
     - **Soft tone** for strategic clients (top 20% revenue): "Just following up on the invoice we sent..."
     - **Professional tone** for managed clients: "We haven't received payment yet for invoice..."
     - **Direct tone** for transactional clients: "Invoice #1234 is now 12 days overdue..."
   - Queues draft email for review before sending

4. **Escalation logic**
   - If invoice affects payroll safety (part of expected receipts before payroll), escalates to Emergency
   - If client has never been late before, flags as unusual behavior
   - If payment delay exceeds 2x normal pattern, suggests escalation options

#### What It Prepares

**For invoice generation:**
- Draft invoice in accounting system with calculated amounts
- Invoice details summary (client, amount, due date, items)

**For collection follow-up:**
- Draft collection email with:
  - Subject line (personalized)
  - Email body (tone-calibrated)
  - Invoice attachment reference
  - Payment instructions
- Reasoning explanation:
  - "Soft tone recommended: Client A is 18% of revenue, historically pays 3 days late, this is day 7"
- Risk assessment:
  - Relationship risk (low / medium / high)
  - Financial impact ($X overdue, affects payroll: yes/no)

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Rules + AI/LLM) |
| **Invoice Calculation** | Rule-based (contract terms) |
| **Payment Pattern Analysis** | Statistical (historical data) |
| **Collection Message Drafting** | AI/LLM (GPT-4) |
| **Tone Calibration** | Based on relationship type + revenue % + delay severity |
| **Personalization** | References past interactions, account status |
| **Context Awareness** | Knows if you've chased before, when last contacted |

### Run Schedule

| Task | Trigger |
|------|---------|
| Invoice generation | When invoice due date arrives (per client contract schedule) |
| Invoice check | Daily at 9am for invoices due that day |
| Collection follow-up | Daily at 9am |
| Overdue detection | Checks all open invoices for overdue status (>7 days past due date) |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Invoices generated this month | Count |
| Invoices awaiting review | Count |
| Average time to send | Invoice date to actually sent (X days) |
| Collection emails drafted this month | Count |
| Collection success rate | % of follow-ups resulting in payment within 7 days |
| Average days to payment | After first follow-up |
| Overdue AR balance | Total $ overdue |
| Last run | Timestamp |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `ObligationAgreement` | Contract terms, billing frequency |
| `ObligationSchedule` | Invoice due dates, amounts |
| `Client` | Relationship type, payment patterns, revenue % |
| `PaymentEvent` | Payment history for pattern analysis |
| `IntegrationMapping` | Xero/QB contact IDs |

### Integration Points

- **Triggered by**: Vigilance Agent (2) for overdue detection, scheduled for invoice generation
- **Integrates with**: Xero, QuickBooks (via integration layer)
- **Outputs**: PreparedAction (invoice draft, collection email)

---

## Agent 4: Vendor & Payment Agent

### Purpose

When cash is tight, ranks vendors by delay risk and drafts postponement messages that preserve relationships while buying you time. Also confirms payment details for statutory obligations.

### Scope

#### What It Does

1. **Vendor delay triage (when shortfall detected)**
   - Triggered by: Payroll safety alert (red status) or buffer breach detection
   - Analyzes all vendors with payments due in next 7-14 days
   - Calculates composite risk score for each vendor:
     - **Payment terms remaining**: (Current day / Total terms) → Day 22 of Net-30 = 73% = safer to delay
     - **Operational criticality**: Payroll processor = critical (10/10), Marketing agency = flexible (3/10)
     - **Past delay tolerance**: Delayed before without issue = flexible, Never delayed = unknown risk
     - **Relationship strength**: Long-term vendor (3+ years) = safer, New vendor = riskier
   - Ranks vendors from safest to riskiest to delay
   - For top 3 safest vendors, prepares:
     - New payment date (stays within payment terms)
     - Draft delay message with reasoning
     - Impact calculation (how much cash freed up, new buffer amount)

2. **Delay message drafting**
   - Generates vendor-specific delay message:
     - Professional tone (maintains relationship)
     - Clear reasoning (client payment delay)
     - Specific new payment date (not vague "soon")
     - Confirmation request ("Please confirm receipt")
   - Example: "Hi Sarah, due to a client payment delay, we'll process your invoice next Wednesday (Jan 15) instead of this Wednesday. This keeps us within Net-30 terms. Please confirm receipt."

3. **Payment batch timing optimization**
   - When multiple vendor payments due same week, calculates optimal sequence
   - Spreads payments across week to maintain buffer
   - Prioritizes critical vendors (payroll, utilities) early in week
   - Delays flexible vendors to end of week
   - Shows reasoning: "Pay Vendor A Monday, Vendor B Wednesday to maintain $20K buffer"

4. **Statutory obligation confirmation**
   - Triggered 7 days before tax/regulatory payment deadlines
   - Retrieves payment amount and recipient details
   - Confirms cash available for payment
   - Prepares payment instructions:
     - Amount, account details, payment reference
     - Deadline (date + time if relevant)
     - Consequence warning if missed ("Late penalty: $500")
   - Queues for approval/submission

#### What It Prepares

**For vendor delays:**
- Ranked delay options (typically 3 options):
  - Option 1: Delay Vendor B ($12K, Risk: Low)
  - Option 2: Delay Vendor C ($8K, Risk: Low)
  - Option 3: Delay Vendor D ($15K, Risk: Medium)
- For each option:
  - Draft delay message (email ready to send)
  - Risk assessment reasoning
  - Impact on buffer: "Frees $12K, new buffer: $18K"
  - New payment date

**For payment batching:**
- Optimized payment schedule (which vendors to pay which days)
- Reasoning for sequence
- Cash flow impact visualization (buffer each day of week)

**For statutory obligations:**
- Payment instructions (amount, account, reference)
- Deadline confirmation
- Submission checklist

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Algorithm + AI/LLM) |
| **Risk Scoring Formula** | `(terms_remaining × 0.3) + (1 - criticality × 0.4) + (delay_history × 0.2) + (relationship_strength × 0.1)` |
| **Payment Sequencing** | Optimization algorithm (maintains buffer while respecting deadlines) |
| **Message Drafting** | AI/LLM (GPT-4) with context: vendor relationship, payment history, terms |

### Run Schedule

| Task | Trigger |
|------|---------|
| Vendor delay triage | Event-driven: Payroll safety alert (red) OR buffer breach detected |
| Payment batch optimization | Weekly on Sunday evening |
| Mid-week reoptimization | If new obligations added mid-week |
| Statutory obligation prep | 7 days before deadline, checks daily |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Delay options prepared this month | Count |
| Vendor delays executed | Count (how many times user approved delays) |
| Delay success rate | % of delays accepted by vendors without issue |
| Average delay duration | X days |
| Relationship impact | Vendors delayed multiple times (monitor risk) |
| Payment batches optimized this month | Count |
| Statutory payments prepared | Count |
| Last run | Timestamp per function |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `ExpenseBucket` | Vendor details, criticality, flexibility, delay history |
| `ObligationSchedule` | Payment due dates, amounts |
| `ObligationAgreement` | Payment terms, vendor relationships |
| `CashAccount` | Available cash for buffer calculations |
| `UserConfiguration` | Buffer thresholds |

### Integration Points

- **Triggered by**: Vigilance Agent (2) for shortfall response
- **Coordinates with**: Payment Batch Sequencer (5)
- **Outputs**: PreparedAction (delay messages, payment schedules)

---

## Agent 5: Payment Batch Sequencer

### Purpose

Optimizes the timing and sequencing of vendor payments across the week to maintain healthy cash buffer while ensuring critical vendors are paid on time.

### Scope

#### What It Does

1. **Analyzes week's payment obligations**
   - Queries all bills due in upcoming week (next 7 days)
   - Categorizes by criticality:
     - **Critical**: Payroll processor, utilities, payroll taxes (must pay on time)
     - **Important**: Key vendors, recurring services (prefer to pay on time)
     - **Flexible**: Marketing, non-critical services (can delay if needed)
   - Notes payment terms for each: Net-30 day 15, Net-60 day 42, etc.

2. **Calculates optimal payment sequence**
   - Simulates different payment schedules (Mon/Wed/Fri splits)
   - For each scenario, calculates daily ending balance
   - Ensures buffer never drops below minimum threshold
   - Prioritizes critical vendors early in week (Monday/Tuesday)
   - Schedules flexible vendors later (Thursday/Friday)
   - Accounts for expected receipts (client payments due that week)

3. **Optimizes for buffer maintenance**
   - Goal: Keep ending balance >$50K (buffer threshold) every day
   - If week is tight, suggests:
     - Delaying flexible vendors to next week
     - Splitting large payments across multiple days
     - Scheduling around expected receipts (pay after large client payment arrives)
   - Shows "buffer health" for each day: Mon $67K, Tue $54K, Wed $48K → flags Wed as risky

4. **Generates payment batch files**
   - Creates CSV/ACH files for bank upload
   - Groups payments by scheduled date:
     - Monday_Batch.csv (3 vendors, $28K)
     - Wednesday_Batch.csv (5 vendors, $47K)
     - Friday_Batch.csv (2 vendors, $15K)
   - Includes vendor details: Name, account, amount, reference

#### What It Prepares

**Optimized payment schedule:**
- Table showing which vendors to pay which days
- Reasoning for sequence: "Pay Vendor A Monday (critical), Vendor B Wednesday (after Client X payment arrives)"
- Daily buffer projection: Starting balance, payments out, receipts in, ending balance

**Payment batch files:**
- CSV downloads for bank upload (one per scheduled day)
- File naming: YYYY-MM-DD_PaymentBatch.csv

**Risk flags:**
- Days where buffer drops below threshold
- Vendors that should be delayed (if week is too tight)
- Missed opportunities (could have paid vendor earlier without risk)

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Optimization Algorithm + Rules) |
| **Core Sequencing** | Constraint optimization algorithm |
| **Objective Function** | Maximize buffer health score |
| **Constraints** | Critical vendors by deadline, buffer >$50K minimum |
| **Criticality Scoring** | Rule-based (vendor category + payment history) |
| **Cash Flow Projection** | Deterministic calculation (uses Forecast Engine data) |

### Run Schedule

| Task | Trigger |
|------|---------|
| Weekly schedule optimization | Sunday evening at 8pm |
| Scope | Upcoming week (Monday-Friday) |
| Re-runs | If new bills added Monday-Wednesday |
| Mid-week reoptimization | Large unexpected payment received, new bill added, vendor payment delayed |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Payment batches optimized this month | Count |
| Total payments sequenced | Count |
| Buffer maintenance success rate | % of days buffer stayed above threshold |
| Average buffer health | Mean daily buffer amount |
| Critical vendors paid on time | % (should be 100%) |
| Flexible vendors delayed | Count (how often optimization suggested delays) |
| Last optimization | Timestamp |
| Next scheduled run | Sunday, 8pm |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `ObligationSchedule` | Bills due this week |
| `ExpenseBucket` | Vendor criticality levels |
| `CashAccount` | Current balances |
| `Forecast Engine output` | Expected receipts |
| `UserConfiguration` | Buffer thresholds |

### Integration Points

- **Receives data from**: Forecast Engine (1)
- **Coordinates with**: Vendor & Payment Agent (4)
- **Outputs**: Payment batch files, optimized schedule

---

## Agent 6: Excess Cash Allocator

### Purpose

Identifies when operating cash exceeds buffer + near-term obligations and suggests optimal allocation strategies (tax reserves, savings, investments, or growth spending).

### Scope

#### What It Does

1. **Detects excess cash**
   - Runs weekly on Sunday evening (after week closes)
   - Calculates available excess:
     - Current bank balance
     - Minus: Buffer threshold ($50K minimum)
     - Minus: Obligations due in next 14-30 days
     - Minus: Safety margin (10% of near-term obligations)
     - Equals: Available excess
   - Example: $487K balance - $50K buffer - $120K obligations - $12K margin = $305K excess
   - Triggers only if excess >$20K (threshold for meaningful allocation)

2. **Analyzes allocation options**
   - **Tax reserves:**
     - Calculates estimated tax liability (quarterly or annual)
     - Suggests setting aside % of revenue (e.g., 25% for taxes)
     - Checks if tax reserve account is underfunded
     - Recommends transfer amount to bring to target level
   - **Savings/emergency fund:**
     - Target: 3-6 months operating expenses
     - Calculates current runway (months of cash at current burn)
     - If runway <6 months, prioritizes building reserves
   - **Debt paydown:**
     - If credit line drawn, calculates interest cost
     - Compares to investment returns (pay down if interest >6%)
   - **Growth investment:**
     - If reserves are healthy, suggests allocating to growth
     - Examples: Hiring, marketing, R&D, equipment
     - Calculates ROI threshold (invest if expected return >debt cost)

3. **Ranks allocation options by priority**
   - Uses rule-based priority framework:
     1. Tax obligations (highest priority - avoid penalties)
     2. Emergency fund (if runway <3 months)
     3. Debt paydown (if interest >6%)
     4. Growth investment (if reserves healthy + ROI >10%)
   - For each option, calculates:
     - Recommended amount
     - Reasoning (why this allocation makes sense)
     - Impact (runway before/after, reserve levels, etc.)

4. **Prepares transfer instructions**
   - For each allocation option:
     - From account: Operating account (...4521)
     - To account: Tax reserve account (...8832) OR external investment account
     - Amount: $XX,XXX
     - Reference: "Q1 2025 tax reserve" or "Emergency fund building"
   - Generates wire transfer details or internal transfer instructions

#### What It Prepares

**Excess cash alert:**
- "You have $305K excess cash this week (after buffer + obligations)"
- Trigger: Suggests reviewing allocation options

**Allocation recommendations (ranked):**

**Option 1: Transfer $75K to tax reserves (Priority: High)**
- Reasoning: Q1 estimated taxes due Jan 15 ($68K), currently only $10K in reserve, shortfall of $58K
- Impact: Fully funds tax obligation + $7K margin
- Risk: If not allocated, will need to draw from operations in 2 weeks

**Option 2: Transfer $100K to emergency fund (Priority: Medium)**
- Reasoning: Current runway is 4.2 months, target is 6 months, need $230K in reserves
- Impact: Increases runway to 5.1 months
- Benefit: Reduces stress, provides buffer for growth investment

**Option 3: Invest $130K in growth (Priority: Low)**
- Reasoning: Reserves healthy after Options 1-2, hiring plan requires $120K over next quarter
- Impact: Funds 2 new hires without disrupting operations
- ROI: New hires expected to generate $300K annual revenue

**Transfer instructions for each option (ready to execute)**

### Technical Specifications

| Attribute | Value |
|-----------|-------|
| **Intelligence Type** | Hybrid (Rules + AI/LLM) |
| **Excess Calculation** | Rule-based (deterministic math) |
| **Allocation Prioritization** | Rule-based framework (tax > reserves > debt > growth) |
| **Reasoning Generation** | AI/LLM (GPT-4) |
| **Context** | Explains trade-offs, timing considerations, combination suggestions |

### Run Schedule

| Task | Trigger |
|------|---------|
| Weekly check | Sunday evening at 9pm (after week closes) |
| Triggered check | When large unexpected payment received (>$50K) |
| Quarterly review | 30 days before estimated tax deadline |

### Metrics to Display

| Metric | Description |
|--------|-------------|
| Excess cash detected this quarter | Count of weeks with excess |
| Total excess allocated | $XXX,XXX (amount moved out of operations) |
| Allocation breakdown | To tax reserves, emergency fund, debt paydown, growth ($ and %) |
| Current runway | X.X months (before/after allocations) |
| Tax reserve funding level | XX% of estimated liability |
| Last run | Timestamp |
| Next scheduled run | Sunday, 9pm |

### Data Dependencies

| Entity | Usage |
|--------|-------|
| `CashAccount` | Current balances, account types |
| `ObligationSchedule` | Near-term obligations |
| `UserConfiguration` | Buffer thresholds, tax rate estimates |
| `Forecast Engine output` | Runway calculations |

### Integration Points

- **Receives data from**: Forecast Engine (1)
- **Independent of**: Vigilance Agent (runs regardless of alerts)
- **Outputs**: PreparedAction (allocation recommendations, transfer instructions)

---

## Agent Dependencies & Interactions

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│  CashAccount | Client | ExpenseBucket | ObligationAgreement/Schedule        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FORECAST ENGINE (Agent 1)                            │
│  - 13-week cash projection                                                  │
│  - Confidence scoring                                                        │
│  - Risk period identification                                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
┌─────────────────────────────┐           ┌─────────────────────────────┐
│   VIGILANCE AGENT (2)       │           │   EXCESS ALLOCATOR (6)      │
│   Monitors for issues       │           │   Optimizes surplus         │
└─────────────┬───────────────┘           └─────────────────────────────┘
              │
              │ Triggers on detection
              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PREPARATION AGENTS                                   │
├────────────────────────┬────────────────────────┬───────────────────────────┤
│   AR/INVOICE (3)       │   VENDOR/PAYMENT (4)   │   BATCH SEQUENCER (5)     │
│   - Invoice drafts     │   - Delay messages     │   - Payment optimization  │
│   - Collection emails  │   - Vendor ranking     │   - Batch file generation │
│                        │   - Statutory prep     │                           │
└────────────────────────┴────────────────────────┴───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ACTION QUEUE                                      │
│                         (PreparedAction items)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER APPROVAL                                        │
│                    Approve / Modify / Skip                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       EXECUTION SERVICE                                      │
│                 (Send emails, process payments, etc.)                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Trigger Relationships

| Detection Type | Triggered Agent | Action Type |
|---------------|-----------------|-------------|
| `LATE_PAYMENT` | AR/Invoice Agent (3) | Collection email draft |
| `PAYROLL_SAFETY` | Vendor/Payment Agent (4) | Vendor delay options |
| `BUFFER_BREACH` | Vendor/Payment Agent (4) | Delay triage + contingency |
| `VENDOR_TERMS_EXPIRING` | Vendor/Payment Agent (4) | Payment preparation |
| `STATUTORY_DEADLINE` | Vendor/Payment Agent (4) | Statutory payment prep |
| `PAYMENT_TIMING_CONFLICT` | Payment Batch Sequencer (5) | Optimized schedule |
| (Weekly schedule) | Payment Batch Sequencer (5) | Week's payment batches |
| (Excess detected) | Excess Cash Allocator (6) | Allocation recommendations |

---

## Implementation Priority

### Phase 1: Core Foundation

| Priority | Agent | Rationale |
|----------|-------|-----------|
| 1 | Forecast Engine (1) | Foundation for all other agents |
| 2 | Cash Flow Vigilance (2) | Enables detection-driven workflow |

### Phase 2: Response Agents

| Priority | Agent | Rationale |
|----------|-------|-----------|
| 3 | AR/Invoice Agent (3) | Addresses most common alert type (late payments) |
| 4 | Vendor/Payment Agent (4) | Critical for shortfall response |

### Phase 3: Optimization

| Priority | Agent | Rationale |
|----------|-------|-----------|
| 5 | Payment Batch Sequencer (5) | Proactive optimization, reduces fire drills |
| 6 | Excess Cash Allocator (6) | Opportunity optimization (nice-to-have) |

---

## Summary Table

| Agent | Primary Function | Intelligence Type | Run Frequency |
|-------|------------------|-------------------|---------------|
| Forecast Engine (1) | Projects 13-week cash position | Hybrid (Rules + Stats) | Real-time + every 6 hours |
| Cash Flow Vigilance (2) | Monitors for shortfalls & risks | Hybrid (Rules + Stats) | Every 6 hours + event-driven |
| AR & Invoice (3) | Generates invoices, drafts collection emails | Hybrid (Rules + AI/LLM) | Daily at 9am + event-driven |
| Vendor & Payment (4) | Ranks vendors for delays, drafts messages | Hybrid (Algorithm + AI/LLM) | Event-driven (shortfall detected) |
| Payment Batch Sequencer (5) | Optimizes payment timing across week | Hybrid (Optimization + Rules) | Weekly (Sunday 8pm) + mid-week |
| Excess Cash Allocator (6) | Suggests allocation for surplus cash | Hybrid (Rules + AI/LLM) | Weekly (Sunday 9pm) + large receipts |

---

## File Structure

```
tamio-backend/app/agents/
├── AGENTS_ARCHITECTURE.md          # This document
├── __init__.py
├── base.py                         # Base agent class
├── forecast/
│   ├── __init__.py
│   ├── engine.py                   # Forecast Engine implementation
│   ├── confidence.py               # Confidence scoring
│   └── risk_flags.py               # Risk period detection
├── vigilance/
│   ├── __init__.py
│   ├── engine.py                   # Vigilance Agent implementation
│   ├── monitors/
│   │   ├── buffer.py               # Buffer health monitoring
│   │   ├── payroll.py              # Payroll safety checks
│   │   ├── revenue.py              # Revenue pattern monitoring
│   │   └── clustering.py           # Obligation clustering
│   └── scoring.py                  # Risk scoring formulas
├── ar_invoice/
│   ├── __init__.py
│   ├── engine.py                   # AR & Invoice Agent implementation
│   ├── invoice_generator.py        # Invoice calculation & drafting
│   ├── collection.py               # Collection email generation
│   └── tone_calibration.py         # Relationship-based tone selection
├── vendor_payment/
│   ├── __init__.py
│   ├── engine.py                   # Vendor & Payment Agent implementation
│   ├── delay_triage.py             # Vendor ranking for delays
│   ├── message_drafting.py         # Delay message generation
│   └── statutory.py                # Statutory obligation handling
├── batch_sequencer/
│   ├── __init__.py
│   ├── engine.py                   # Payment Batch Sequencer implementation
│   ├── optimizer.py                # Constraint optimization algorithm
│   └── batch_generator.py          # CSV/ACH file generation
├── excess_allocator/
│   ├── __init__.py
│   ├── engine.py                   # Excess Cash Allocator implementation
│   ├── detection.py                # Excess cash detection
│   ├── allocation.py               # Allocation option ranking
│   └── transfer.py                 # Transfer instruction generation
├── scheduler.py                    # APScheduler integration for all agents
└── routes.py                       # API endpoints for agent management
```
