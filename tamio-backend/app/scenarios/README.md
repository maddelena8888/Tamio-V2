# Scenario Analysis Module (Control Engine)

The Scenario Analysis module provides a comprehensive "what-if" modeling system that allows users to explore financial decisions before committing to them. It's designed to never change reality unless explicitly confirmed by the user.

## Architecture Overview

### Core Components

1. **Financial Rules** (`models.FinancialRule`) - Define what "safe" means for the business
2. **Scenarios** (`models.Scenario`) - What-if scenarios that model potential changes
3. **Scenario Events** (`models.ScenarioEvent`) - Cloned/modified cash events within scenarios
4. **Rule Evaluations** (`models.RuleEvaluation`) - Results of evaluating rules against forecasts
5. **Scenario Forecasts** (`models.ScenarioForecast`) - Computed forecasts with scenario overlay

### Key Principles

- **Non-destructive**: Scenarios never modify canonical data unless confirmed
- **Layer-based**: Scenarios create overlay layers on top of base forecast
- **Deterministic**: All transformations are explicit and reversible
- **Auditable**: Full attribution tracking for all changes

## API Endpoints

### Financial Rules

```
POST   /api/scenarios/rules          - Create a financial rule
GET    /api/scenarios/rules          - Get all rules for a user
PUT    /api/scenarios/rules/{id}     - Update a rule
DELETE /api/scenarios/rules/{id}     - Delete a rule
```

### Scenarios

```
POST   /api/scenarios/scenarios                - Create a scenario
GET    /api/scenarios/scenarios                - Get all scenarios
GET    /api/scenarios/scenarios/{id}           - Get specific scenario
PUT    /api/scenarios/scenarios/{id}           - Update scenario (adjust knobs)
DELETE /api/scenarios/scenarios/{id}           - Discard scenario
POST   /api/scenarios/scenarios/{id}/build     - Build scenario layer
POST   /api/scenarios/scenarios/{id}/confirm   - Confirm and commit to reality
```

### Analysis

```
GET    /api/scenarios/scenarios/{id}/forecast  - Get scenario forecast with comparison
GET    /api/scenarios/suggest                  - Get Tamio-suggested scenarios
GET    /api/scenarios/evaluate/base            - Evaluate rules on base forecast
```

## Scenario Types

### Cash In Scenarios

1. **Payment Delay** (`payment_delay`)
   - Shift revenue event dates forward
   - Optional: Partial payment modeling
   - Example: "Client pays 2 weeks late"

2. **Client Loss** (`client_loss`)
   - Remove all future revenue from a client
   - Effective date-based
   - Example: "Lose client ABC on Jan 1"

3. **Client Gain** (`client_gain`)
   - Add new recurring revenue streams
   - Example: "New client starting next month at $10k/mo"

4. **Client Change** (`client_change`)
   - Modify existing revenue amounts (upsell/downsell)
   - Example: "Client XYZ increases from $5k to $7k/mo"

### Cash Out Scenarios

5. **Hiring** (`hiring`)
   - Add new recurring payroll expenses
   - Optional: One-time onboarding costs
   - Example: "Hire engineer at $8k/mo starting Feb 1"

6. **Firing** (`firing`)
   - Remove future payroll expenses
   - Optional: Severance payment
   - Example: "Let go contractor with 2 weeks severance"

7. **Contractor Gain** (`contractor_gain`)
   - Add contractor expenses
   - Example: "Add designer at $5k/mo"

8. **Contractor Loss** (`contractor_loss`)
   - Remove contractor expenses
   - Example: "End contractor engagement"

9. **Increased Expense** (`increased_expense`)
   - Add new or increase existing expenses
   - One-time or recurring
   - Example: "New office rent $3k/mo"

10. **Decreased Expense** (`decreased_expense`)
    - Reduce or eliminate expenses
    - Example: "Cancel software subscription"

11. **Payment Delay Out** (`payment_delay_out`)
    - Delay outgoing payments to vendors
    - Temporary liquidity relief
    - Example: "Delay vendor payment by 1 week"

## Usage Flow

### 1. Setup Financial Rules (First-time)

```python
POST /api/scenarios/rules
{
  "user_id": "user_123",
  "rule_type": "minimum_cash_buffer",
  "name": "3-Month Safety Buffer",
  "threshold_config": {
    "months": 3
  }
}
```

### 2. Create a Scenario

```python
POST /api/scenarios/scenarios
{
  "user_id": "user_123",
  "name": "What if we hire 2 engineers?",
  "scenario_type": "hiring",
  "entry_path": "user_defined",
  "scope_config": {},
  "parameters": {
    "role_title": "Senior Engineer",
    "start_date": "2026-01-15",
    "monthly_cost": 8000,
    "onboarding_costs": 2000
  }
}
```

### 3. Build Scenario Layer

```python
POST /api/scenarios/scenarios/{scenario_id}/build

# Response:
{
  "message": "Scenario built successfully",
  "events_generated": 12  # 3 months × 4 payroll events
}
```

### 4. View Scenario Forecast

```python
GET /api/scenarios/scenarios/{scenario_id}/forecast

# Response:
{
  "base_forecast": { ... },
  "scenario_forecast": { ... },
  "deltas": {
    "weeks": [
      {
        "week_number": 1,
        "delta_cash_out": 8000,
        "delta_ending_balance": -8000
      },
      ...
    ]
  },
  "rule_evaluations": [
    {
      "severity": "amber",
      "is_breached": true,
      "first_breach_week": 8,
      "action_window_weeks": 7,
      ...
    }
  ],
  "decision_signals": {
    "signals": [
      {
        "signal_type": "rule_breach",
        "title": "Cash Buffer Warning",
        "message": "Your cash balance will fall below the required 3-month buffer...",
        "recommended_actions": [...]
      }
    ]
  }
}
```

