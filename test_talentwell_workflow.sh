#!/bin/bash

# TalentWell Complete Workflow Test
# Tests all four new API endpoints with sample data

API_KEY="e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384"
BASE_URL="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"

echo "=== TalentWell Workflow Test ==="
echo "API Base URL: $BASE_URL"
echo

# Test 1: Seed Policies
echo "1. Testing Policy Seeding..."
curl -X POST "${BASE_URL}/api/talentwell/seed-policies" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  | python3 -m json.tool

echo -e "\n=== Policy Seeding Complete ===\n"

# Test 2: Import Sample CSV Data
echo "2. Testing CSV Import..."
cat << 'EOF' > /tmp/test_csv_data.json
{
  "deals": "Deal Id,Deal Name,Job Title,Account Name,Location,Deal Owner,Stage,Created Time,Closing Date,Source,Source Detail,Referrer Name,Description,Amount\n123456,John Smith - Financial Advisor,Financial Advisor,Morgan Stanley,Boston MA,Steve Perry,Initial Contact,2025-01-15 10:30:00,2025-03-01,Referral,LinkedIn,Sarah Johnson,Senior advisor with 10+ years experience,150000\n123457,Sarah Miller - Portfolio Manager,Portfolio Manager,Goldman Sachs,New York NY,Steve Perry,Qualification,2025-01-20 14:15:00,2025-02-28,Email Inbound,,Direct application,Portfolio management expert with CFA certification,180000",
  "stage_history": "Deal Id,Stage,Changed Time,Duration,Changed By\n123456,Initial Contact,2025-01-15 10:30:00,0,Steve Perry\n123457,Qualification,2025-01-20 14:15:00,2,Steve Perry",
  "meetings": "Deal Id,Title,Start DateTime,Participants,Email Opened,Link Clicked\n123456,Initial Interview,2025-01-22 15:00:00,Steve Perry; John Smith,Yes,Yes\n123457,Portfolio Review,2025-01-25 11:00:00,Steve Perry; Sarah Miller,Yes,No",
  "notes": "Deal Id,Note Content,Created Time,Created By\n123456,Great cultural fit for Boston office,2025-01-22 16:00:00,Steve Perry\n123457,Strong technical skills need salary negotiation,2025-01-25 12:00:00,Steve Perry"
}
EOF

curl -X POST "${BASE_URL}/api/talentwell/import-exports" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/test_csv_data.json \
  | python3 -m json.tool

echo -e "\n=== CSV Import Complete ===\n"

# Test 3: Validate Sample Digest Data
echo "3. Testing Digest Validation..."
cat << 'EOF' > /tmp/test_digest_data.json
{
  "subject": "TalentWell Weekly Digest - Week of Jan 22, 2025",
  "intro_block": "<p>Hi Steve,</p><p>Here are this week's top candidate matches based on your search criteria. Each candidate has been carefully vetted and matched to your specific requirements.</p>",
  "candidates": [
    {
      "name": "John Smith",
      "location": "Boston, MA (Open to relocation)",
      "hard_skills": [
        "10+ years portfolio management experience",
        "Series 7 & 66 licensed", 
        "CFA Level II candidate"
      ],
      "availability": "30 days notice",
      "compensation": "$150K-$180K base",
      "ref_code": "REF-2025-WK03-001"
    },
    {
      "name": "Sarah Miller",
      "location": "New York, NY (Remote preferred)",
      "hard_skills": [
        "8 years wealth management experience",
        "CFP certified",
        "Specializes in HNW clients ($5M+)"
      ],
      "availability": "Immediate",
      "compensation": "$125K-$145K base + bonus",
      "ref_code": "REF-2025-WK03-002"
    }
  ]
}
EOF

curl -X POST "${BASE_URL}/api/talentwell/validate" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/test_digest_data.json \
  > /tmp/validation_response.json

# Check if validation was successful
if grep -q '"valid": true' /tmp/validation_response.json; then
    echo "✅ Validation successful!"
    cat /tmp/validation_response.json | python3 -m json.tool | grep -E "(valid|candidate_count|html_size)"
else
    echo "❌ Validation failed:"
    cat /tmp/validation_response.json | python3 -m json.tool
fi

echo -e "\n=== Digest Validation Complete ===\n"

# Test 4: Test Send (if validation was successful)
if grep -q '"valid": true' /tmp/validation_response.json; then
    echo "4. Testing Email Send..."
    cat << 'EOF' > /tmp/test_send_data.json
{
  "digest_data": {
    "subject": "TalentWell Weekly Digest - Week of Jan 22, 2025",
    "intro_block": "<p>Hi Steve,</p><p>Here are this week's top candidate matches based on your search criteria. Each candidate has been carefully vetted and matched to your specific requirements.</p>",
    "candidates": [
      {
        "name": "John Smith",
        "location": "Boston, MA (Open to relocation)",
        "hard_skills": [
          "10+ years portfolio management experience",
          "Series 7 & 66 licensed", 
          "CFA Level II candidate"
        ],
        "availability": "30 days notice",
        "compensation": "$150K-$180K base",
        "ref_code": "REF-2025-WK03-001"
      },
      {
        "name": "Sarah Miller", 
        "location": "New York, NY (Remote preferred)",
        "hard_skills": [
          "8 years wealth management experience",
          "CFP certified",
          "Specializes in HNW clients ($5M+)"
        ],
        "availability": "Immediate", 
        "compensation": "$125K-$145K base + bonus",
        "ref_code": "REF-2025-WK03-002"
      }
    ]
  },
  "test_recipient": "daniel.romitelli@emailthewell.com"
}
EOF

    curl -X POST "${BASE_URL}/api/talentwell/test-send" \
      -H "X-API-Key: $API_KEY" \
      -H "Content-Type: application/json" \
      -d @/tmp/test_send_data.json \
      | python3 -m json.tool

    echo -e "\n=== Test Send Complete ===\n"
else
    echo "4. Skipping Test Send due to validation failure"
fi

# Test 5: Email System Status
echo "5. Checking Email System Status..."
curl -X GET "${BASE_URL}/api/talentwell/email-status" \
  -H "X-API-Key: $API_KEY" \
  | python3 -m json.tool

echo -e "\n=== Email Status Check Complete ===\n"

# Clean up temporary files
rm -f /tmp/test_csv_data.json /tmp/test_digest_data.json /tmp/test_send_data.json /tmp/validation_response.json

echo "=== TalentWell Workflow Test Complete ==="