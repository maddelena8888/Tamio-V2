# CLAUDE.md — Tamio Treasury Operator

## Project overview

This project uses **TypeScript** (primary) and **Python** (backend).

**Frontend** (`tamio-frontend/`): React app with Recharts for charts and a light design system theme. Key pages and their routes:

| Route | Component | Common name |
|-------|-----------|-------------|
| `/` (index) | `ForecastCanvas` | Home / Canvas |
| `/dashboard` | `Dashboard` | Dashboard |
| `/projections` | `Projections` | Projections |
| `/rules` | `Rules` | Rules & Alerts |
| `/health` | `Health` | Health |
| `/scenarios` | `Forecast` | Scenarios |
| `/ledger` | `ClientsExpenses` | Ledger |
| `/tami` | `Tami` | TAMI Chat |
| `/forecast-scenarios` | `UnifiedForecast` | Unified Forecast |

Note: `/home` redirects to `/`, `/clients` redirects to `/ledger`. See `src/router.tsx` for the full routing table.

**Backend** (`tamio-backend/`): Python FastAPI app with a demo guard middleware (`app/middleware/demo_guard.py`) that blocks mutation POST/PUT/DELETE requests for demo accounts. Allowed POSTs for demo: auth endpoints, forecast calculation, TAMI chat, and scenario creation.

## Common mistakes to avoid

1. **Verify you're editing the correct file.** When editing UI components, ALWAYS check which component is actually rendered on the target page/route before making changes. Common mistake: editing `ForecastChart.tsx` when the actual rendered component is `ForecastCanvas.tsx`. Use the route table above or trace from `src/router.tsx`.

2. **Confirm changes are visible after editing.** After making frontend changes, always restart the dev server and confirm the change is visible. Do NOT blame browser caching if changes aren't appearing — instead re-verify the edit was applied to the correct file and the correct component function.

3. **Trace the router before editing a page.** When the user asks for changes to a specific page (e.g., "canvas page", "dashboard", "home"), first trace the router to find which component file is rendered for that route before editing anything. Page names don't always match component filenames.

4. **Eagerly capture ORM attributes before heavy DB operations.** `compute_scenario_forecast` (and similar heavy async calls) expire all ORM objects in the AsyncSession, even with `expire_on_commit=False`. Accessing expired attributes triggers a lazy load → `MissingGreenlet` error in async context. **Fix pattern**: capture ORM attributes into plain Python variables (dicts, tuples, strings) immediately after loading, BEFORE calling any `await` that does heavy DB work. See `context.py`, `orchestrator.py` for examples. This applies to any code path that loads ORM objects then calls forecast/scenario computation.

## Communication style

Keep initial plans and responses concise. When presenting options or plans, start with 3 or fewer unless asked for more. Avoid overly broad output — the user prefers iterative refinement over comprehensive first drafts.

## Architecture

The TAMI AI assistant lives in `tamio-backend/app/tami/`. The core loop:

```
orchestrator.py → agent1_prompt_builder.py → agent2_responder.py → tools.py → context.py
```

**Flow per user message:**
1. `orchestrator.chat()` calls `context.build_context()` — loads all deterministic financial data from DB
2. `orchestrator` calls `agent1_prompt_builder.build_prompt()` — classifies intent, injects relevant knowledge, builds system message + conversation history
3. `orchestrator` calls `agent2_responder.call_openai()` — sends messages + tool schemas to Anthropic API
4. If Claude calls a tool → `tools.dispatch_tool()` executes it → context is rebuilt → `agent2_responder.generate_response()` produces final answer with tool result
5. `agent2_responder.parse_response()` converts Claude's output to `TAMIResponse` (message_markdown, mode, ui_hints)
6. Messages saved to DB, response returned

**MAX_TOOL_LOOPS = 1** — one tool execution per user message, no chaining. Defined in `orchestrator.py:44`.

**Intent routing** (`intent.py`): Pattern-based classification (11 intents) determines which knowledge to inject and whether to use the fast model (`should_use_fast_model()`). Simple queries (greetings, term lookups) use the fast model; scenario creation/modification always use the full model.

