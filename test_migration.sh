#!/bin/bash

# ============================================
# Azure Infrastructure Migration Test Script
# ============================================
# Quick curl-based tests for migrated resources
# Usage: ./test_migration.sh [api-key]

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${CONTAINER_APP_URL:-https://well-intake-api.salmonsmoke-78b2d936.eastus.azurecontainerapps.io}"
API_KEY="${1:-${API_KEY}}"
TIMEOUT=30

# Header
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Azure Infrastructure Migration Tests${NC}"
echo -e "${BLUE}============================================${NC}"
echo "Base URL: $BASE_URL"
echo "Timestamp: $(date)"
echo ""

# Function to test endpoint
test_endpoint() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    
    echo -e "${YELLOW}Testing: $name${NC}"
    echo "  Method: $method"
    echo "  Endpoint: $endpoint"
    
    # Build curl command
    local curl_cmd="curl -s -o /dev/null -w '%{http_code}' -X $method"
    
    if [ ! -z "$API_KEY" ]; then
        curl_cmd="$curl_cmd -H 'X-API-Key: $API_KEY'"
    fi
    
    if [ ! -z "$data" ]; then
        curl_cmd="$curl_cmd -H 'Content-Type: application/json' -d '$data'"
    fi
    
    curl_cmd="$curl_cmd --connect-timeout $TIMEOUT '$BASE_URL$endpoint'"
    
    # Execute curl
    local status=$(eval $curl_cmd)
    
    if [ "$status" = "$expected_status" ]; then
        echo -e "  ${GREEN}✓ PASSED${NC} (Status: $status)"
    else
        echo -e "  ${RED}✗ FAILED${NC} (Expected: $expected_status, Got: $status)"
    fi
    echo ""
}

# Function to test with response body
test_with_response() {
    local name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    
    echo -e "${YELLOW}Testing: $name${NC}"
    echo "  Method: $method"
    echo "  Endpoint: $endpoint"
    
    # Build curl command
    local curl_cmd="curl -s -X $method"
    
    if [ ! -z "$API_KEY" ]; then
        curl_cmd="$curl_cmd -H 'X-API-Key: $API_KEY'"
    fi
    
    if [ ! -z "$data" ]; then
        curl_cmd="$curl_cmd -H 'Content-Type: application/json' -d '$data'"
    fi
    
    curl_cmd="$curl_cmd --connect-timeout $TIMEOUT '$BASE_URL$endpoint'"
    
    # Execute curl and get response
    local response=$(eval $curl_cmd)
    local exit_code=$?
    
    if [ $exit_code -eq 0 ] && [ ! -z "$response" ]; then
        echo -e "  ${GREEN}✓ PASSED${NC}"
        echo "  Response: $(echo $response | python3 -m json.tool 2>/dev/null || echo $response | head -c 200)..."
    else
        echo -e "  ${RED}✗ FAILED${NC} (Exit code: $exit_code)"
    fi
    echo ""
}

# ============================================
# 1. Container App Health Tests
# ============================================
echo -e "${BLUE}=== Container App Tests ===${NC}"
echo ""

test_with_response "Health Check" "GET" "/health" ""

test_endpoint "API Root" "GET" "/" "" "200"

test_endpoint "Manifest Endpoint" "GET" "/manifest.xml" "" "200"

# ============================================
# 2. Authentication Tests
# ============================================
echo -e "${BLUE}=== Authentication Tests ===${NC}"
echo ""

# Test without API key
echo -e "${YELLOW}Testing: Unauthenticated Request${NC}"
status=$(curl -s -o /dev/null -w '%{http_code}' -X GET "$BASE_URL/test/kevin-sullivan")
if [ "$status" = "401" ] || [ "$status" = "403" ]; then
    echo -e "  ${GREEN}✓ PASSED${NC} (Correctly rejected: $status)"
else
    echo -e "  ${RED}✗ FAILED${NC} (Expected 401/403, Got: $status)"
fi
echo ""

if [ ! -z "$API_KEY" ]; then
    test_with_response "Authenticated Test Endpoint" "GET" "/test/kevin-sullivan" ""
else
    echo -e "${YELLOW}⚠ Skipping authenticated tests (no API key provided)${NC}"
    echo ""
fi

# ============================================
# 3. Email Processing Tests
# ============================================
echo -e "${BLUE}=== Email Processing Tests ===${NC}"
echo ""

