"""TAMI Complete Knowledge Base

This module contains ALL curated knowledge that TAMI uses to provide
accurate, relevant answers about Tamio's features and financial concepts.

Categories:
1. GLOSSARY - Financial terms and definitions
2. SCENARIO_EXPLANATIONS - What each scenario does, when to use it
3. RISK_INTERPRETATION - RED/AMBER/GREEN framework, action windows
4. BEST_PRACTICES - Situational guidance and proactive advice
5. PRODUCT_FEATURES - How Tamio features work, how-to guides
6. COMMON_SITUATIONS - Pre-built responses for frequent cases

Instructions for maintaining this file:
- Keep explanations concise but complete
- Use plain language (founders, not accountants)
- Include practical examples where helpful
- Update when product features change
"""

# =============================================================================
# 1. GLOSSARY - Financial Terms and Definitions
# =============================================================================

GLOSSARY = {
    # -------------------------------------------------------------------------
    # Core Cash Flow
    # -------------------------------------------------------------------------
    "cash_in": {
        "term": "Cash In (Income)",
        "definition": "Money expected to come into the business (e.g. client payments, settlements).",
        "category": "core_cash_flow"
    },
    "cash_out": {
        "term": "Cash Out (Costs)",
        "definition": "Money expected to leave the business (e.g. payroll, rent, contractors).",
        "category": "core_cash_flow"
    },
    "cash_balance": {
        "term": "Cash Balance",
        "definition": "The amount of cash available at a specific point in time.",
        "category": "core_cash_flow"
    },
    "starting_cash": {
        "term": "Starting Cash",
        "definition": "Cash available at the beginning of the forecast period.",
        "category": "core_cash_flow"
    },
    "ending_balance": {
        "term": "Ending Balance",
        "definition": "Cash remaining at the end of a given week in the forecast.",
        "category": "core_cash_flow"
    },
    "net_cash_change": {
        "term": "Net Cash Change",
        "definition": "Cash in minus cash out for a given period.",
        "category": "core_cash_flow"
    },
    "runway": {
        "term": "Runway",
        "definition": "How long the business can operate before cash falls below zero or a safety buffer.",
        "category": "core_cash_flow"
    },
    "cash_buffer": {
        "term": "Cash Buffer",
        "definition": "A minimum amount of cash the business aims to keep available for safety.",
        "category": "core_cash_flow"
    },
    "13_week_forecast": {
        "term": "13-Week Forecast",
        "definition": "A short-term, rolling forecast showing expected cash movements week by week.",
        "category": "core_cash_flow"
    },
    "forecast_horizon": {
        "term": "Forecast Horizon",
        "definition": "How far into the future the forecast looks.",
        "category": "core_cash_flow"
    },

    # -------------------------------------------------------------------------
    # Clients & Revenue
    # -------------------------------------------------------------------------
    "client": {
        "term": "Client",
        "definition": "A revenue relationship that generates cash inflows.",
        "category": "clients_revenue"
    },
    "client_type": {
        "term": "Client Type",
        "definition": "The way a client pays: retainer, project, usage-based, or mixed.",
        "category": "clients_revenue"
    },
    "billing_frequency": {
        "term": "Billing Frequency",
        "definition": "How often a client is billed (monthly, milestones, usage settlement).",
        "category": "clients_revenue"
    },
    "payment_terms": {
        "term": "Payment Terms",
        "definition": "How long after invoicing payment is expected (e.g. Net 30).",
        "category": "clients_revenue"
    },

    # -------------------------------------------------------------------------
    # Expenses & Obligations
    # -------------------------------------------------------------------------
    "expense_bucket": {
        "term": "Expense Bucket",
        "definition": "A grouped category of costs (e.g. Payroll, Contractors, Tools).",
        "category": "expenses_obligations"
    },
    "fixed_costs": {
        "term": "Fixed Costs",
        "definition": "Expenses that are hard to change quickly (e.g. payroll, rent).",
        "category": "expenses_obligations"
    },
    "variable_costs": {
        "term": "Variable Costs",
        "definition": "Expenses that can be adjusted with less friction (e.g. contractors, marketing).",
        "category": "expenses_obligations"
    },
    "obligation": {
        "term": "Obligation",
        "definition": "A recurring or one-off commitment to pay money in the future.",
        "category": "expenses_obligations"
    },
    "priority": {
        "term": "Priority",
        "definition": "How essential an expense is (High / Medium / Low).",
        "category": "expenses_obligations"
    },
    "stability": {
        "term": "Stability",
        "definition": "Whether an expense is predictable or varies month to month.",
        "category": "expenses_obligations"
    },
    "expected_cash_out_event": {
        "term": "Expected Cash-Out Event",
        "definition": "A specific future date where money is expected to leave the business.",
        "category": "expenses_obligations"
    },
    "cost_structure": {
        "term": "Cost Structure",
        "definition": "The overall composition of fixed vs variable costs in the business.",
        "category": "expenses_obligations"
    },

    # -------------------------------------------------------------------------
    # Scenarios & What-Ifs
    # -------------------------------------------------------------------------
    "scenario": {
        "term": "Scenario",
        "definition": "A temporary 'what if' change applied on top of the base forecast.",
        "category": "scenarios"
    },
    "base_forecast": {
        "term": "Base Forecast",
        "definition": "The forecast assuming nothing changes from today.",
        "category": "scenarios"
    },
    "scenario_forecast": {
        "term": "Scenario Forecast",
        "definition": "The forecast after applying one or more scenario layers.",
        "category": "scenarios"
    },
    "scenario_layer": {
        "term": "Scenario Layer",
        "definition": "A single change within a scenario (e.g. client loss, hiring).",
        "category": "scenarios"
    },
    "linked_changes": {
        "term": "Linked Changes",
        "definition": "Second-order effects connected to a scenario (e.g. reducing costs after losing revenue).",
        "category": "scenarios"
    },
    "effective_date": {
        "term": "Effective Date",
        "definition": "When a scenario change starts to affect cash flow.",
        "category": "scenarios"
    },
    "lag": {
        "term": "Lag",
        "definition": "A delay between a change and when its cash impact appears.",
        "category": "scenarios"
    },
    "discard_scenario": {
        "term": "Discard Scenario",
        "definition": "Removing a scenario without changing the base forecast.",
        "category": "scenarios"
    },

    # -------------------------------------------------------------------------
    # Risk & Decision Making
    # -------------------------------------------------------------------------
    "rule": {
        "term": "Rule",
        "definition": "A constraint used to assess financial safety (e.g. minimum cash buffer).",
        "category": "risk_decision"
    },
    "rule_breach": {
        "term": "Rule Breach",
        "definition": "When a forecast violates a defined rule.",
        "category": "risk_decision"
    },
    "action_window": {
        "term": "Action Window",
        "definition": "How much time remains before a rule breach occurs.",
        "category": "risk_decision"
    },
    "confidence_level": {
        "term": "Confidence Level",
        "definition": "How reliable a forecasted event is, based on data quality and history.",
        "category": "risk_decision"
    },
    "clustering_risk": {
        "term": "Clustering Risk",
        "definition": "When many cash-out events pile up in the same period.",
        "category": "risk_decision"
    },
    "downside_risk": {
        "term": "Downside Risk",
        "definition": "The potential negative impact if assumptions break.",
        "category": "risk_decision"
    },
    "liquidity_risk": {
        "term": "Liquidity Risk",
        "definition": "The risk of running out of usable cash even if the business is profitable.",
        "category": "risk_decision"
    },

    # -------------------------------------------------------------------------
    # Advanced FP&A
    # -------------------------------------------------------------------------
    "burn_rate": {
        "term": "Burn Rate",
        "definition": "The speed at which the business consumes cash over time.",
        "category": "advanced_fpa"
    },
    "working_capital": {
        "term": "Working Capital",
        "definition": "Cash tied up in receivables, payables, and short-term obligations.",
        "category": "advanced_fpa"
    },
    "sensitivity_analysis": {
        "term": "Sensitivity Analysis",
        "definition": "Testing how changes in one variable affect the overall outcome.",
        "category": "advanced_fpa"
    },
    "forecast_variance": {
        "term": "Forecast Variance",
        "definition": "The difference between expected and actual cash flows.",
        "category": "advanced_fpa"
    },
    "leading_indicator": {
        "term": "Leading Indicator",
        "definition": "A signal that predicts future performance (e.g. payment delays).",
        "category": "advanced_fpa"
    },
    "lagging_indicator": {
        "term": "Lagging Indicator",
        "definition": "A metric that confirms performance after it happens (e.g. cash balance).",
        "category": "advanced_fpa"
    },
    "operating_leverage": {
        "term": "Operating Leverage",
        "definition": "How much profits change when revenue changes, based on cost structure.",
        "category": "advanced_fpa"
    },
    "scenario_planning": {
        "term": "Scenario Planning",
        "definition": "Exploring multiple possible futures to prepare better decisions.",
        "category": "advanced_fpa"
    },
    "cost_elasticity": {
        "term": "Cost Elasticity",
        "definition": "How easily costs can scale up or down with revenue.",
        "category": "advanced_fpa"
    },
    "capital_intensity": {
        "term": "Capital Intensity",
        "definition": "How much cash is required to operate or grow the business.",
        "category": "advanced_fpa"
    },
    "cash_conversion_cycle": {
        "term": "Cash Conversion Cycle (CCC)",
        "definition": "The time it takes to turn spending into collected cash (from paying costs to receiving client payments).",
        "category": "advanced_fpa"
    },
    "days_sales_outstanding": {
        "term": "Days Sales Outstanding (DSO)",
        "definition": "Average number of days it takes to collect payment after invoicing clients.",
        "category": "advanced_fpa"
    },
    "days_payable_outstanding": {
        "term": "Days Payable Outstanding (DPO)",
        "definition": "Average number of days the business takes to pay vendors or expenses.",
        "category": "advanced_fpa"
    },
    "days_cash_on_hand": {
        "term": "Days Cash on Hand",
        "definition": "How many days the business can operate using existing cash, assuming no new income.",
        "category": "advanced_fpa"
    },
    "liquidity_coverage": {
        "term": "Liquidity Coverage",
        "definition": "Whether near-term cash inflows are sufficient to cover near-term cash outflows.",
        "category": "advanced_fpa"
    },
    "burn_multiple": {
        "term": "Burn Multiple",
        "definition": "How much cash is burned to generate one unit of net revenue growth (used to judge efficiency).",
        "category": "advanced_fpa"
    },
    "unit_economics": {
        "term": "Unit Economics",
        "definition": "Revenue and cost structure at the level of a single customer, contract, or transaction.",
        "category": "advanced_fpa"
    },
    "contribution_margin": {
        "term": "Contribution Margin",
        "definition": "Revenue remaining after variable costs, used to fund fixed costs and growth.",
        "category": "advanced_fpa"
    },
    "fixed_cost_coverage": {
        "term": "Fixed Cost Coverage",
        "definition": "Whether recurring revenue reliably covers fixed expenses like payroll and rent.",
        "category": "advanced_fpa"
    },
    "scenario_elasticity": {
        "term": "Scenario Elasticity",
        "definition": "How sensitive cash outcomes are to small changes in assumptions (e.g. delays, churn).",
        "category": "advanced_fpa"
    },
    "cost_absorption": {
        "term": "Cost Absorption",
        "definition": "The ability of revenue to 'absorb' fixed costs without increasing risk.",
        "category": "advanced_fpa"
    },
    "margin_of_safety": {
        "term": "Margin of Safety",
        "definition": "The buffer between expected cash outcomes and the minimum survivable level.",
        "category": "advanced_fpa"
    },
    "cash_stress_test": {
        "term": "Cash Stress Test",
        "definition": "A scenario designed to test how the business performs under adverse conditions.",
        "category": "advanced_fpa"
    },
    "downside_case": {
        "term": "Downside Case",
        "definition": "A pessimistic forecast based on worse-than-expected assumptions.",
        "category": "advanced_fpa"
    },
    "upside_case": {
        "term": "Upside Case",
        "definition": "An optimistic forecast based on better-than-expected assumptions.",
        "category": "advanced_fpa"
    },
    "base_case": {
        "term": "Base Case",
        "definition": "The most likely forecast given current information (Tamio's base forecast).",
        "category": "advanced_fpa"
    },
    "operating_cash_flow": {
        "term": "Operating Cash Flow",
        "definition": "Cash generated or consumed by core business operations, excluding financing.",
        "category": "advanced_fpa"
    },
    "non_operating_cash_flow": {
        "term": "Non-Operating Cash Flow",
        "definition": "Cash movements not tied to operations (e.g. loans, repayments, capital injections).",
        "category": "advanced_fpa"
    },
    "cash_timing_risk": {
        "term": "Cash Timing Risk",
        "definition": "Risk created by when cash moves, not how much moves.",
        "category": "advanced_fpa"
    },
    "forecast_confidence_band": {
        "term": "Forecast Confidence Band",
        "definition": "A conceptual range around forecasts reflecting uncertainty, not a single number.",
        "category": "advanced_fpa"
    },
    "variance_attribution": {
        "term": "Variance Attribution",
        "definition": "Understanding why actual results differ from forecast (timing, volume, mix).",
        "category": "advanced_fpa"
    },
    "structural_deficit": {
        "term": "Structural Deficit",
        "definition": "A situation where the business model consistently consumes more cash than it generates.",
        "category": "advanced_fpa"
    },
    "structural_surplus": {
        "term": "Structural Surplus",
        "definition": "A situation where recurring operations reliably generate excess cash.",
        "category": "advanced_fpa"
    },
    "capacity_constraint": {
        "term": "Capacity Constraint",
        "definition": "A limit (people, tools, time) that prevents revenue from scaling without new costs.",
        "category": "advanced_fpa"
    },
    "incremental_cost": {
        "term": "Incremental Cost",
        "definition": "The additional cost incurred by making a specific change (e.g. adding a client).",
        "category": "advanced_fpa"
    },
    "incremental_revenue": {
        "term": "Incremental Revenue",
        "definition": "The additional revenue generated by a specific change or decision.",
        "category": "advanced_fpa"
    },
    "payback_period": {
        "term": "Payback Period",
        "definition": "How long it takes for a decision (hire, tool, campaign) to recover its cash cost.",
        "category": "advanced_fpa"
    },
    "capital_allocation": {
        "term": "Capital Allocation",
        "definition": "How cash is deliberately assigned across growth, safety, and optionality.",
        "category": "advanced_fpa"
    },
}


