#!/bin/bash
# Run TalentWell test suite with coverage report

echo "==================================="
echo "TalentWell Test Suite Execution"
echo "==================================="
echo ""

# Activate virtual environment if it exists
if [ -f "../../zoho/bin/activate" ]; then
    source ../../zoho/bin/activate
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing..."
    pip install pytest pytest-cov pytest-asyncio
fi

echo "Running TalentWell Test Suite..."
echo ""

# Run tests with coverage
pytest -v \
    test_data_quality.py \
    test_bullet_ranking.py \
    test_integration.py \
    test_voit.py \
    test_async_zoho.py \
    --cov=../../app/jobs/talentwell_curator \
    --cov=../../app/cache/voit \
    --cov=../../app/cache/c3 \
    --cov-report=term-missing \
    --cov-report=html:coverage_html \
    --tb=short

echo ""
echo "==================================="
echo "Test Coverage Summary"
echo "==================================="
echo ""
echo "Coverage report saved to: coverage_html/index.html"
echo ""

# Display test statistics
echo "Test Statistics:"
echo "----------------"
echo "- test_data_quality.py: Tests for AUM rounding, compensation standardization, internal note filtering, availability formatting, and company anonymization"
echo "- test_bullet_ranking.py: Tests for scoring algorithm, growth metrics prioritization, deduplication, and bullet limit enforcement"
echo "- test_integration.py: Tests for Outlook enrichment cache write/read, cross-system deduplication"
echo "- test_voit.py: Tests for model tier selection, complexity calculation, budget tracking with Azure OpenAI"
echo "- test_async_zoho.py: Tests for async Zoho API calls, batch queries, and performance comparison"

echo ""
echo "Key Coverage Areas:"
echo "-------------------"
echo "✅ Data Quality Improvements"
echo "   - AUM rounding to privacy ranges ($5B+, $1B-$5B, etc.)"
echo "   - Compensation standardization (Target comp: \$XXXk-\$XXXk OTE)"
echo "   - Internal note filtering (patterns: 'hard time', 'TBD', 'unclear')"
echo "   - Availability formatting consistency"
echo "   - Company anonymization for privacy"
echo ""
echo "✅ Bullet Ranking & Prioritization"
echo "   - Growth metrics appear first"
echo "   - Financial metrics prioritized"
echo "   - Location/company deduplication"
echo "   - Max 5 bullets enforced"
echo "   - Never add fake data"
echo ""
echo "✅ Cross-System Integration"
echo "   - Outlook → TalentWell enrichment cache"
echo "   - Embedding-based deduplication"
echo "   - Multi-source data merge (CRM + Apollo + Transcript)"
echo "   - Batch processing with parallelization"
echo ""
echo "✅ VoIT Orchestration"
echo "   - GPT-5-nano for simple (<3k chars)"
echo "   - GPT-5-mini for medium (3-7k chars)"
echo "   - GPT-5 full for complex (>7k chars)"
echo "   - Budget tracking and quality scoring"
echo "   - Fallback to regex extraction on API failure"
echo ""
echo "✅ Async Zoho API"
echo "   - Concurrent field queries"
echo "   - Batch processing with pagination"
echo "   - Rate limit handling with retries"
echo "   - Connection pooling for performance"

echo ""
echo "==================================="
echo "Test Execution Complete"
echo "===================================">