### 5. Iterate (Adjust Knobs)

```python
PUT /api/scenarios/scenarios/{scenario_id}
{
  "parameters": {
    "start_date": "2026-02-01",  # Delayed start
    "monthly_cost": 7000  # Adjusted compensation
  }
}

# Scenario automatically rebuilds
```

### 6. Confirm or Discard

**Option A: Confirm (commit to reality)**
```python
POST /api/scenarios/scenarios/{scenario_id}/confirm

# Applies all scenario events to canonical data
# Base forecast updates
```

**Option B: Discard**
```python
DELETE /api/scenarios/scenarios/{scenario_id}

# Marks scenario as discarded
# No canonical data changed
```

## Rule Evaluation

### Severity Levels

- **GREEN**: All rules satisfied
- **AMBER**: Approaching threshold or future breach
- **RED**: Current breach or imminent breach

### Decision Signals

Rule evaluations generate actionable decision signals:

```python
{
  "signal_type": "rule_breach",
  "severity": "red",
  "title": "Cash Buffer Warning",
  "message": "Your cash balance is currently below...",
  "earliest_risk_week": 1,
  "action_window_weeks": 0,
  "recommended_actions": [
    "Immediately defer all non-essential expenses",
    "Accelerate all receivables collection",
    ...
  ]
}
```

## Tamio-Suggested Scenarios

The system can suggest relevant scenarios based on current state:

```python
GET /api/scenarios/suggest?user_id=user_123

# Response:
{
  "suggestions": [
    {
      "scenario_type": "decreased_expense",
      "reason": "Low runway - consider cost reduction",
      "suggested_params": {
        "reduction_pct": 10,
        "category": "discretionary"
      }
    },
    {
      "scenario_type": "client_loss",
      "reason": "Understand impact of losing key clients",
      "suggested_params": {}
    }
  ]
}
```

## Advanced Features

### Stacked Scenarios

Create compound scenarios by layering multiple scenarios:

```python
# Scenario 1: Hire engineer
POST /api/scenarios/scenarios
{
  "scenario_type": "hiring",
  "layer_order": 0,
  ...
}

# Scenario 2: Add on top - lose a client
POST /api/scenarios/scenarios
{
  "scenario_type": "client_loss",
  "parent_scenario_id": "scenario_1_id",
  "layer_order": 1,
  ...
}
```

### Linked Scenarios (Second-Order Effects)

When creating scenarios, the system can detect and prompt for linked effects:

- Client loss → Reduce contractors/tools?
- Client gain → Add contractor capacity?
- Hiring → Increase tool/software costs?

## Database Schema

### Key Tables

1. **financial_rules** - Financial safety rule definitions
2. **scenarios** - Scenario configurations
3. **scenario_events** - Modified/added/deleted events per scenario
4. **rule_evaluations** - Rule evaluation results
5. **scenario_forecasts** - Computed forecast snapshots

### Relationships

```
User
  ├── FinancialRule (1:N)
  ├── Scenario (1:N)
  │   ├── ScenarioEvent (1:N)
  │   ├── RuleEvaluation (1:N)
  │   └── ScenarioForecast (1:N)
  └── RuleEvaluation (1:N)
```

## Implementation Notes

### Canonical Data Preservation

Scenarios never modify canonical objects (`CashEvent`, `Client`, `ExpenseBucket`) until confirmed. All modifications happen in memory or in `ScenarioEvent` table.

### Event Operations

Three types of operations:

1. **ADD** - New events that don't exist in base
2. **MODIFY** - Changed versions of existing events
3. **DELETE** - Events removed from timeline

### Forecast Computation

The scenario forecast is computed by:

1. Loading all base canonical events
2. Applying scenario layer transformations
3. Running standard forecast engine on modified event list
4. Comparing to base forecast to generate deltas

### Performance Considerations

- Scenario events are lazy-loaded
- Forecasts are computed on-demand
- Consider caching for frequently accessed scenarios
- Rule evaluations are lightweight (no event creation)

## Error Handling

Common errors and how to handle them:

1. **Scenario not found** (404) - Check scenario_id
2. **Rule breach** - Not an error, but a warning in evaluation
3. **Invalid parameters** (422) - Check scenario type requirements
4. **Circular scenario reference** - Prevent in parent_scenario_id validation

## Testing Scenarios

Example test flow:

```bash
# 1. Create user and rules
curl -X POST /api/scenarios/rules -d '{...}'

# 2. Create base data (clients, expenses)
curl -X POST /api/data/clients -d '{...}'

# 3. Get base forecast
curl /api/forecast?user_id=user_123

# 4. Create scenario
curl -X POST /api/scenarios/scenarios -d '{...}'

# 5. Build and evaluate
curl -X POST /api/scenarios/scenarios/{id}/build
curl /api/scenarios/scenarios/{id}/forecast

# 6. Iterate
curl -X PUT /api/scenarios/scenarios/{id} -d '{...}'

# 7. Confirm or discard
curl -X POST /api/scenarios/scenarios/{id}/confirm
```

## Future Enhancements

Potential additions:

- **Probabilistic scenarios**: Add confidence ranges
- **Sensitivity analysis**: Automatically vary parameters
- **Scenario templates**: Pre-built common scenarios
- **Scenario sharing**: Share scenarios between users
- **Multi-scenario comparison**: Compare 3+ scenarios side-by-side
- **Scenario versioning**: Track scenario evolution over time
