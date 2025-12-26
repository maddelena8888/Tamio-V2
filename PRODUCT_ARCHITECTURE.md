# Tamio Product Architecture

## Overview
Tamio is a cash flow forecasting platform designed for SMEs, combining manual data entry simplicity with powerful AI-driven insights and scenario planning capabilities.

## Technology Stack

### Frontend
- Single Page Application (HTML/JavaScript)
- Chart.js for data visualization
- Responsive design with mobile support

### Backend
- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with AsyncPG
- **ORM**: SQLAlchemy (Async)
- **Migrations**: Alembic
- **Authentication**: JWT tokens

### External Integrations
- **Xero API**: Accounting data synchronization
- **OpenAI GPT-4**: AI assistant (TAMI)

## Product Flow

```mermaid
---
config:
  layout: fixed
---
flowchart TB
 subgraph subGraph0["Data Ingestion"]
        ManualInput["Manual Data Entry"]
        DataSource{"Choose Data Source"}
        XeroSync["Xero OAuth Flow"]
        InputEmployees["Add Clients / Revenue"]
        InputExpenses["Add Expenses"]
        XeroAuth["Authorize Xero Access"]
        XeroFetch["Fetch Xero Data"]
        XeroMap["Auto-map to Tamio Structure"]
        DataGroup["Data Grouping & Organization"]
        ValidateData{"Data Complete?"}
        Dashboard["Dashboard View"]
  end
 subgraph subGraph1["Cash Flow Forecasting"]
        ForecastEngine["Forecast Engine"]
        CoreFeatures{"User Action"}
        CalcCashFlow["Calculate 13-Week<br>Cash Flow Projection"]
        ForecastChart["Display Forecast Chart<br>with Buffer Zones"]
  end
 subgraph subGraph2["Scenario Analysis"]
        ScenarioSelect["Select Scenario Type"]
        ScenarioTypes{"Scenario Type"}
        Hiring["Add Employee Scenario"]
        Firing["Remove Employee Scenario"]
        ClientGain["New Client Scenario"]
        ClientLoss["Lost Client Scenario"]
        PriceChange["Client Rate Change"]
        ExpenseChange["Recurring Expense Change"]
        PaymentDelay["Invoice/Payment Timing"]
        Contractor["Add/Remove Contractor"]
        PipelineEngine["Scenario Pipeline Engine"]
        RuleEngine["Apply Scenario Rules"]
        RecalcForecast["Recalculate Forecast<br>with Scenario"]
        CompareView["Side-by-Side Comparison<br>Current vs Scenario"]
        SaveScenario{"Save Scenario?"}
        StoreScenario["Store to Database"]
  end
 subgraph subGraph3["AI Assistant - TAMI"]
        TAMIChat["TAMI Chat Interface"]
        UserQuestion["User Inputs Question"]
        Agent1["Agent 1: Context Builder"]
        FetchContext["Fetch Relevant Data:<br>• Business financials<br>• Current forecast<br>• Active scenarios<br>• Cash flow status"]
        BuildPrompt["Build Enriched Prompt<br>with Context"]
        Agent2["Agent 2: AI Responder"]
        CallOpenAI["Call OpenAI GPT-4<br>with Context"]
        GenerateResponse["Generate Contextual<br>Financial Advice"]
        FormatResponse["Format Response<br>with Charts/Data"]
        DisplayChat["Display in Chat UI"]
        FollowUp{"Follow-up Question?"}
  end
    Start(["User Arrives"]) --> Signup["Account Creation"]
    Signup --> Login{"Has Account?"}
    Login -- New User --> Register["Register with Email/Password"]
    Login -- Existing User --> Auth["Login with JWT"]
    Register --> Onboard["Onboarding Wizard"]
    Auth --> Dashboard
    Onboard --> DataSource
    DataSource -- Manual Entry --> ManualInput
    DataSource -- Xero Connected --> XeroSync
    ManualInput --> InputEmployees & InputExpenses
    XeroSync --> XeroAuth
    XeroAuth --> XeroFetch
    XeroFetch --> XeroMap
    InputEmployees --> DataGroup
    InputExpenses --> DataGroup
    XeroMap --> DataGroup
    DataGroup --> ValidateData
    ValidateData -- No --> DataSource
    ValidateData -- Yes --> Dashboard
    Dashboard --> CoreFeatures
    CoreFeatures -- View Forecast --> ForecastEngine
    ForecastEngine --> CalcCashFlow
    CalcCashFlow --> ForecastChart
    ForecastChart --> Dashboard
    CoreFeatures -- Run Scenario --> ScenarioSelect
    ScenarioSelect --> ScenarioTypes
    ScenarioTypes -- Hiring --> Hiring
    ScenarioTypes -- Firing --> Firing
    ScenarioTypes -- Client Gain --> ClientGain
    ScenarioTypes -- Client Loss --> ClientLoss
    ScenarioTypes -- Price Change --> PriceChange
    ScenarioTypes -- Expense Change --> ExpenseChange
    ScenarioTypes -- Payment Delay --> PaymentDelay
    ScenarioTypes -- Contractor --> Contractor
    Hiring --> PipelineEngine
    Firing --> PipelineEngine
    ClientGain --> PipelineEngine
    ClientLoss --> PipelineEngine
    PriceChange --> PipelineEngine
    ExpenseChange --> PipelineEngine
    PaymentDelay --> PipelineEngine
    Contractor --> PipelineEngine
    PipelineEngine --> RuleEngine
    RuleEngine --> RecalcForecast
    RecalcForecast --> CompareView
    CompareView --> SaveScenario
    SaveScenario -- Yes --> StoreScenario
    SaveScenario -- No --> Dashboard
    StoreScenario --> Dashboard
    CoreFeatures -- Ask TAMI --> TAMIChat
    TAMIChat --> UserQuestion
    UserQuestion --> Agent1
    Agent1 --> FetchContext
    FetchContext --> BuildPrompt
    BuildPrompt --> Agent2
    Agent2 --> CallOpenAI
    CallOpenAI --> GenerateResponse
    GenerateResponse --> FormatResponse
    FormatResponse --> DisplayChat
    DisplayChat --> FollowUp
    FollowUp -- Yes --> UserQuestion
    FollowUp -- No --> Dashboard
    CoreFeatures -- Manage Data --> ManageData["Edit/Update Data"]
    ManageData --> DataSource
    CoreFeatures -- Sync Xero --> XeroResync["Re-sync Xero Data"]
    XeroResync --> XeroFetch
    CoreFeatures -- Logout --> End(["Session End"])

    style DataGroup fill:#e3f2fd
    style Dashboard fill:#2196f3,color:#fff
    style ForecastChart fill:#ff9800,color:#fff
    style PipelineEngine fill:#fff3e0
    style CompareView fill:#ff9800,color:#fff
    style Agent1 fill:#f3e5f5
    style Agent2 fill:#f3e5f5
    style DisplayChat fill:#9c27b0,color:#fff
    style Start fill:#4caf50,color:#fff
    style End fill:#f44336,color:#fff
```

