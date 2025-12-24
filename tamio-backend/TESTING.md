# Tamio Backend - Testing Guide

Quick guide to test the Tamio backend manually.

## Prerequisites

- Backend running at http://localhost:8000
- Database configured and migrated

## Test Scenario: Manual Input Flow

This tests the complete manual input → forecast workflow.

### Step 1: Create a User

```bash
curl -X POST http://localhost:8000/api/auth/manual/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "founder@startup.com"}' | jq
```

**Expected Response:**
```json
{
  "id": "user_abc123",
  "email": "founder@startup.com",
  "xero_tenant_id": null,
  "created_at": "2025-01-15T10:30:00Z"
}
```

**Save the `user_id` for next steps!**

### Step 2: Add Starting Cash

```bash
USER_ID="user_abc123"  # Replace with your user_id

curl -X POST "http://localhost:8000/api/events/bank-accounts?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "account_name": "Operating Account",
    "balance": 450000.00,
    "currency": "USD",
    "as_of_date": "2025-01-15"
  }' | jq
```

**Expected Response:**
```json
{
  "id": "acct_xyz789",
  "user_id": "user_abc123",
  "account_name": "Operating Account",
  "current_balance": "450000.00",
  "currency": "USD",
  "as_of_date": "2025-01-15",
  "source": "manual_input",
  "source_id": null,
  "updated_at": "2025-01-15T10:35:00Z"
}
```

### Step 3: Add Revenue Events

**High confidence project milestone:**
```bash
curl -X POST "http://localhost:8000/api/events/revenue?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Client A",
    "amount": 120000.00,
    "date": "2025-02-03",
    "revenue_type": "project",
    "confidence": "high",
    "is_recurring": false
  }' | jq
```

**Recurring retainer:**
```bash
curl -X POST "http://localhost:8000/api/events/revenue?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Client B - Retainer",
    "amount": 25000.00,
    "date": "2025-02-01",
    "revenue_type": "retainer",
    "confidence": "high",
    "is_recurring": true,
    "recurrence_pattern": "monthly"
  }' | jq
```

### Step 4: Add Obligations (Expenses)

**Fixed obligation (Payroll):**
```bash
curl -X POST "http://localhost:8000/api/events/obligation?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Payroll",
    "amount": 45000.00,
    "date": "2025-02-01",
    "category": "payroll",
    "obligation_type": "fixed",
    "is_recurring": true,
    "recurrence_pattern": "bi-weekly"
  }' | jq
```

**Variable obligation (Contractors):**
```bash
curl -X POST "http://localhost:8000/api/events/obligation?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Contractors",
    "amount": 15000.00,
    "date": "2025-02-15",
    "category": "contractor",
    "obligation_type": "variable",
    "is_recurring": true,
    "recurrence_pattern": "monthly"
  }' | jq
```

**Discretionary obligation (Software subscriptions):**
```bash
curl -X POST "http://localhost:8000/api/events/obligation?user_id=$USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_name": "Software Subscriptions",
    "amount": 3000.00,
    "date": "2025-02-05",
    "category": "subscription",
    "obligation_type": "discretionary",
    "is_recurring": true,
    "recurrence_pattern": "monthly"
  }' | jq
```

### Step 5: View All Events

```bash
curl "http://localhost:8000/api/events?user_id=$USER_ID" | jq
```

You should see all events (including recurring instances generated automatically).

### Step 6: Get 13-Week Forecast

```bash
curl "http://localhost:8000/api/forecast?user_id=$USER_ID" | jq
```

**Expected Response Structure:**
```json
{
  "starting_cash": "450000.00",
  "forecast_start_date": "2025-01-15",
  "weeks": [
    {
      "week_number": 1,
      "week_start": "2025-01-15",
      "week_end": "2025-01-22",
      "starting_balance": "450000.00",
      "cash_in": "0.00",
      "cash_out": "0.00",
      "net_change": "0.00",
      "ending_balance": "450000.00",
      "events": []
    },
    {
      "week_number": 2,
      "week_start": "2025-01-22",
      "week_end": "2025-01-29",
      "starting_balance": "450000.00",
      "cash_in": "25000.00",
      "cash_out": "48000.00",
      "net_change": "-23000.00",
      "ending_balance": "427000.00",
      "events": [...]
    },
    ...
  ],
  "summary": {
    "lowest_cash_week": 8,
    "lowest_cash_amount": "350000.00",
    "total_cash_in": "320000.00",
    "total_cash_out": "420000.00",
    "runway_weeks": 13
  }
}
```

### Step 7: Verify Forecast Logic

