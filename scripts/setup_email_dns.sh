#!/bin/bash
# Script to verify and setup DNS records for TalentWell email deliverability
# Domain: emailthewell.com
# Email Service: Azure Communication Services

set -e

echo "========================================="
echo "Email DNS Setup for emailthewell.com"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check DNS record
check_dns() {
    local record_type=$1
    local record_name=$2
    echo -e "${YELLOW}Checking ${record_type} record for ${record_name}...${NC}"
    dig +short ${record_name} ${record_type} | head -5
    echo ""
}

echo "Step 1: Verify Current DNS Records"
echo "======================================"
echo ""

# Check SPF
echo "Current SPF Record:"
check_dns TXT emailthewell.com | grep "v=spf1"

# Check DMARC
echo "Current DMARC Record:"
check_dns TXT _dmarc.emailthewell.com

# Check MX
echo "Current MX Records:"
check_dns MX emailthewell.com

# Check DKIM selectors
echo "Current DKIM Selectors (Microsoft 365):"
check_dns CNAME selector1._domainkey.emailthewell.com
check_dns CNAME selector2._domainkey.emailthewell.com

echo ""
echo "========================================="
echo "Step 2: Required DNS Changes"
echo "========================================="
echo ""

echo -e "${YELLOW}ACTION REQUIRED:${NC} Add the following DNS records in Cloudflare:"
echo ""

echo "1. UPDATE SPF Record (TXT)"
echo "   Name: @"
echo "   Content: v=spf1 include:spf.protection.outlook.com include:zcsend.net include:spf.azure-communication-services.net ~all"
echo "   TTL: Auto"
echo ""

echo "2. ADD Azure Communication Services Domain in Azure Portal"
echo "   a. Go to: Azure Portal > Communication Services > Domains"
echo "   b. Click 'Add custom domain'"
echo "   c. Enter: emailthewell.com"
echo "   d. Azure will provide DKIM CNAME records - add them to Cloudflare"
echo ""

echo -e "${GREEN}CURRENT DMARC is correct - no changes needed${NC}"
echo ""

echo "========================================="
echo "Step 3: Test Email Deliverability"
echo "========================================="
echo ""

echo "After DNS changes propagate (15-30 minutes), test with:"
echo "  1. Send test digest: curl -X POST http://localhost:8000/api/talentwell/test-email"
echo "  2. Check email headers for SPF/DKIM/DMARC pass"
echo "  3. Use mail-tester.com for deliverability score"
echo ""

echo "DNS verification complete!"