**Context payload** (`context.py`): `build_context()` loads ~10 data sources into `ContextPayload`: starting cash, 13-week forecast, buffer rule evaluations, active scenarios, client/expense summaries, behavior insights, active alerts. This is deterministic — same DB state always produces the same context.

**Streaming** uses `chat_streaming()` which yields SSE chunks. In streaming mode, response format is plain markdown (not JSON), mode is derived from intent, and tool calling is disabled.

### Key files

| File | Role |
|------|------|
| `app/tami/orchestrator.py` | Main loop: `chat()`, `chat_streaming()` |
| `app/tami/agent1_prompt_builder.py` | Builds system prompt with context + knowledge injection |
| `app/tami/agent2_responder.py` | Calls Anthropic API, handles tool results, parses response |
| `app/tami/tools.py` | Tool schemas (OpenAI format) + `dispatch_tool()` router |
| `app/tami/context.py` | Loads all DB data into `ContextPayload` |
| `app/tami/intent.py` | Intent classification + knowledge routing |
| `app/tami/cache.py` | TTL-based context cache (60s) for streaming |
| `app/scenarios/engine.py` | Scenario layer builder (11 types, ~1300 lines) |
| `app/scenarios/rule_engine.py` | Financial rule evaluation (buffer rules, severity) |
| `app/forecast/engine_v2.py` | 13-week rolling forecast engine |
| `app/seed/agencyco.py` | AgencyCo demo data ($8M ARR marketing agency) |
| `app/config.py` | Settings via pydantic-settings (env vars) |

## Engineering preferences

These are non-negotiable:

- **DRY is important** — flag repetition aggressively. If you see the same pattern in two places, extract it before it reaches three.
- **Well-tested code is non-negotiable.** I'd rather have too many tests than too few.
- **Code should be "engineered enough"** — not fragile/hacky AND not over-abstracted. Find the middle.
- **Handle more edge cases, not fewer.** Thoughtfulness > speed.
- **Explicit over clever.** If it needs a comment to explain what's happening, it's probably too clever.

## Domain context

TAMI is an AI treasury assistant for SMB CFOs (agencies, consultancies, service businesses).

**Key domain rules:**

- **Payroll is always the highest priority obligation** — it's a trust contract, not just an expense. The `ExpenseBucket` model tracks `category: "payroll"` and `criticality: "critical"`. Never suggest delaying payroll.
- **Client relationships have types** (`relationship_type` field): `strategic` (large, high-value — softer communication), `managed` (balanced), `transactional` (smaller, firmer approach). These affect how TAMI communicates about them.
- **Cash confidence levels matter**: `high` (Xero repeating invoice), `medium` (synced contact, manual entry), `low` (manual, no validation). These are NOT interchangeable — a forecast built on low-confidence data should say so.
- **Financial tone must be precise but not alarming.** TAMI is a calm operator, not a panic button. Think: a sharp CFO whispering in your ear, not a customer support bot and not a fire alarm.

**Obligation architecture** (three layers):
1. **ObligationAgreement** — WHY: the contractual reason (vendor bill, payroll, subscription)
2. **ObligationSchedule** — WHEN: specific due dates and estimated amounts
3. **PaymentEvent** — REALITY: what actually got paid, for reconciliation

**Scenario types** (11 total): `payment_delay`, `client_loss`, `client_gain`, `client_change`, `hiring`, `firing`, `contractor_gain`, `contractor_loss`, `increased_expense`, `decreased_expense`, `payment_delay_out`. Scenarios are non-destructive virtual overlays — they never modify canonical data.

**Rule severity**: `green` (safe), `amber` (approaching breach), `red` (breached). The minimum cash buffer rule checks `cash_balance >= monthly_opex × required_months`.

## Tool design conventions

Tools live in `app/tami/tools.py`. Two categories:

**Scenario tools** (5 — closed set): `scenario_create_or_update_layer`, `scenario_iterate_layer`, `scenario_discard_layer`, `scenario_get_suggestions`, `plan_build_goal_scenarios`. These create/modify virtual scenario overlays. Don't add more scenario tools — extend the engine instead.