Check that:
- ✅ Starting cash = $450,000
- ✅ Week 2 shows retainer ($25k in) and payroll ($45k out)
- ✅ Week 3 shows project milestone ($120k in)
- ✅ Recurring events appear every month/bi-weekly as configured
- ✅ Running balance updates correctly each week
- ✅ Summary shows lowest cash week and runway

## Test Scenario: Using Dev Utils

Much faster way to create realistic test data:

```bash
# Create comprehensive test data
python dev_utils.py create_test_data founder@startup.com

# Output will show user_id, copy it
# Example: user_abc123

# Get formatted forecast
python dev_utils.py get_forecast user_abc123
```

This creates:
- 1 user
- 1 bank account ($450k)
- 3 clients (retainer, project, usage)
- ~30 cash events (revenue + obligations)

## Test Scenario: Xero Integration

**Note:** Requires Xero Developer account and credentials in `.env`

### Step 1: Get Authorization URL

```bash
curl http://localhost:8000/api/auth/xero/login | jq
```

**Expected Response:**
```json
{
  "auth_url": "https://login.xero.com/identity/connect/authorize?..."
}
```

### Step 2: Authorize in Browser

1. Copy the `auth_url` and open in browser
2. Log in to Xero
3. Select organization
4. Click "Authorize"
5. You'll be redirected to: `http://localhost:8000/api/auth/xero/callback?code=...`

**Expected Response:**
```json
{
  "success": true,
  "user_id": "user_xyz123",
  "message": "Successfully connected to Your Company Name"
}
```

### Step 3: Trigger Xero Sync

```bash
USER_ID="user_xyz123"  # From callback response

curl -X POST "http://localhost:8000/api/sync/xero?user_id=$USER_ID" | jq
```

**Expected Response:**
```json
{
  "status": "completed",
  "user_id": "user_xyz123",
  "results": {
    "bank_accounts_synced": 2,
    "invoices_synced": 12,
    "bills_synced": 8,
    "transactions_synced": 156,
    "clients_created": 5
  }
}
```

### Step 4: View Synced Data

```bash
# View all events
curl "http://localhost:8000/api/events?user_id=$USER_ID" | jq

# Get forecast
curl "http://localhost:8000/api/forecast?user_id=$USER_ID" | jq
```

## Testing Checklist

### Manual Input
- [ ] User creation works
- [ ] Bank account creation works
- [ ] Revenue event creation works
- [ ] Obligation event creation works
- [ ] Recurring events generate correctly
- [ ] Events appear in list
- [ ] Forecast calculates correctly

### Xero Integration
- [ ] OAuth URL generation works
- [ ] Callback handles authorization
- [ ] Token is stored encrypted
- [ ] Sync fetches bank accounts
- [ ] Sync fetches invoices → revenue events
- [ ] Sync fetches bills → obligation events
- [ ] Sync fetches historical transactions
- [ ] Clients are created from contacts
- [ ] Forecast includes Xero data

### Forecast Engine
- [ ] Starting cash calculated from bank accounts
- [ ] Events grouped into correct weeks
- [ ] Cash in calculated correctly
- [ ] Cash out calculated correctly
- [ ] Running balance updates correctly
- [ ] Lowest cash week identified
- [ ] Runway calculated correctly
- [ ] Events limited to top 10 per week

### Error Handling
- [ ] Missing user_id returns 400
- [ ] Invalid date format returns 422
- [ ] Xero sync without token returns 400
- [ ] Database errors return 500

## Common Issues

### "User not found"
- Verify `user_id` is correct
- Check database: `SELECT * FROM users;`

### "No events in forecast"
- Check events exist: `SELECT * FROM cash_events WHERE user_id = 'xxx';`
- Verify dates are in future
- Check week_number calculation

### Xero sync fails
- Verify credentials in `.env`
- Check token is stored: `SELECT xero_tenant_id FROM users WHERE id = 'xxx';`
- Try refreshing token

### Recurring events not generated
- Check `is_recurring` is true
- Verify `recurrence_pattern` is valid
- Check events table for future instances

## Database Inspection

```bash
# Connect to database
psql -d tamio_db

# View users
SELECT id, email, xero_tenant_id FROM users;

# View events
SELECT id, date, amount, direction, event_type, client_name
FROM cash_events
WHERE user_id = 'user_abc123'
ORDER BY date;

# View forecast data
SELECT week_number, date, amount, direction
FROM cash_events
WHERE user_id = 'user_abc123'
AND date >= CURRENT_DATE
ORDER BY week_number, date;
```

## Clean Up Test Data

```bash
# Using dev utils (safe, prompts for confirmation)
python dev_utils.py clear_all

# Or via database (dangerous!)
psql -d tamio_db -c "DELETE FROM cash_events; DELETE FROM clients; DELETE FROM bank_accounts; DELETE FROM users;"
```

## API Documentation

Interactive API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Use these to test endpoints interactively.