## Core Features

### 1. Account Creation & Authentication
- JWT-based authentication
- Secure password hashing (bcrypt)
- Email/password registration
- Persistent sessions

### 2. Data Ingestion
Two primary data entry methods:

#### Manual Entry
- Clients and Revenue streams
- Employees and Payroll
- Recurring Expenses
- Custom billing cycles

#### Xero Integration
- OAuth 2.0 authentication flow
- Automatic data sync
- Smart mapping to Tamio data structure
- Bank account integration
- Invoice and contact synchronization

### 3. Cash Flow Forecasting
- **Time Horizon**: 13-week rolling forecast
- **Methodology**: Event-based projection engine
- **Visualization**: Interactive charts with buffer zones
- **Insights**: Cash runway, low-balance warnings, trend analysis

### 4. Scenario Analysis
12 scenario types supported:
- **People**: Hiring, Firing, Contractor changes
- **Revenue**: Client gain/loss, Rate changes
- **Expenses**: Increased/decreased recurring costs
- **Timing**: Payment delays (inbound/outbound)

**Pipeline Architecture**:
- Dynamic handler system
- Rule-based modifications
- Side-by-side comparisons
- Persistent scenario storage

### 5. TAMI AI Assistant
Two-agent architecture:

#### Agent 1: Context Builder
- Fetches relevant business data
- Analyzes current financial state
- Gathers forecast and scenario information
- Builds enriched prompt with context

#### Agent 2: AI Responder
- OpenAI GPT-4 integration
- Context-aware financial advice
- Natural language responses
- Multi-turn conversation support

## API Endpoints

### Authentication (`/api/v1/auth`)
- POST `/register` - User registration
- POST `/login` - User authentication
- POST `/refresh` - Token refresh

### Data Management (`/api/v1/data`)
- Clients, Employees, Contractors CRUD
- Invoices and Expenses management
- Recurring obligations tracking

### Forecasting (`/api/v1/forecast`)
- GET `/` - Generate forecast
- GET `/summary` - Forecast summary statistics

### Scenarios (`/api/v1/scenarios`)
- GET `/` - List scenarios
- POST `/` - Create scenario
- POST `/pipeline/run` - Execute scenario pipeline
- GET `/{id}/forecast` - Get scenario forecast

### TAMI (`/api/v1/tami`)
- POST `/chat` - Send message to TAMI
- GET `/context` - Get business context

### Xero (`/api/v1/xero`)
- GET `/auth/url` - Get OAuth URL
- POST `/auth/callback` - OAuth callback
- POST `/sync` - Trigger data sync
- GET `/status` - Sync status

## Database Schema

### Core Models
- **User**: Authentication and profile
- **Client**: Revenue sources
- **Employee**: Payroll obligations
- **Contractor**: Variable labor costs
- **Invoice**: Receivables
- **Expense**: Recurring costs
- **Scenario**: What-if analyses
- **XeroConnection**: Integration state

### Relationships
- Users → Multiple clients, employees, scenarios
- Clients → Multiple invoices
- Scenarios → Cloned forecast data

## Security Considerations
- JWT token authentication
- CORS configuration for allowed origins
- Password hashing with bcrypt
- OAuth 2.0 for Xero integration
- Environment-based configuration
- Database connection pooling with pre-ping

## Deployment
- FastAPI ASGI server (Uvicorn)
- PostgreSQL database
- Environment variables for configuration
- Database migrations via Alembic
- Static frontend deployment

## Future Enhancements
- Multi-currency support
- Team collaboration features
- Advanced reporting
- Mobile app
- Additional accounting integrations (QuickBooks, Sage)
- ML-based forecast improvements