**Operational tools** (expanding set): `check_payroll_safety`, `draft_collection_message`, `analyze_concentration_risk`, `generate_briefing`. These are **read-only** — they query data and return analysis. Self-contained, no chaining needed (`MAX_TOOL_LOOPS = 1` still holds).

**Schema format** — OpenAI function calling format (converted to Anthropic format by `agent2_responder._convert_tools_to_anthropic_format()`):
```python
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "When to use this tool",
        "parameters": {
            "type": "object",
            "properties": { ... },
            "required": [...]
        }
    }
}
```

**Dispatch** — `dispatch_tool(db, user_id, tool_name, tool_args)` uses a simple if-elif chain routing to private handler functions (`_create_or_update_layer`, `_iterate_layer`, etc.). Unknown tools return `{"error": f"Unknown tool: {tool_name}"}`.

**Result structure** — all tools return `Dict[str, Any]` with:
- Success: `{"success": True, "message": "...", ...additional_data}`
- Failure: `{"success": False, "error": "..."}`

**Tool results are INVISIBLE to users.** They flow back into Claude via `generate_response()`, which adds the tool_use + tool_result to the message history and calls Claude again WITHOUT tools. Claude then generates a natural language explanation. The user only sees markdown — never raw tool output.

**When adding a new operational tool:**
1. Add schema to `TOOL_SCHEMAS` list in `tools.py`
2. Add elif branch in `dispatch_tool()`
3. Implement private handler function `_your_handler(db, user_id, args)`
4. Return result dict matching the success/failure pattern above
5. Add intent enum + patterns to `intent.py` (see "Intent wiring" below)
6. Add `_intent_to_mode` mapping in `orchestrator.py`
7. Add intent to `complex_intents` in `should_use_fast_model()` (operational tools need the full model)
8. Write tests in `tests/tami/test_operational_tools.py`

### Operational tool patterns

Established conventions from `check_payroll_safety`:

**Shared helpers** — if two tools need the same computation, extract a `_compute_*()` helper. Example: `_compute_payroll_coverage()` is shared between `check_payroll_safety` and `generate_briefing`. Place shared helpers in the `# OPERATIONAL TOOLS` section of `tools.py`, before the tool handler functions.

**Data access** — operational tools reuse existing models and engines:
- Forecast data: `calculate_13_week_forecast(db, user_id)` (already imported)
- Clients: `Client` model from `app.data.clients.models`
- Expenses: `ExpenseBucket` model from `app.data.expenses.models`
- Obligations: `ObligationAgreement`, `ObligationSchedule` from `app.data.obligations.models`
- Rule evaluations: `evaluate_rules(db, user_id, forecast)` (already imported)
- Scenario impact: `calculate_13_week_forecast(db, user_id, scenario_context=ScenarioContext(...))` with `excluded_client_ids`

**Confidence layering** — two levels of behavioral confidence override:
- **Layer 1** (engine-level, deferred): Downgrade in `engine_v2.py._compute_client_events()` based on `payment_behavior` + `avg_payment_delay_days`
- **Layer 2** (tool-level, implemented): Query `ObligationSchedule.status == "overdue"` at tool execution time, reclassify HIGH → MEDIUM for specific clients. Stricter than Layer 1 because it uses real-time overdue state. Used in `_compute_payroll_coverage()`.

**Message generation** — each tool builds a human-readable `message` field in its return dict. This gives Claude a starting point for its natural language response. Keep messages factual and precise — no exclamation marks, no "Great news!".

### Intent wiring

For each new operational tool, update `intent.py`:
1. Add enum value to `Intent` class (e.g., `CHECK_PAYROLL = "check_payroll"`)
2. Add 2-4 regex patterns to `INTENT_PATTERNS` with appropriate priorities (70-90 range)
3. Add to `get_intent_description()` dict
4. Add to `get_relevant_knowledge_keys()` with relevant glossary terms
5. Add to `complex_intents` in `should_use_fast_model()` — all operational tools need tool calling, so they need the full model