# =============================================================================
# 2. SCENARIO EXPLANATIONS
# =============================================================================

SCENARIO_EXPLANATIONS = {
    "overview": """
Every scenario in Tamio has two layers:

1. **Primary change**: The thing that just happened or might happen (e.g. client pays late, hire made).
2. **Second-order effects**: The consequences of that change (cash gaps, cost mismatches, capacity issues).

Tamio always prompts for second-order effects because:
- Most cash crises don't come from the first event
- They come from what wasn't adjusted afterward

**Important**: Scenarios never overwrite truth:
- Base forecast = current reality
- Scenarios = hypothetical layers
""",

    "payment_delay": {
        "scenario_type": "Payment Delay (Cash In)",
        "what_it_does": "Shifts expected cash-in events backward; optionally splits partial payments.",
        "when_to_use": {
            "user_signals": [
                "Viewing a specific client repeatedly",
                "Opening invoices",
                "Checking near-term forecast dips"
            ],
            "predictive_signals": [
                "Client historically pays late (e.g. avg +7–14 days)",
                "Increasing variance in payment timing",
                "Recent partial payments"
            ]
        },
        "typical_impact": "Short-term liquidity pressure; buffer breach risk.",
        "second_order_effects": [
            "Delay vendor payments",
            "Reduce discretionary spend",
            "Assess future cash clustering"
        ],
        "common_mistake": "Assuming timing doesn't matter if revenue is 'booked.'"
    },

    "client_loss": {
        "scenario_type": "Client Loss",
        "what_it_does": "Removes all future cash-in events from an end date.",
        "when_to_use": {
            "user_signals": [
                "Repeatedly viewing a single client",
                "Editing scope",
                "Exploring downside scenarios"
            ],
            "predictive_signals": [
                "Rising churn risk tag",
                "Declining usage/project velocity",
                "Delayed payments + shrinking deal size"
            ]
        },
        "typical_impact": "Structural revenue loss; runway compression.",
        "second_order_effects": [
            "Contractor/tool reductions",
            "Fixed cost reassessment with lag"
        ],
        "common_mistake": "Removing revenue without adjusting costs."
    },

    "client_gain": {
        "scenario_type": "Client Gain",
        "what_it_does": "Adds new revenue agreements and expected cash-in events.",
        "when_to_use": {
            "user_signals": [
                "Adding a new client manually",
                "Viewing upside scenarios",
                "Editing forecast assumptions"
            ],
            "predictive_signals": [
                "Pipeline conversion patterns",
                "Historic win-rate timing",
                "Past onboarding costs"
            ]
        },
        "typical_impact": "Improved runway; inflow uplift.",
        "second_order_effects": [
            "Hiring",
            "Contractors",
            "Tools",
            "Onboarding costs"
        ],
        "common_mistake": "Treating new revenue as cost-free."
    },

    "client_change": {
        "scenario_type": "Client Change (Upsell / Downsell / Scope Change)",
        "what_it_does": "Modifies future cash-in amounts from an effective date.",
        "when_to_use": {
            "user_signals": [
                "Editing client cards",
                "Revisiting the same agreement across sessions"
            ],
            "predictive_signals": [
                "Historic scope creep",
                "Usage variance",
                "Prior upsell/downsell frequency"
            ]
        },
        "typical_impact": "Margin volatility; forecast shape change.",
        "second_order_effects": [
            "Delivery costs",
            "Contractor usage",
            "Tooling changes"
        ],
        "common_mistake": "Updating revenue but ignoring cost sensitivity."
    },

    "hiring": {
        "scenario_type": "Hiring (Payroll Gain)",
        "what_it_does": "Adds recurring payroll obligations and one-off hiring costs.",
        "when_to_use": {
            "user_signals": [
                "Viewing runway repeatedly",
                "Exploring growth scenarios"
            ],
            "predictive_signals": [
                "Revenue growth trends",
                "Sustained utilisation pressure",
                "Prior hiring timing vs cash stress"
            ]
        },
        "typical_impact": "Higher fixed burn; reduced flexibility.",
        "second_order_effects": [
            "Revenue targets",
            "Buffer sufficiency checks"
        ],
        "common_mistake": "Hiring before validating cash support."
    },

    "firing": {
        "scenario_type": "Firing (Payroll Loss)",
        "what_it_does": "Removes payroll costs; models severance.",
        "when_to_use": {
            "user_signals": [
                "Repeated downside scenario testing",
                "Cost page focus"
            ],
            "predictive_signals": [
                "Buffer breach probability",
                "Sustained negative cash flow",
                "Declining revenue trend"
            ]
        },
        "typical_impact": "Short-term cash relief.",
        "second_order_effects": [
            "Delivery slowdown",
            "Revenue impact"
        ],
        "common_mistake": "Treating layoffs as pure savings."
    },

    "contractor_gain": {
        "scenario_type": "Contractor Gain",
        "what_it_does": "Adds contractor cash-out events (fixed or variable).",
        "when_to_use": {
            "user_signals": [
                "Editing project costs",
                "Capacity planning behaviour"
            ],
            "predictive_signals": [
                "Historic contractor ramp patterns",
                "Project overruns",
                "Revenue-linked cost elasticity"
            ]
        },
        "typical_impact": "Variable cost increase; margin sensitivity.",
        "second_order_effects": [
            "Client linkage",
            "Ramp lag"
        ],
        "common_mistake": "Starting contractors before cash arrives."
    },

    "contractor_loss": {
        "scenario_type": "Contractor Loss",
        "what_it_does": "Reduces or removes contractor spend.",
        "when_to_use": {
            "user_signals": [
                "Cost-cutting exploration",
                "Scenario iteration"
            ],
            "predictive_signals": [
                "Project completion history",
                "Revenue deceleration"
            ]
        },
        "typical_impact": "Short-term savings.",
        "second_order_effects": [
            "Delivery delays",
            "Milestone slippage"
        ],
        "common_mistake": "Cutting capacity without modeling delivery impact."
    },

    "increased_expense": {
        "scenario_type": "Increased Expense",
        "what_it_does": "Adds new one-off or recurring expenses.",
        "when_to_use": {
            "user_signals": [
                "Adding tools",
                "Marketing spend",
                "Tax items"
            ],
            "predictive_signals": [
                "Seasonal spend patterns",
                "Prior ROI lag",
                "Buffer sensitivity"
            ]
        },
        "typical_impact": "Faster buffer drawdown.",
        "second_order_effects": [
            "Capex/buffer gating",
            "Timing sensitivity"
        ],
        "common_mistake": "Adding spend without liquidity checks."
    },

    "decreased_expense": {
        "scenario_type": "Decreased Expense",
        "what_it_does": "Reduces or cancels future expenses.",
        "when_to_use": {
            "user_signals": [
                "Cost review behaviour",
                "Repeated forecast stress checks"
            ],
            "predictive_signals": [
                "Contract expiry dates",
                "Discretionary spend elasticity"
            ]
        },
        "typical_impact": "Runway extension.",
        "second_order_effects": [
            "Termination fees",
            "Notice periods"
        ],
        "common_mistake": "Ignoring contractual lock-ins."
    },

    "payment_delay_out": {
        "scenario_type": "Payment Delay (Cash Out)",
        "what_it_does": "Shifts outgoing payments; supports partial payments.",
        "when_to_use": {
            "user_signals": [
                "Reviewing near-term cash dips",
                "Vendor pages"
            ],
            "predictive_signals": [
                "Prior vendor delay tolerance",
                "Clustering risk detection"
            ]
        },
        "typical_impact": "Temporary liquidity relief.",
        "second_order_effects": [
            "Catch-up schedules",
            "Payment clustering risk"
        ],
        "common_mistake": "Delaying payments without a recovery plan."
    }
}


