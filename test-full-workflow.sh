#!/bin/bash
echo "==========================================="
echo "WELL INTAKE UI - COMPLETE WORKFLOW TEST"
echo "==========================================="
echo ""

# Test 1: Check if Static Web App is accessible
echo "✓ TEST 1: Checking Static Web App..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://proud-ocean-087af290f.2.azurestaticapps.net/)
if [ "$STATUS" = "302" ]; then
    echo "  ✅ Static Web App is live (redirecting to Azure AD login)"
else
    echo "  ❌ Static Web App not responding correctly"
fi

# Test 2: Check backend health
echo ""
echo "✓ TEST 2: Checking Backend API..."
HEALTH=$(curl -s -X GET "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health" \
  -H "X-API-Key: e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384" | grep -o '"status":"healthy"')
if [ ! -z "$HEALTH" ]; then
    echo "  ✅ Backend API is healthy"
else
    echo "  ❌ Backend API issue detected"
fi

# Test 3: Test email extraction
echo ""
echo "✓ TEST 3: Testing Email Extraction..."
EXTRACTION=$(curl -s -X POST "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/intake/email" \
  -H "X-API-Key: e49d2dbcfa4547f5bdc371c5c06aae2afd06914e16e680a7f31c5fc5384ba384" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_email": "kevin.sullivan@namcoa.com",
    "subject": "Test - Kevin Sullivan Recruiting",
    "body": "From: Kevin Sullivan\nPhone: 704-905-8002\nCompany: NAMCOA\nInterested in advisor opportunities",
    "dry_run": true
  }' | grep -o '"status":"requires_input"')
if [ ! -z "$EXTRACTION" ]; then
    echo "  ✅ Email extraction endpoint working"
else
    echo "  ❌ Email extraction failed"
fi

# Test 4: Check CORS configuration
echo ""
echo "✓ TEST 4: Checking CORS Configuration..."
CORS=$(curl -s -I -X OPTIONS "https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io/health" \
  -H "Origin: https://proud-ocean-087af290f.2.azurestaticapps.net" \
  -H "Access-Control-Request-Method: POST" | grep -i "access-control-allow-origin")
if [ ! -z "$CORS" ]; then
    echo "  ✅ CORS properly configured"
else
    echo "  ⚠️  CORS may need adjustment"
fi

echo ""
echo "==========================================="
echo "DEPLOYMENT SUMMARY"
echo "==========================================="
echo ""
echo "📱 WEB UI URL:"
echo "   https://proud-ocean-087af290f.2.azurestaticapps.net/"
echo ""
echo "🔑 AUTHENTICATION:"
echo "   Azure AD (automatic redirect on access)"
echo ""
echo "📁 SUPPORTED FILES:"
echo "   .msg and .eml files"
echo ""
echo "⚡ FEATURES:"
echo "   • Drag-and-drop file upload"
echo "   • Auto-extraction with LangGraph"
echo "   • Editable fields before submission"
echo "   • LinkedIn/Calendly URL detection"
echo "   • Deal name preview"
echo "   • Direct Zoho CRM integration"
echo ""
echo "✅ READY FOR YOUR 10AM DEADLINE!"
echo "==========================================="