In `orchestrator.py`, add the new intent to `_intent_to_mode()` mapping → `"explain_forecast"` mode.

## Frontend conventions

When adding new UI components or features, always check they are wired into navigation/routing:
- New pages need menu entries in `MainLayout` and route definitions in `src/router.tsx`
- New context providers need wrapper components
- New overlay components (modals, popups, drawers) need proper z-index values — use `z-50` or higher for modals/popups

## Code style

Inferred from the existing codebase:

**Imports** — stdlib → third-party → local, grouped with blank lines:
```python
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.config import settings
from app.tami.schemas import TAMIResponse, TAMIMode
```

**Naming:**
- Functions/variables: `snake_case` (`dispatch_tool`, `user_id`)
- Classes: `PascalCase` (`DetectionEngine`, `TAMIResponse`)
- Enums: `PascalCase` class, `UPPER_CASE` values (`TAMIMode.EXPLAIN_FORECAST`)
- Constants: `UPPER_CASE` (`MAX_TOOL_LOOPS`, `TOOL_SCHEMAS`)
- Private functions: leading underscore (`_create_or_update_layer`)

**Async** — used throughout. All DB operations, API calls, and tool handlers are `async def` with `await`. Tests use `AsyncMock()` and `@pytest.mark.asyncio`.

**Error handling** — try-except at strategic points with graceful degradation. Tools return error dicts, not exceptions. API failures produce fallback responses via `create_fallback_response()`. Never let an exception bubble up to the user as a raw traceback.

**Type hints** — comprehensive on all function signatures. Use `Optional[T]`, `List[T]`, `Dict[str, Any]`. Pydantic models with `Field()` for API schemas.

**Docstrings** — module-level triple-quote docstrings at file top explaining purpose. Function docstrings with Args/Returns where non-obvious. Pragmatic, not ceremonial.

## Testing expectations

Framework: `pytest` + `pytest-asyncio`. Tests live in `tamio-backend/tests/`.