if [ ! -z "$API_KEY" ]; then
    # Test email intake
    test_data='{
        "subject": "Migration Test - Senior Developer Position",
        "from": "test@example.com",
        "body": "This is a test email for the migrated infrastructure. Candidate: John Doe, Position: Senior Developer, Location: New York",
        "received": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'"
    }'
    
    test_with_response "Email Intake" "POST" "/intake/email" "$test_data"
    
    # Test batch processing
    batch_data='{
        "emails": [
            {
                "subject": "Batch Test 1",
                "from": "test1@example.com",
                "body": "First batch test email"
            },
            {
                "subject": "Batch Test 2",
                "from": "test2@example.com",
                "body": "Second batch test email"
            }
        ]
    }'
    
    test_with_response "Batch Processing" "POST" "/batch/submit" "$batch_data"
fi

# ============================================
# 4. Cache Status Test
# ============================================
echo -e "${BLUE}=== Cache Tests ===${NC}"
echo ""

if [ ! -z "$API_KEY" ]; then
    test_with_response "Cache Status" "GET" "/cache/status" ""
fi

# ============================================
# 5. WebSocket/Streaming Test
# ============================================
echo -e "${BLUE}=== WebSocket Tests ===${NC}"
echo ""

if [ ! -z "$API_KEY" ]; then
    echo -e "${YELLOW}Testing: WebSocket Endpoint Discovery${NC}"
    ws_response=$(curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/stream/connect")
    if [ ! -z "$ws_response" ]; then
        echo -e "  ${GREEN}✓ WebSocket endpoint available${NC}"
        echo "  Response: $(echo $ws_response | head -c 100)..."
    else
        echo -e "  ${YELLOW}⚠ WebSocket endpoint not configured${NC}"
    fi
    echo ""
fi

# ============================================
# 6. Performance Test
# ============================================
echo -e "${BLUE}=== Performance Tests ===${NC}"
echo ""

echo -e "${YELLOW}Testing: Response Time${NC}"
start_time=$(date +%s%N)
curl -s -o /dev/null "$BASE_URL/health"
end_time=$(date +%s%N)
elapsed_ms=$(((end_time - start_time) / 1000000))

if [ $elapsed_ms -lt 1000 ]; then
    echo -e "  ${GREEN}✓ PASSED${NC} (Response time: ${elapsed_ms}ms)"
elif [ $elapsed_ms -lt 3000 ]; then
    echo -e "  ${YELLOW}⚠ WARNING${NC} (Response time: ${elapsed_ms}ms - slower than expected)"
else
    echo -e "  ${RED}✗ FAILED${NC} (Response time: ${elapsed_ms}ms - too slow)"
fi
echo ""

# ============================================
# 7. Azure Service Integration Tests
# ============================================
echo -e "${BLUE}=== Azure Service Integration Tests ===${NC}"
echo ""

if [ ! -z "$API_KEY" ]; then
    # Test service health endpoints if available
    services=("postgresql" "redis" "storage" "servicebus" "signalr" "aisearch" "appinsights")
    
    for service in "${services[@]}"; do
        echo -e "${YELLOW}Checking: $service integration${NC}"
        
        # Try health endpoint for specific service
        status=$(curl -s -o /dev/null -w '%{http_code}' -H "X-API-Key: $API_KEY" \
                 --connect-timeout 5 "$BASE_URL/health/$service" 2>/dev/null)
        
        if [ "$status" = "200" ]; then
            echo -e "  ${GREEN}✓ $service is healthy${NC}"
        elif [ "$status" = "404" ]; then
            echo -e "  ${YELLOW}⚠ $service health endpoint not implemented${NC}"
        else
            echo -e "  ${RED}✗ $service may have issues (Status: $status)${NC}"
        fi
    done
    echo ""
fi

# ============================================
# Summary
# ============================================
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}============================================${NC}"
echo "Tests completed at: $(date)"
echo ""
echo -e "${GREEN}Note: For comprehensive testing, run:${NC}"
echo "  python tests/test_migrated_infrastructure.py"
echo ""
echo -e "${YELLOW}To test with API key:${NC}"
echo "  ./test_migration.sh YOUR_API_KEY"
echo ""
echo -e "${YELLOW}To set API key in environment:${NC}"
echo "  export API_KEY=your-api-key"
echo "  ./test_migration.sh"
echo ""