# =============================================================================
# 3. RISK INTERPRETATION
# =============================================================================

RISK_INTERPRETATION = {
    "overview": """
Tamio uses a Red / Amber / Green framework across forecasts, scenarios, and insights.
Risk is contextual, not absolute.

Tamio considers:
- Cash buffer rules (user-defined)
- Fixed vs variable cost mix
- Timing of cash-in vs cash-out
- Historical behaviour (e.g. payment delays)
- Scenario-adjusted forecasts (not just base case)

A RED state for one company might be AMBER for another with:
- Lower fixed costs
- More flexible expenses
- Faster receivables
""",

    "green": {
        "status": "GREEN — Stable",
        "what_it_means": [
            "Cash position is healthy",
            "Buffer rules are respected",
            "No near-term liquidity stress"
        ],
        "typical_conditions": [
            "≥ buffer threshold maintained",
            "Cash-in covers fixed cash-out",
            "Forecast volatility is low"
        ],
        "user_guidance": [
            "No action required",
            "Good time for planning, growth scenarios, or investment decisions"
        ],
        "tami_tone": "You're in a stable position. Nothing urgent to act on. It's a good time for growth."
    },

    "amber": {
        "status": "AMBER — Watch Closely",
        "what_it_means": [
            "Risk is emerging but still manageable",
            "Action window exists, but it's not closing yet"
        ],
        "typical_conditions": [
            "Buffer likely breached in 4–12 weeks",
            "One or more delayed payments",
            "Cost growth outpacing inflows",
            "Increased forecast variance"
        ],
        "user_guidance": [
            "Review scenarios",
            "Prepare contingency actions",
            "Decide what levers are available if conditions worsen"
        ],
        "tami_tone": "This isn't urgent yet, but it's worth preparing."
    },

    "red": {
        "status": "RED — Action Required",
        "what_it_means": [
            "Material liquidity risk is imminent or already present",
            "Delay reduces available options"
        ],
        "typical_conditions": [
            "Buffer breached or projected breach within 0–4 weeks",
            "Payroll coverage at risk",
            "Cash-out exceeds cash-in with no recovery path",
            "Clustering of delayed payments"
        ],
        "user_guidance": [
            "Immediate scenario modelling recommended",
            "Prioritise reversible actions first",
            "Confirm which decisions need to be made now vs deferred"
        ],
        "tami_tone": "This needs attention now. Let's look at your options."
    },

    "action_window": {
        "concept": "Action Window",
        "description": """
The action window is the amount of time remaining before:
- A risk becomes irreversible, or
- Available corrective actions meaningfully shrink

It answers: "How much time do I have to change the outcome?"
""",
        "windows": {
            "> 8 weeks": {
                "meaning": "Wide window",
                "typical_response": "Strategic planning, scenario exploration"
            },
            "4-8 weeks": {
                "meaning": "Narrowing",
                "typical_response": "Prepare actions, soft adjustments"
            },
            "0-4 weeks": {
                "meaning": "Critical",
                "typical_response": "Execute decisions, protect liquidity"
            },
            "0 weeks": {
                "meaning": "Closed",
                "typical_response": "Damage control, recovery mode"
            }
        }
    }
}