**Every new tool needs at minimum:**
1. **Happy path test** — tool executes successfully with valid args, returns expected result structure
2. **Edge case tests** — empty data, missing fields, invalid scenario_id, etc.
3. **Result structure test** — verify the tool result dict matches what `agent2_responder.generate_response()` expects (i.e., it's JSON-serializable and includes `success` key)

**Test patterns used in this codebase:**
```python
@pytest.fixture
def mock_db():
    return AsyncMock()

class TestFeatureName:
    @pytest.mark.asyncio
    async def test_happy_path(self, mock_db, ...):
        # Setup
        # Execute
        # Assert
```

**Use the AgencyCo seed data** (`app/seed/agencyco.py`) for realistic test scenarios. It provides: 15 clients with varied payment behaviors, $487K across 3 accounts, bi-weekly $85K payroll, overdue invoices, and multiple detection triggers.

**Operational tool tests** live in `tests/tami/test_operational_tools.py`. Established patterns:
- **Mock helpers** — `_make_payroll_bucket()`, `_make_forecast_week()`, `_make_forecast()` build realistic mock data. Add similar helpers for new tools (e.g., `_make_client()` for concentration risk).
- **DB mock via `_setup_db_mock()`** — tracks query execution order and returns appropriate results per query. When a tool makes N sequential DB queries, the mock returns different data for each call based on call count. Extend this pattern for new tools that query different tables.
- **Forecast mocking** — patch `app.tami.tools.calculate_13_week_forecast` to return `_make_forecast(weeks)`. This avoids hitting the real forecast engine in unit tests.
- **Dispatch routing test** — every new tool gets a test confirming `dispatch_tool(db, user_id, "tool_name", {})` doesn't return `{"error": "Unknown tool: ..."}`.
- **All tool return values must be JSON-serializable** — test with `json.dumps(result)` to catch Decimal, date, or ORM objects leaking into the output.

## What NOT to do

- **Don't add more scenario tools** — the 5 scenario operations (create, iterate, discard, suggest, goal-plan) are a closed set managed through the scenario engine. New analytical capabilities should be operational tools (read-only). New scenario capabilities should extend the engine.
- **Don't change the tool result format** without updating `agent2_responder.py`'s `generate_response()` conversion logic. Tool results must be JSON-serializable dicts with a `success` key.
- **Don't hardcode dollar amounts or thresholds** — use the context payload. Thresholds come from `FinancialRule.threshold_config`. Cash values come from `build_context()`. The only constants should be structural (like `MAX_TOOL_LOOPS`).
- **Don't make TAMI sound like a generic chatbot.** It should sound like a sharp CFO whispering in your ear, not a customer support bot. No "Great question!", no "I'd be happy to help!", no exclamation marks on financial data.
- **Don't bypass the orchestrator.** All TAMI interactions go through `orchestrator.chat()` or `chat_streaming()`. Don't call `agent2_responder` directly from routes.
- **Don't modify canonical data from tools.** Scenario tools create virtual overlays via `ScenarioEvent` objects. Only explicit user confirmation (scenario status → `confirmed`) should affect real data.

## Quick reference: running the project

```bash
# Backend
cd tamio-backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd tamio-frontend
npm install
npm run dev  # Vite on port 5173

# Tests
cd tamio-backend
pytest tests/ -v

# Database migrations
cd tamio-backend
alembic upgrade head

# Test a TAMI tool against live backend (requires backend running + AgencyCo seeded)
cd tamio-backend && bash scripts/test_tool.sh check_payroll_safety
cd tamio-backend && bash scripts/test_tool.sh draft_collection_message
# Or use the slash command: /test-tool check_payroll_safety
```

## Test TAMI tool

When asked to "test check_payroll_safety", "test draft_collection_message", "test analyze_concentration_risk", "test generate_briefing", or more generally "test <tool_name>":
1. Run: `cd tamio-backend && bash scripts/test_tool.sh <tool_name>`
2. Show the full output
3. If the backend isn't running (connection refused), tell the user to start it first with `cd tamio-backend && uvicorn app.main:app --reload --port 8000`

## Restart dev servers

When asked to "restart servers" or "restart dev":
1. Kill any existing frontend/backend processes on ports 8000 and 5173
2. Start the Python backend: `cd tamio-backend && uvicorn app.main:app --reload --port 8000 &`
3. Start the frontend: `cd tamio-frontend && npm run dev &`
4. Verify both are running by checking the ports
5. Report the URLs to the user (backend: http://localhost:8000, frontend: http://localhost:5173)

## Tech debt scan

When asked to "run techdebt", "tech debt", or "find duplicates":

Scan this codebase for duplicated code and fix it. Work through each category in order. For each, search the actual files (don't assume — grep and read), refactor the duplication, then verify nothing broke before moving to the next.

**Category 1 — Dead re-export shims (backend):** Search for files containing "DEPRECATED: Import from app.models" or "DEPRECATED: Import from app.schemas" in `tamio-backend/`. For each: find all imports of the deprecated path, update them to the canonical location (`app.models` or `app.schemas`), delete the shim, run `cd tamio-backend && python -m pytest tests/ -x -q`. Also delete any stale `.bak` files in the frontend.

**Category 2 — Route CRUD boilerplate (backend):** Routes in `tamio-backend/app/data/*/routes.py` repeat fetch-by-ID + ownership check, locked-field enforcement, and update-field loops. Extract shared helpers into `tamio-backend/app/data/route_utils.py`. Run tests after.

**Category 3 — Frontend formatting utilities:** Search for `formatCompact` across `tamio-frontend/src/`. Consolidate all copies into a single export in `tamio-frontend/src/lib/format.ts`. Update all import sites. Run `cd tamio-frontend && npx tsc --noEmit`.

**Category 4 — Frontend status styling functions:** Search for `get*Styles` or `get*StatusStyles` in `tamio-frontend/src/lib/api/`. Co-locate or extract a shared helper — only if it reduces code without hurting readability. Run TypeScript check after.

**Rules:** Work one category at a time. Verify before moving on. Skip resolved categories. Commit after each category.
