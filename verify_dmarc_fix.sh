#!/bin/bash

echo "=========================================="
echo "DMARC Record Verification Tool"
echo "emailthewell.com"
echo "=========================================="
echo ""
echo "Checking current DMARC policy..."
echo ""

DMARC_RECORD=$(dig _dmarc.emailthewell.com TXT +short 2>/dev/null)

echo "Current record:"
echo "$DMARC_RECORD"
echo ""
echo "=========================================="
echo "Status Check:"
echo "=========================================="

if echo "$DMARC_RECORD" | grep -q "p=none"; then
    echo "✅ SUCCESS! DMARC policy is set to p=none"
    echo "✅ Emails should now deliver to inbox"
    echo ""
    echo "Additional checks:"
    if echo "$DMARC_RECORD" | grep -q "sp=none"; then
        echo "  ✅ Subdomain policy: sp=none (correct)"
    else
        echo "  ⚠️  Subdomain policy: NOT FOUND"
    fi

    if echo "$DMARC_RECORD" | grep -q "pct=100"; then
        echo "  ✅ Percentage: pct=100 (correct)"
    else
        echo "  ⚠️  Percentage: NOT FOUND"
    fi

    if echo "$DMARC_RECORD" | grep -q "fo=1"; then
        echo "  ✅ Forensic options: fo=1 (correct)"
    else
        echo "  ⚠️  Forensic options: NOT FOUND"
    fi
    echo ""
    echo "=========================================="
    echo "🎉 FIX COMPLETE!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "1. Monitor email deliverability over next 24-48 hours"
    echo "2. Check for customer feedback about email delivery"
    echo "3. Review DMARC reports in carlos.martinez@emailthewell.com"
    echo ""

elif echo "$DMARC_RECORD" | grep -q "p=quarantine"; then
    echo "⏳ STILL PROPAGATING..."
    echo "❌ Current policy: p=quarantine (old policy still active)"
    echo ""
    echo "This is normal! DNS changes take time."
    echo ""
    echo "What to do:"
    echo "1. Wait 5-10 more minutes"
    echo "2. Run this script again: ./verify_dmarc_fix.sh"
    echo "3. If still showing old policy after 30 minutes, contact IT"
    echo ""

elif echo "$DMARC_RECORD" | grep -q "p=reject"; then
    echo "⚠️  WARNING: Policy is set to p=reject"
    echo "This is even stricter than quarantine!"
    echo "Contact IT immediately if this is unexpected."
    echo ""

else
    echo "❓ UNKNOWN STATUS"
    echo "Could not determine DMARC policy"
    echo ""
    echo "Possible reasons:"
    echo "1. DNS record not found"
    echo "2. Formatting issue"
    echo "3. DNS propagation in progress"
    echo ""
    echo "Contact IT for assistance."
fi

echo "=========================================="
echo "DNS Server Response Time: $(date)"
echo "=========================================="