# =============================================================================
# 4. BEST PRACTICES
# =============================================================================

BEST_PRACTICES = {
    "liquidity_runway": {
        "category": "Liquidity & Runway Discipline",
        "practices": [
            "If runway < 8 weeks, prioritise actions that buy time (delay cash-out, accelerate cash-in) before making irreversible cuts.",
            "Always plan to act with ≥4 weeks of runway remaining — decisions made at zero runway are almost always worse.",
            "Treat cash buffer breaches as timing problems first, not profitability problems.",
            "Avoid operating continuously below your buffer — short breaches are manageable, sustained breaches are structural.",
            "Run at least one downside scenario at all times so risks are never a surprise."
        ]
    },

    "revenue_cash_in": {
        "category": "Revenue & Cash-In Management",
        "practices": [
            "Do not rely on 'expected' revenue to fund fixed costs unless payment behaviour is consistently on time.",
            "If a client pays late twice in a row, model delays as the new baseline until behaviour improves.",
            "Concentration risk matters — losing one large client often hurts more than five small ones.",
            "Before committing spend, check cash-in timing, not just revenue totals.",
            "Separate delivery confidence from payment confidence — they are not the same risk."
        ]
    },

    "cost_structure": {
        "category": "Cost Structure & Flexibility",
        "practices": [
            "Protect flexibility before cutting deeply — variable costs are safer levers than fixed ones.",
            "If fixed costs exceed predictable cash-in, you are operating in a fragile state.",
            "Tag costs by reversibility, not just category (payroll vs tools isn't enough).",
            "Avoid stacking new fixed costs during periods of forecast volatility.",
            "Delay discretionary spend first, reduce essential spend last."
        ]
    },

    "hiring_capacity": {
        "category": "Hiring & Capacity Decisions",
        "practices": [
            "Before hiring, confirm the hire can be supported without future revenue assumptions.",
            "If a hire depends on 'winning the next deal', model the downside where that deal slips.",
            "Prefer staged or contract-based capacity increases when runway is uncertain.",
            "Hiring decisions should be scenario-tested, not instinct-driven."
        ]
    },

    "scenario_hygiene": {
        "category": "Scenario & Decision Hygiene",
        "practices": [
            "Never act on a single forecast — always compare base vs scenario.",
            "If the same scenario keeps appearing, it's likely becoming your base case.",
            "Document why a decision was made — future you will need that context."
        ]
    },

    "tami_usage_note": """
How Tamio Uses These:
- Surfaced only when relevant
- Paired with supporting data
- Framed as considerations, not instructions
- Designed to reduce panic and improve timing
"""
}


