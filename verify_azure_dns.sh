#!/bin/bash

echo "=========================================="
echo "Azure Communication Services DNS Check"
echo "emailthewell.com"
echo "=========================================="
echo ""

echo "1. Checking SPF Record..."
SPF=$(dig emailthewell.com TXT +short | grep spf1)
if echo "$SPF" | grep -q "azure-communication-services.net"; then
    echo "✅ SPF includes Azure Communication Services"
    echo "   $SPF"
else
    echo "❌ Azure Communication Services NOT found in SPF"
    echo "   Current: $SPF"
fi
echo ""

echo "2. Checking Azure DKIM Selector 1..."
DKIM1=$(dig selector1-azurecomm-prod-net._domainkey.emailthewell.com CNAME +short)
if [ -n "$DKIM1" ]; then
    echo "✅ DKIM Selector 1 configured: $DKIM1"
else
    echo "❌ DKIM Selector 1 not found"
fi
echo ""

echo "3. Checking Azure DKIM Selector 2..."
DKIM2=$(dig selector2-azurecomm-prod-net._domainkey.emailthewell.com CNAME +short)
if [ -n "$DKIM2" ]; then
    echo "✅ DKIM Selector 2 configured: $DKIM2"
else
    echo "❌ DKIM Selector 2 not found"
fi
echo ""

echo "4. Checking DMARC Policy (should be unchanged)..."
DMARC=$(dig _dmarc.emailthewell.com TXT +short)
if echo "$DMARC" | grep -q "p=none"; then
    echo "✅ DMARC policy correct: monitoring mode (p=none)"
else
    echo "⚠️  DMARC policy unexpected"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
if echo "$SPF" | grep -q "azure-communication-services.net" && [ -n "$DKIM1" ] && [ -n "$DKIM2" ]; then
    echo "✅ All Azure Communication Services DNS records configured!"
    echo ""
    echo "DNS Lookup Count Check:"
    LOOKUP_COUNT=$(echo "$SPF" | grep -o "include:" | wc -l)
    echo "   Total SPF lookups: $LOOKUP_COUNT/10 (RFC limit)"
    if [ "$LOOKUP_COUNT" -le 5 ]; then
        echo "   ✅ Well within safe limits"
    elif [ "$LOOKUP_COUNT" -le 8 ]; then
        echo "   ⚠️  Getting close to limit"
    else
        echo "   ❌ Approaching RFC limit!"
    fi
    echo ""
    echo "Next steps:"
    echo "1. Configure Azure Communication Services custom domain"
    echo "2. Test email sending from Azure"
    echo "3. Monitor DMARC reports for Azure emails"
else
    echo "⏳ Some records not yet propagated. Wait 5-10 minutes and try again."
    echo ""
    echo "Missing records:"
    if ! echo "$SPF" | grep -q "azure-communication-services.net"; then
        echo "  ❌ SPF record (Azure Communication Services not included)"
    fi
    if [ -z "$DKIM1" ]; then
        echo "  ❌ DKIM Selector 1"
    fi
    if [ -z "$DKIM2" ]; then
        echo "  ❌ DKIM Selector 2"
    fi
fi
echo "=========================================="
