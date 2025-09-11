# TalentWell Test Suite

Comprehensive test suite for the TalentWell import and persistence system, covering CSV imports, policy seed generation, and Outlook email intake functionality.

## Overview

This test suite provides comprehensive coverage for:

1. **Import/Export System** (`test_import_exports.py`)
   - CSV parsing with various encodings and formats
   - Column mapping resilience and aliases
   - Idempotent upsert operations
   - File size and row limits
   - Multipart upload handling
   - Auto-cleanup of old uploads

2. **Policy Seed Generation** (`test_seed_policies.py`)
   - Employer normalization (National vs Independent)
   - City to metro area mapping
   - Subject line bandit prior calculation
   - Selector prior generation
   - Redis operations without TTL
   - Database persistence and versioning

3. **Outlook Email Intake** (`test_intake_outlook.py`)
   - Email processing idempotency
   - Transaction commit/rollback handling
   - Retry logic for API failures
   - Correlation ID generation and tracking
   - Comprehensive audit logging
   - Input validation and sanitization

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── fixtures/
│   ├── sample_csv_files.py       # CSV test data with edge cases
│   └── outlook_payloads.py       # Realistic email payloads
├── test_import_exports.py        # CSV import system tests
├── test_seed_policies.py         # Policy generation tests  
├── test_intake_outlook.py        # Email intake tests
├── run_talentwell_tests.py       # Test runner script
├── requirements-test.txt         # Test dependencies
└── README_TALENTWELL_TESTS.md   # This file
```

## Running Tests

### Quick Start

```bash
# Run all TalentWell tests
python tests/run_talentwell_tests.py

# Run with coverage reporting
python tests/run_talentwell_tests.py --coverage

# Run specific test file
python tests/run_talentwell_tests.py tests/test_import_exports.py

# Run tests in parallel
python tests/run_talentwell_tests.py --parallel
```

### Using pytest directly

```bash
# Run all TalentWell tests
python -m pytest tests/test_import_exports.py tests/test_seed_policies.py tests/test_intake_outlook.py -v

# Run with coverage
python -m pytest tests/test_import_exports.py tests/test_seed_policies.py tests/test_intake_outlook.py \
  --cov=app.admin.import_exports --cov=app.admin.seed_policies --cov=app.main \
  --cov-report=term-missing --cov-report=html:tests/htmlcov

# Run only unit tests
python -m pytest -m unit -v

# Run only integration tests  
python -m pytest -m integration -v

# Run specific test class
python -m pytest tests/test_import_exports.py::TestCSVParsing -v

# Run specific test method
python -m pytest tests/test_import_exports.py::TestCSVParsing::test_parse_valid_csv -v
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
Fast, isolated tests that mock external dependencies:
- CSV parsing logic
- Data validation and sanitization
- Business rule application
- Error handling

### Integration Tests (`@pytest.mark.integration`)
Tests that verify component interactions:
- Database operations
- Redis caching
- Zoho API integration
- Email processing pipeline

### Slow Tests (`@pytest.mark.slow`)
Performance and load tests:
- Large file processing
- Concurrent operations
- Memory usage validation
- Timeout behavior

## Key Features

### 1. Comprehensive Mocking
- PostgreSQL database operations
- Redis cache management
- Zoho API responses
- LangGraph processing
- Azure services integration

### 2. Realistic Test Data
- Multiple CSV formats and encodings
- Various email types (recruitment, referral, candidate applications)
- Edge cases and malformed data
- Performance test datasets

### 3. Error Injection
```python
# Use error_injector fixture to test failure scenarios
def test_database_failure(error_injector):
    error_injector.inject_database_error("Connection failed")
    # Test database failure handling
```

### 4. Performance Monitoring
```python
# Use performance_monitor fixture to track metrics
def test_large_import_performance(performance_monitor):
    performance_monitor.start()
    # Run performance-critical code
    performance_monitor.stop()
    
    assert performance_monitor.elapsed_time < 5.0
    assert performance_monitor.memory_usage['peak_mb'] < 512
```

### 5. Concurrency Testing
```python
# Use concurrency_tester fixture for parallel operations
async def test_concurrent_processing(concurrency_tester):
    results, errors = await concurrency_tester.run_concurrent(
        process_email, email1, email2, email3
    )
    assert len(errors) == 0
    assert len(results) == 3
```

