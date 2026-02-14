#!/bin/bash
# Test a TAMI operational tool via the chat endpoint.
# Usage: ./scripts/test_tool.sh <tool_name>
#
# Requires: backend running on localhost:8000, AgencyCo seeded.

set -euo pipefail

TOOL_NAME="${1:-}"
BASE_URL="http://localhost:8000/api/tami/chat"
BACKEND_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -z "$TOOL_NAME" ]; then
    echo "Usage: ./scripts/test_tool.sh <tool_name>"
    echo ""
    echo "Available tools:"
    echo "  check_payroll_safety        \"Can I make payroll this month?\""
    echo "  draft_collection_message    \"Draft a follow-up for the overdue RetailCo invoice\""
    echo "  analyze_concentration_risk  \"What's my client concentration risk?\""
    echo "  generate_briefing           \"What should I know today?\""
    exit 1
fi

# Discover demo user ID from the database (suppress SQLAlchemy logging)
USER_ID=$("$BACKEND_DIR/venv/bin/python" -c "
import asyncio, sys, os, logging
logging.disable(logging.CRITICAL)
sys.path.insert(0, '$BACKEND_DIR')
os.chdir('$BACKEND_DIR')
from sqlalchemy import text
from app.database import engine
async def main():
    async with engine.connect() as conn:
        r = await conn.execute(text(\"SELECT id FROM users WHERE email = 'demo@agencyco.com'\"))
        row = r.fetchone()
        print(row[0] if row else '')
    await engine.dispose()
asyncio.run(main())
")

if [ -z "$USER_ID" ]; then
    echo "Error: Could not find demo user. Run seed first: POST /api/seed/agencyco"
    exit 1
fi

echo "Demo user: $USER_ID"
echo "Tool:      $TOOL_NAME"
echo "---"

# Map tool name to a natural-language test message
case "$TOOL_NAME" in
    check_payroll_safety)
        MESSAGE="Can I make payroll this month?" ;;
    draft_collection_message)
        MESSAGE="Draft a follow-up email for the overdue RetailCo invoice" ;;
    analyze_concentration_risk)
        MESSAGE="What's my client concentration risk?" ;;
    generate_briefing)
        MESSAGE="What should I know today?" ;;
    *)
        echo "Unknown tool: $TOOL_NAME"
        echo "Run without arguments to see available tools."
        exit 1 ;;
esac

echo "Message:   \"$MESSAGE\""
echo "---"

# Hit the chat endpoint
RESPONSE=$(curl -s -w "\n%{http_code}" "$BASE_URL" \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$USER_ID\", \"message\": \"$MESSAGE\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" != "200" ]; then
    echo "HTTP $HTTP_CODE"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    exit 1
fi

# Extract and display key fields
echo ""
echo "=== TAMI Response ==="
echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
resp = data.get('response', {})
print(resp.get('message_markdown', '(no response)'))
print()
print(f\"Mode: {resp.get('mode', 'unknown')}\")
tools = data.get('tool_calls_made', [])
if tools:
    print(f'Tools called: {len(tools)}')
    for t in tools:
        print(f'  - {t.get(\"name\", \"unknown\")}')
"
