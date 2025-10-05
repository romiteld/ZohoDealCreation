#!/bin/bash
# Test Calendly email processing with curl

# Set your API key here or export it as an environment variable
API_KEY="${API_KEY:-your-api-key-here}"
API_URL="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"

# Calendly email payload
read -r -d '' PAYLOAD << 'EOF'
{
  "sender_email": "notifications@calendly.com",
  "sender_name": "Calendly",
  "subject": "New Event: Tim Koski - Recruiting Consult",
  "body": "A new event has been scheduled.\n\nEvent Type:\nRecruiting Consult\n\nInvitee:\nTim Koski\ntim.koski@everpar.com\n\nInvitee Phone Number:\n+1 918-237-1276\n\nEvent Date/Time:\n11:00am - 11:30am (America/Chicago) on Wednesday, September 24, 2025\n\nLocation:\nThis is a phone call. The Well will call the invitee at the phone number provided.\n\nInvitee Time Zone:\nAmerica/Chicago\n\nQuestions:\n\nPlease share more about the opportunity you have available:\nLooking to hire 2 lead advisors in the Tulsa market ASAP. Planning to add a third CSA in 2026, two associate advisors in 2027, and another lead advisor in 2028.\n\nView event in Calendly: https://calendly.com/scheduled_events/evt_abc123\n\nNeed to make changes to this event?\nCancel: https://calendly.com/cancellations/evt_abc123\nReschedule: https://calendly.com/reschedulings/evt_abc123\n\nPowered by Calendly.com",
  "attachments": [],
  "reply_to": "tim.koski@everpar.com",
  "internet_message_id": "evt_abc123@calendly.com"
}
EOF

# Test with dry run first (preview only)
echo "🧪 Testing Calendly email extraction (dry run)..."
echo "================================================"

# Create dry run payload
DRY_RUN_PAYLOAD=$(echo "$PAYLOAD" | jq '. + {dry_run: true}')

curl -X POST "${API_URL}/intake/email" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d "${DRY_RUN_PAYLOAD}" | python -m json.tool

echo -e "\n\n"

# To actually create records, uncomment the following:
# echo "📝 Creating Zoho records from Calendly email..."
# echo "================================================"
# 
# curl -X POST "${API_URL}/intake/email" \
#   -H "X-API-Key: ${API_KEY}" \
#   -H "Content-Type: application/json" \
#   -d "${PAYLOAD}" | python -m json.tool