# =============================================================================
# 5. PRODUCT FEATURES
# =============================================================================

PRODUCT_FEATURES = {
    "clients": {
        "what_it_is": """
Clients represent your revenue sources in Tamio. Each client generates expected
cash inflows that feed into your 13-week forecast.
""",
        "how_to_add": """
To add a client:
1. Go to Clients & Expenses → Clients tab
2. Click "Add Client"
3. Enter the client name and select the billing type:
   - **Retainer**: Fixed monthly amount (e.g., $5,000/month)
   - **Project**: One-time or milestone-based payments
   - **Usage**: Variable based on consumption (e.g., hourly billing)
   - **Mixed**: Combination of the above
4. Enter the billing amount and payment terms
5. Set the payment behavior and churn risk (see below)
6. Save - Tamio will automatically generate forecast events
""",
        "fields": {
            "client_type": {
                "description": "How this client is billed",
                "options": {
                    "retainer": "Fixed recurring amount (monthly/weekly). Best for predictable revenue like subscriptions or ongoing services.",
                    "project": "One-time or milestone payments. Use for fixed-scope projects with defined deliverables.",
                    "usage": "Variable billing based on consumption. Use for hourly work or usage-based pricing.",
                    "mixed": "Combination of billing types. Use when a client has both retainer and project work."
                }
            },
            "payment_behavior": {
                "description": "How reliably this client pays on time. Affects scenario suggestions.",
                "options": {
                    "on_time": "Client consistently pays within terms. Forecast treats this revenue as reliable.",
                    "delayed": "Client typically pays late. Tamio may suggest 'payment delay' scenarios to stress-test.",
                    "unknown": "No payment history yet. Default for new clients."
                },
                "impact": "Clients marked as 'delayed' will trigger scenario suggestions to model late payments."
            },
            "churn_risk": {
                "description": "Likelihood this client will leave. Affects scenario suggestions.",
                "options": {
                    "low": "Stable, long-term relationship. Unlikely to churn.",
                    "medium": "Normal business relationship. Standard assumptions.",
                    "high": "At-risk client. May leave soon."
                },
                "impact": "Clients marked as 'high' churn risk will trigger 'client loss' scenario suggestions."
            }
        },
        "tips": [
            "Set payment_behavior based on actual history - it helps TAMI suggest relevant scenarios",
            "High churn_risk clients should have 'client loss' scenarios modeled",
            "If a client's revenue is uncertain, set churn_risk to 'high' even if relationship is good"
        ]
    },

    "expenses": {
        "what_it_is": """
Expense buckets represent your recurring cash outflows - payroll, rent, software,
contractors, etc. They generate expected cash-out events in your forecast.
""",
        "how_to_add": """
To add an expense:
1. Go to Clients & Expenses → Expenses tab
2. Click "Add Expense"
3. Enter the expense name and select the category:
   - Payroll, Rent, Contractor, Software, Marketing, Other
4. Choose the type:
   - **Fixed**: Same amount every period (e.g., salary, rent)
   - **Variable**: Amount fluctuates (e.g., commission, usage-based)
5. Enter the monthly amount
6. Set the priority level (see below)
7. Save - Tamio will generate forecast events
""",
        "fields": {
            "category": {
                "description": "What type of expense this is",
                "options": {
                    "payroll": "Salaries, wages, benefits. Usually highest priority.",
                    "rent": "Office space, facilities. Usually fixed and essential.",
                    "contractor": "Freelancers, agencies. Often tied to specific projects.",
                    "software": "SaaS subscriptions, tools. Often discretionary.",
                    "marketing": "Advertising, events, content. Usually discretionary.",
                    "other": "Anything else - travel, supplies, etc."
                }
            },
            "bucket_type": {
                "description": "Whether the amount is predictable",
                "options": {
                    "fixed": "Same amount every period. Use for salaries, rent, fixed subscriptions.",
                    "variable": "Amount changes. Use for usage-based costs, commissions, hourly contractors."
                }
            },
            "priority": {
                "description": "How critical this expense is. Affects scenario suggestions and buffer calculations.",
                "options": {
                    "high/essential": "Must be paid. Cutting this would seriously harm the business. Examples: payroll, rent, critical infrastructure.",
                    "medium/important": "Important but has some flexibility. Examples: software subscriptions, marketing.",
                    "low/discretionary": "Nice to have. Can be reduced or eliminated if cash is tight. Examples: perks, non-essential tools, travel."
                },
                "impact": "Low-priority expenses are suggested for reduction when cash is tight. High-priority expenses are always included in buffer calculations."
            }
        },
        "tips": [
            "Be honest about priority - it helps TAMI suggest realistic cost-cutting scenarios",
            "Payroll should almost always be 'high' priority",
            "If you're not sure, start with 'medium' and adjust based on scenario analysis"
        ]
    },

    "forecasts": {
        "what_it_is": """
The 13-week forecast shows your projected cash position week by week. It's the
core of Tamio - everything else (scenarios, rules, TAMI analysis) is built on this.
""",
        "how_it_works": """
The forecast is calculated automatically from your data:

1. **Starting cash**: Sum of all your connected bank accounts
2. **Cash events**: Generated from your clients (cash in) and expenses (cash out)
3. **Week-by-week projection**:
   - Week 1: Starting cash + cash in - cash out = ending balance
   - Week 2: Previous ending balance + cash in - cash out = new ending balance
   - ...repeat for 13 weeks

The forecast updates automatically when you:
- Add/edit clients or expenses
- Connect bank accounts
- Run scenarios
""",
        "key_metrics": {
            "runway_weeks": {
                "what": "How many weeks until your cash hits zero (if current trends continue)",
                "interpretation": {
                    "13+ weeks": "Healthy - you won't run out in the forecast window",
                    "8-12 weeks": "Monitor closely - start planning",
                    "4-8 weeks": "Urgent - take action now",
                    "1-4 weeks": "Critical - immediate intervention needed"
                }
            },
            "lowest_cash_week": {
                "what": "Which week has your tightest cash position",
                "interpretation": "This is when you're most vulnerable. Plan around this week."
            },
            "lowest_cash_amount": {
                "what": "The minimum cash balance in your 13-week forecast",
                "interpretation": "Compare this to your buffer requirement. If it's below your buffer, you'll see a rule breach."
            }
        },
        "tips": [
            "Check the forecast weekly - it updates as time passes",
            "The 'lowest cash week' is your planning target - focus scenarios on improving that week",
            "If runway is below 8 weeks, prioritize cash preservation"
        ]
    },

    "scenarios": {
        "what_it_is": """
Scenarios let you model "what if" situations without affecting your base forecast.
They help you stress-test your cash position and plan for different futures.
""",
        "how_to_create": """
You can create scenarios in two ways:

**1. Ask TAMI**:
   - "What if I lose Acme Corp?"
   - "Show me what happens if payroll is delayed 2 weeks"
   - TAMI will create the scenario for you

**2. Manual creation**:
   - Go to Scenarios page
   - Click "New Scenario"
   - Select the scenario type and configure parameters
""",
        "scenario_types": {
            "payment_delay": {
                "what": "Model a client paying late",
                "when_to_use": "When you're worried about a client's payment timing",
                "parameters": ["Client to delay", "Delay duration (weeks)", "Partial payment (optional)"],
                "example": "Acme usually pays 2 weeks late - model that to see impact on week 6"
            },
            "client_loss": {
                "what": "Model losing a client entirely",
                "when_to_use": "Stress test against losing revenue, especially for high churn_risk clients",
                "parameters": ["Client to lose", "Effective date", "Linked cost reductions (optional)"],
                "example": "What if Tech Startup churns next month? Do we need to cut costs?"
            },
            "client_gain": {
                "what": "Model winning a new client",
                "when_to_use": "Plan for expected new revenue or model sales targets",
                "parameters": ["Revenue amount", "Start date", "Billing type", "Linked costs (optional)"],
                "example": "If we close the deal in pipeline, how does that change runway?"
            },
            "client_change": {
                "what": "Model upsell or downsell with existing client",
                "when_to_use": "When client scope is changing",
                "parameters": ["Client", "New amount or delta", "Effective date"],
                "example": "Acme wants to reduce scope by 20% starting March"
            },
            "hiring": {
                "what": "Model adding an employee",
                "when_to_use": "Plan headcount additions",
                "parameters": ["Monthly cost (fully loaded)", "Start date", "One-time costs (optional)"],
                "example": "Can we afford to hire a senior engineer at $12k/month?"
            },
            "firing": {
                "what": "Model removing an employee",
                "when_to_use": "Model cost reduction through layoffs",
                "parameters": ["Monthly savings", "End date", "Severance costs (optional)"],
                "example": "What's the impact of reducing team by 1 person?"
            },
            "contractor_gain": {
                "what": "Model adding contractor costs",
                "when_to_use": "Plan for new contractor engagements",
                "parameters": ["Monthly cost", "Start date", "Linked to client (optional)"],
                "example": "We need a contractor for the new project - $5k/month"
            },
            "contractor_loss": {
                "what": "Model removing contractor costs",
                "when_to_use": "Model cost reduction",
                "parameters": ["Contractor/bucket to reduce", "End date or reduction %"],
                "example": "End the design contractor engagement to save $3k/month"
            },
            "increased_expense": {
                "what": "Model new or increased expenses",
                "when_to_use": "Plan for new costs or price increases",
                "parameters": ["Category", "Amount", "One-time vs recurring", "Start date"],
                "example": "AWS costs increasing by $500/month starting next quarter"
            },
            "decreased_expense": {
                "what": "Model reducing expenses",
                "when_to_use": "Plan cost cuts",
                "parameters": ["Expense to reduce", "Reduction amount or %", "Effective date"],
                "example": "Cancel the $200/month tool we don't use"
            },
            "payment_delay_out": {
                "what": "Model delaying your payments to vendors",
                "when_to_use": "Preserve cash by pushing out payments",
                "parameters": ["Vendor/expense to delay", "Delay duration"],
                "example": "Delay software payments by 2 weeks to bridge a cash gap"
            }
        },
        "scenario_workflow": """
1. **Draft**: Scenario is being configured
2. **Active**: Ready to view and evaluate against rules
3. **Saved**: Keep for reference without committing
4. **Confirmed**: Move to actual plan (affects base forecast)
5. **Discarded**: Rejected, archived

You can stack multiple scenarios to see combined effects:
"What if we lose Client A AND reduce contractors AND delay software payments?"
""",
        "tips": [
            "Always model 'client loss' for your highest-revenue clients",
            "Stack scenarios to find the combination that works",
            "Use 'Confirm' only when you're actually making the change - it affects your base forecast"
        ]
    },

    "rules": {
        "what_it_is": """
Financial rules are safety guardrails that alert you when your forecast crosses
dangerous thresholds. Currently, Tamio supports the "minimum cash buffer" rule.
""",
        "minimum_cash_buffer": {
            "what": "Ensures you maintain X months of operating expenses in cash",
            "how_calculated": """
1. Calculate monthly operating expenses (sum of all expense buckets)
2. Multiply by the number of months you want as buffer (typically 3)
3. Compare every week's ending balance to this threshold
4. If any week falls below the threshold → BREACH
""",
            "example": """
Monthly expenses: $50,000
Buffer months: 3
Required buffer: $150,000

If Week 6 shows ending balance of $120,000:
→ BREACH: $30,000 below required buffer
→ Severity: Depends on how soon (Week 6 = AMBER)
→ Action window: 5 weeks to fix
""",
            "severity_levels": {
                "green": "All good. No breach detected, minimum balance is above 80% of buffer.",
                "amber": "Warning. Either approaching the threshold OR breach is 5+ weeks away. Time to plan.",
                "red": "Critical. Breach within 4 weeks or already below buffer. Take action now."
            },
            "action_window": "The number of weeks you have before the breach occurs. Use this time to take corrective action."
        },
        "tips": [
            "3 months is a common buffer for startups - adjust based on your risk tolerance",
            "If you're frequently breaching, either increase revenue or cut expenses",
            "Use scenarios to find the combination that keeps you in the green"
        ]
    },

    "cash_accounts": {
        "what_it_is": """
Cash accounts represent your actual bank accounts. The sum of all account balances
is your starting cash position for the forecast.
""",
        "how_to_add": """
You can add cash accounts in two ways:

**1. Connect via Xero**:
   - Go to Settings → Integrations → Xero
   - Authorize Tamio to access your Xero account
   - Bank accounts sync automatically

**2. Manual entry**:
   - Go to Dashboard or Settings
   - Add account name and current balance
   - Update balance regularly for accurate forecasts
""",
        "tips": [
            "Connect Xero for automatic balance updates",
            "Include all accounts that hold operating cash",
            "Don't include investment accounts or restricted funds unless they're truly available"
        ]
    },

    "xero_integration": {
        "what_it_is": """
Tamio integrates with Xero to automatically sync your financial data - bank accounts,
invoices, bills, and contacts.
""",
        "what_syncs": {
            "from_xero": [
                "Bank account balances",
                "Invoices (become client revenue events)",
                "Bills (become expense events)",
                "Contacts (become clients or vendors)",
                "Repeating invoices and bills"
            ],
            "to_xero": [
                "New contacts created in Tamio",
                "Invoice updates (if enabled)"
            ]
        },
        "how_to_connect": """
1. Go to Settings → Integrations
2. Click "Connect Xero"
3. Log into your Xero account and authorize Tamio
4. Select which organization to connect (if you have multiple)
5. Initial sync runs automatically
6. Data refreshes periodically or on-demand
""",
        "sync_status": {
            "synced": "Data matches between Tamio and Xero",
            "pending_push": "Tamio has changes to send to Xero",
            "pending_pull": "Xero has changes to pull into Tamio",
            "conflict": "Data differs and needs manual resolution",
            "error": "Sync failed - check connection"
        },
        "tips": [
            "Xero is the source of truth for historical data",
            "Manual edits in Tamio won't override Xero-synced fields",
            "Re-sync if you've made changes in Xero that aren't showing"
        ]
    }
}


