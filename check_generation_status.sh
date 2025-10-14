#!/bin/bash
# Check status of vault alerts generation

echo "========================================================================"
echo "🔍 VAULT ALERTS GENERATION STATUS CHECK"
echo "========================================================================"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if process is running
if ps aux | grep -E "generate_boss_format|generate_test_email" | grep -v grep > /dev/null; then
    echo "✅ Generation process is RUNNING"
    ps aux | grep -E "generate_boss_format|generate_test_email" | grep -v grep | awk '{print "   PID: "$2" | CPU: "$3"% | MEM: "$4"% | CMD: "$11" "$12" "$13}'
    echo ""
else
    echo "❌ Generation process is NOT running"
    echo ""
fi

# Check for output files
echo "📄 Looking for output files..."
echo ""

OUTPUT_FILES=$(find /home/romiteld/Development/Desktop_Apps/outlook -name "vault_alerts_*.html" -mmin -30 2>/dev/null)

if [ -z "$OUTPUT_FILES" ]; then
    echo "   ⏳ No output files found yet (generation still in progress)"
    echo ""
    echo "   Estimated time remaining: 3-8 minutes"
    echo "   (GPT-5 is generating bullets for each candidate)"
else
    echo "   ✅ GENERATION COMPLETE! Found output files:"
    echo ""
    for file in $OUTPUT_FILES; do
        SIZE=$(du -h "$file" | cut -f1)
        MTIME=$(stat -c '%y' "$file" | cut -d'.' -f1)
        echo "   📁 $file"
        echo "      Size: $SIZE | Modified: $MTIME"
        echo ""
    done

    echo "========================================================================"
    echo "📋 NEXT STEPS:"
    echo "========================================================================"
    echo "1. Review the HTML files in your browser"
    echo "2. Run validation: python3 test_validation_only.py"
    echo "3. Send to bosses using template: BOSS_APPROVAL_EMAIL.md"
    echo ""
fi

echo "========================================================================"
echo "💡 TIP: Run this script again in 2-3 minutes to check progress"
echo "========================================================================"