## Test Data Fixtures

### CSV Test Data
- **Valid data**: Properly formatted CSV with all required fields
- **Mixed encodings**: UTF-8, Unicode characters, special symbols
- **Date formats**: Various date/time formats commonly found in Zoho exports
- **Column aliases**: Alternative column names and mappings
- **Malformed data**: Broken quotes, missing fields, encoding issues
- **Large datasets**: Performance testing with 10K+ rows
- **Edge cases**: Empty files, header-only, whitespace issues

### Email Test Data  
- **Recruitment emails**: Professional recruiter outreach
- **Referral emails**: Internal and partner referrals
- **Candidate applications**: Direct applications with attachments
- **Headhunter pitches**: Multiple candidates in single email
- **Forwarded emails**: Nested email content
- **Bulk emails**: Mass recruiting messages
- **Malformed emails**: Encoding issues and sanitization tests

## Environment Setup

### Test Environment Variables
Tests use isolated environment variables defined in `conftest.py`:

```python
test_env = {
    'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
    'API_KEY': 'test-api-key-12345',
    'OPENAI_API_KEY': 'sk-test-openai-key',
    'USE_LANGGRAPH': 'true',
    # ... other test-specific variables
}
```

### Dependencies
Install test dependencies with:
```bash
pip install -r tests/requirements-test.txt
```

Key testing libraries:
- **pytest**: Test framework
- **pytest-asyncio**: Async test support
- **pytest-mock**: Mocking utilities
- **pytest-cov**: Coverage reporting
- **pytest-timeout**: Test timeout handling
- **pytest-xdist**: Parallel test execution

## Coverage Goals

Target coverage metrics:
- **Line coverage**: > 80% for all modules
- **Branch coverage**: > 70% for conditional logic
- **Function coverage**: > 90% for public APIs

Generate coverage reports:
```bash
python tests/run_talentwell_tests.py
# View HTML report: tests/htmlcov/index.html
```

## Best Practices

### Test Organization
- Group related tests in classes
- Use descriptive test names that explain the scenario
- Follow Arrange-Act-Assert pattern
- Keep tests isolated and independent

### Fixtures and Mocking
- Use fixtures for common setup
- Mock external dependencies consistently
- Provide realistic test data
- Clean up resources after tests

### Error Testing
- Test both success and failure paths
- Verify error messages and status codes
- Test recovery mechanisms
- Validate transaction rollback

### Performance Testing
- Set reasonable performance baselines
- Test with realistic data volumes
- Monitor memory usage and response times
- Test concurrent operations

## Debugging Failed Tests

### Common Issues
1. **Import errors**: Check PYTHONPATH and module imports
2. **Missing fixtures**: Verify conftest.py is loaded correctly
3. **Mock configuration**: Ensure mocks match actual API signatures
4. **Async tests**: Use proper async fixtures and decorators
5. **Database tests**: Verify transaction mocking is correct

### Debug Techniques
```bash
# Run with verbose output
python -m pytest tests/test_import_exports.py -v -s

# Drop into debugger on failure
python -m pytest tests/test_import_exports.py --pdb

# Show full traceback
python -m pytest tests/test_import_exports.py --tb=long

# Run single test with detailed output
python -m pytest tests/test_import_exports.py::TestCSVParsing::test_parse_valid_csv -v -s --tb=short
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: TalentWell Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r tests/requirements-test.txt
      - name: Run TalentWell tests
        run: python tests/run_talentwell_tests.py --coverage
      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          file: ./tests/coverage.xml
```

## Contributing

When adding new tests:

1. **Follow naming conventions**: `test_*.py` for files, `test_*` for functions
2. **Add appropriate markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
3. **Update fixtures**: Add new test data to fixture files
4. **Document complex tests**: Add docstrings explaining test scenarios
5. **Verify coverage**: Ensure new code is adequately tested

## Support

For questions about the test suite:
1. Check this README for common patterns
2. Review existing tests for examples
3. Look at conftest.py for available fixtures
4. Run tests in verbose mode for debugging

## Changelog

### Version 1.0 (2025-01-15)
- Initial comprehensive test suite
- CSV import system tests
- Policy seed generation tests  
- Outlook email intake tests
- Performance and concurrency testing
- Comprehensive fixture system