# =============================================================================
# 6. COMMON SITUATIONS
# =============================================================================

COMMON_SITUATIONS = {
    "losing_big_client": {
        "situation": "Losing a Big Client",
        "description": "Your largest or one of your largest clients is at risk of churning or has already churned.",
        "key_questions": [
            "What percentage of revenue does this client represent?",
            "Are there linked costs that can be reduced?",
            "How much runway do you lose without this client?"
        ],
        "recommended_actions": [
            "Create a 'client loss' scenario immediately",
            "Model linked cost reductions (contractors, tools tied to that client)",
            "Check if remaining clients can cover fixed costs",
            "Identify discretionary expenses that can be paused"
        ],
        "tami_response_guidance": "Focus on quantifying the impact first, then explore mitigation options. Don't panic - show the numbers."
    },

    "late_payments": {
        "situation": "Late Payments / Cash Timing Issues",
        "description": "One or more clients are paying later than expected, creating short-term cash pressure.",
        "key_questions": [
            "Is this a one-time delay or a pattern?",
            "Which weeks are most affected?",
            "Can you delay any outgoing payments to compensate?"
        ],
        "recommended_actions": [
            "Create a 'payment delay' scenario to see the impact",
            "Check for payment clustering (multiple late payments in same week)",
            "Model delaying discretionary vendor payments",
            "If pattern repeats, update the client's payment_behavior to 'delayed'"
        ],
        "tami_response_guidance": "Treat as a timing problem, not a revenue problem. Show which weeks are affected and what buffer looks like."
    },

    "seasonal_dips": {
        "situation": "Seasonal Cash Flow Dips",
        "description": "Predictable periods where cash inflows drop or outflows spike (e.g., holiday seasons, Q4 slowdowns).",
        "key_questions": [
            "When does the dip typically occur?",
            "How deep is the dip compared to your buffer?",
            "Can you pre-position cash before the dip?"
        ],
        "recommended_actions": [
            "Build scenarios for the seasonal period",
            "Consider delaying discretionary spend into the dip period",
            "Accelerate collections before the dip",
            "Ensure buffer is adequate for the seasonal low point"
        ],
        "tami_response_guidance": "Normalize seasonal patterns - this is expected. Focus on whether buffer covers the dip."
    },

    "considering_hiring": {
        "situation": "Considering a New Hire",
        "description": "Thinking about adding headcount but unsure if cash position supports it.",
        "key_questions": [
            "What's the fully-loaded monthly cost?",
            "Are there one-time hiring costs?",
            "Does the hire depend on winning new revenue?",
            "What's the runway impact?"
        ],
        "recommended_actions": [
            "Create a 'hiring' scenario with full costs",
            "Model the downside: what if expected revenue doesn't arrive?",
            "Check if hire can be supported by current cash alone",
            "Consider contractor-first approach if runway is tight"
        ],
        "tami_response_guidance": "Don't just show cost - show runway impact. Ask if the hire depends on future revenue assumptions."
    },

    "need_to_cut_costs": {
        "situation": "Need to Cut Costs",
        "description": "Cash position is tight and cost reduction is necessary.",
        "key_questions": [
            "Which costs are discretionary vs essential?",
            "What's the fastest lever to pull?",
            "Are there contractual lock-ins on any expenses?",
            "What's the delivery/revenue impact of cuts?"
        ],
        "recommended_actions": [
            "Start with discretionary expenses (low priority)",
            "Model contractor reductions before payroll cuts",
            "Check for termination fees or notice periods",
            "Stack multiple small cuts to see cumulative effect",
            "Delay vendor payments as a bridge while cutting"
        ],
        "tami_response_guidance": "Guide through priority order: discretionary first, then variable, then fixed. Show cumulative impact of stacked scenarios."
    },

    "runway_below_8_weeks": {
        "situation": "Runway Below 8 Weeks",
        "description": "Critical situation where cash runway is dangerously short.",
        "key_questions": [
            "What's the exact runway?",
            "What are the biggest cash-out items in the next 8 weeks?",
            "Are there any receivables that can be accelerated?",
            "What fixed costs can be deferred or cut?"
        ],
        "recommended_actions": [
            "Immediately model all available cost cuts",
            "Accelerate any outstanding receivables",
            "Delay all non-essential vendor payments",
            "Consider payroll alternatives (reduced hours, deferred comp)",
            "Explore bridge financing options"
        ],
        "tami_response_guidance": "This is RED status. Be direct but calm. Focus on actionable options, not panic. Prioritize reversible actions."
    },

    "buffer_breach_warning": {
        "situation": "Buffer Breach Warning",
        "description": "Forecast shows you'll fall below your cash buffer threshold.",
        "key_questions": [
            "When does the breach occur?",
            "How far below the buffer?",
            "What's the action window?",
            "Is this temporary or structural?"
        ],
        "recommended_actions": [
            "Determine if breach is timing-based or structural",
            "Model scenarios to avoid or minimize the breach",
            "If temporary: delay expenses, accelerate receivables",
            "If structural: need to adjust cost base or increase revenue"
        ],
        "tami_response_guidance": "Explain the difference between timing breach and structural breach. A one-week dip is different from sustained underfunding."
    }
}


