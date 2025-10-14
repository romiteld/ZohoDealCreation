#!/bin/bash
# Monitor boss approval email generation progress

echo "========================================================================"
echo "📊 BOSS APPROVAL EMAIL - GENERATION PROGRESS"
echo "========================================================================"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if process is running
if ps aux | grep "send_boss_approval_email" | grep -v grep | grep -v monitor > /dev/null; then
    echo "✅ Generation process is RUNNING"
    RUNTIME=$(ps aux | grep "send_boss_approval_email.py" | grep -v grep | awk '{print $10}')
    PID=$(ps aux | grep "send_boss_approval_email.py" | grep -v grep | awk '{print $2}')
    echo "   PID: $PID | Runtime: $RUNTIME"
    echo ""
else
    echo "❌ Generation process is NOT running"
    echo ""
fi

# Check log file
if [ -f "boss_email_send.log" ]; then
    echo "📄 Latest log entries:"
    echo "------------------------------------------------------------------------"
    tail -20 boss_email_send.log
    echo "------------------------------------------------------------------------"
    echo ""

    # Check for completion indicators
    if grep -q "EMAIL SENT SUCCESSFULLY" boss_email_send.log; then
        echo "🎉 ✅ EMAIL SENT SUCCESSFULLY!"
        echo ""
        MESSAGE_ID=$(grep "Message ID:" boss_email_send.log | tail -1 | cut -d':' -f2-)
        echo "   Message ID: $MESSAGE_ID"
        echo ""
        echo "Next steps:"
        echo "1. Bosses should receive email from noreply@emailthewell.com"
        echo "2. Wait for their approval confirmation"
        echo "3. After approval, deploy to production"
    elif grep -q "ERROR" boss_email_send.log; then
        echo "❌ ERROR DETECTED in logs - check above for details"
    else
        echo "⏳ STILL PROCESSING..."
        echo ""
        echo "⏰ EXPECTED TIMELINE:"
        echo "   First run (cache empty): 2-3 HOURS"
        echo "   Subsequent runs (cache warm): 8 minutes"
        echo ""
        echo "   This is the FIRST run since cache was cleared"
        echo "   LangGraph + GPT-5 generating bullets for each candidate"
        echo "   Please be patient - check back in 30-60 minutes"
    fi
else
    echo "📄 Log file not created yet"
    echo "   Process may still be starting up..."
fi

echo ""
echo "========================================================================"
echo "💡 TIPS:"
echo "========================================================================"
echo "• Run this script again: bash monitor_boss_email.sh"
echo "• Watch live: tail -f boss_email_send.log"
echo "• Check every 30-60 minutes during first run"
echo "========================================================================"