# =============================================================================
# 7. HOW-TO GUIDES
# =============================================================================

HOW_TO_GUIDES = {
    "add_a_client": {
        "question": "How do I add a client?",
        "answer": PRODUCT_FEATURES["clients"]["how_to_add"]
    },
    "add_an_expense": {
        "question": "How do I add an expense?",
        "answer": PRODUCT_FEATURES["expenses"]["how_to_add"]
    },
    "create_a_scenario": {
        "question": "How do I create a scenario?",
        "answer": PRODUCT_FEATURES["scenarios"]["how_to_create"]
    },
    "connect_xero": {
        "question": "How do I connect Xero?",
        "answer": PRODUCT_FEATURES["xero_integration"]["how_to_connect"]
    },
    "understand_forecast": {
        "question": "How does the forecast work?",
        "answer": PRODUCT_FEATURES["forecasts"]["how_it_works"]
    },
    "understand_runway": {
        "question": "What is runway and how is it calculated?",
        "answer": """
Runway is the number of weeks until your cash hits zero, assuming current trends continue.

**Calculation:**
Tamio looks at each week's ending balance in the 13-week forecast. The first week where
the ending balance hits zero (or goes negative) determines your runway.

**Interpretation:**
- 13+ weeks: You won't run out in the forecast window
- 8-12 weeks: Monitor closely and start planning
- 4-8 weeks: Urgent - take action to extend runway
- 1-4 weeks: Critical - immediate intervention needed

**How to extend runway:**
1. Accelerate revenue (close deals faster, collect payments sooner)
2. Reduce expenses (cut discretionary costs, delay non-essential spending)
3. Raise capital (if other options aren't sufficient)
"""
    },
    "understand_buffer_rule": {
        "question": "What is the cash buffer rule?",
        "answer": PRODUCT_FEATURES["rules"]["minimum_cash_buffer"]["what"] + "\n\n" +
                  PRODUCT_FEATURES["rules"]["minimum_cash_buffer"]["how_calculated"]
    },
    "model_client_loss": {
        "question": "How do I model losing a client?",
        "answer": """
To model losing a client:

**Option 1 - Ask TAMI:**
Just say "What if I lose [Client Name]?" and TAMI will create the scenario.

**Option 2 - Manual:**
1. Go to Scenarios
2. Create new scenario → "Client Loss"
3. Select the client
4. Set the effective date (when they stop paying)
5. Optionally add linked cost reductions (e.g., reduce contractors who worked on that client)
6. View the impact on your forecast

**What you'll see:**
- How your ending balance changes week by week
- Whether it triggers a buffer rule breach
- How many weeks of runway you lose
- Suggested actions to mitigate
"""
    },
    "model_hiring": {
        "question": "How do I model hiring someone?",
        "answer": """
To model adding headcount:

**Option 1 - Ask TAMI:**
Say "What if I hire someone at $X/month starting [date]?"

**Option 2 - Manual:**
1. Go to Scenarios
2. Create new scenario → "Hiring"
3. Enter the monthly cost (fully loaded - salary + benefits + taxes)
4. Set the start date
5. Optionally add one-time costs (recruiter fee, equipment, onboarding)
6. View the impact

**Tip:** Include ALL costs - a $100k salary often costs $120-140k fully loaded.
"""
    },
    "improve_runway": {
        "question": "How do I extend my runway?",
        "answer": """
To extend runway, you need to either increase cash in or decrease cash out:

**Increase cash in:**
- Model new client wins (scenario: client_gain)
- Accelerate payment collection (scenario: reduce payment delays)
- Upsell existing clients (scenario: client_change)

**Decrease cash out:**
- Cut discretionary expenses first (scenario: decreased_expense)
- Reduce contractor costs (scenario: contractor_loss)
- Delay vendor payments temporarily (scenario: payment_delay_out)
- Last resort: reduce headcount (scenario: firing)

**Use TAMI:**
Ask "How can I extend runway to X weeks?" and TAMI will suggest scenarios.

**Stack scenarios:**
Try combinations to find what works: "What if I reduce software costs AND delay marketing spend AND lose one contractor?"
"""
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_glossary_term(term: str) -> dict | None:
    """Get a glossary definition by term key."""
    return GLOSSARY.get(term)


def get_glossary_by_category(category: str) -> list[dict]:
    """Get all glossary terms in a category."""
    return [term for term in GLOSSARY.values() if term.get("category") == category]


def get_scenario_explanation(scenario_type: str) -> dict | None:
    """Get detailed explanation for a scenario type."""
    return SCENARIO_EXPLANATIONS.get(scenario_type)


def get_risk_status(status: str) -> dict | None:
    """Get risk interpretation for a status (green/amber/red)."""
    return RISK_INTERPRETATION.get(status.lower())


def get_best_practices(category: str = None) -> dict | list:
    """Get best practices, optionally filtered by category."""
    if category:
        return BEST_PRACTICES.get(category)
    return BEST_PRACTICES


def get_feature_knowledge(feature_name: str) -> dict | None:
    """Get knowledge about a specific product feature."""
    return PRODUCT_FEATURES.get(feature_name)


def get_common_situation(situation_key: str) -> dict | None:
    """Get guidance for a common situation."""
    return COMMON_SITUATIONS.get(situation_key)


def get_how_to_guide(topic: str) -> dict | None:
    """Get a how-to guide for a specific topic."""
    return HOW_TO_GUIDES.get(topic)


def get_all_glossary() -> dict:
    """Get the complete glossary."""
    return GLOSSARY


def get_all_scenarios() -> dict:
    """Get all scenario explanations."""
    return SCENARIO_EXPLANATIONS


def get_all_features() -> dict:
    """Get all product feature knowledge."""
    return PRODUCT_FEATURES


def get_all_situations() -> dict:
    """Get all common situations."""
    return COMMON_SITUATIONS


def get_all_how_tos() -> dict:
    """Get all how-to guides."""
    return HOW_TO_GUIDES


def search_glossary(query: str) -> list[dict]:
    """Search glossary for terms matching the query."""
    query_lower = query.lower()
    results = []
    for key, term in GLOSSARY.items():
        if (query_lower in key.lower() or
            query_lower in term["term"].lower() or
            query_lower in term["definition"].lower()):
            results.append(term)
    return results
