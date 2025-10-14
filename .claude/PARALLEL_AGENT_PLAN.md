# Parallel Agent Execution Plan - Vault Alerts Migration

**Strategy**: Launch 6 agents in parallel across 4 waves
**Estimated Total Time**: ~3.5 hours (down from 9.25 hours sequential)
**Coordination**: File-based locking + git branches

---

## Wave 1: Independent Agents (Launch Simultaneously)

### Agent 1: Anonymizer Consolidation Specialist
**Duration**: 60 minutes
**Branch**: `feature/anonymizer-consolidation`
**Files Owned**:
- `app/jobs/anonymizer.py` (DELETE)
- `app/jobs/vault_alerts_generator.py:1020-1069` (DELETE method)
- `generate_boss_format_langgraph.py:216-253` (DELETE function)
- `tests/test_anonymizer.py` (UPDATE imports)
- `ANONYMIZER_QUICKSTART.md` (UPDATE examples)
- `ANONYMIZATION_TEST_SUMMARY.md` (UPDATE examples)

**Task**:
```
1. Search all CandidateAnonymizer imports: rg "CandidateAnonymizer" -l
2. DELETE app/jobs/anonymizer.py
3. DELETE duplicate anonymization methods in:
   - vault_alerts_generator.py (lines 1020-1069)
   - generate_boss_format_langgraph.py (lines 216-253)
4. UPDATE all imports to: from app.utils.anonymizer import anonymize_candidate_data
5. UPDATE documentation examples to function-based API
6. CREATE tests/test_anonymizer_consolidated.py (6+ test cases)
7. RUN: pytest tests/test_anonymizer_consolidated.py -v
8. VERIFY: rg "CandidateAnonymizer" returns 0 results
9. COMMIT with message: "Phase 1: Consolidate anonymizer to single canonical implementation"
10. UPDATE .claude/agent1_state.json with completion status
```

**MCP Servers**: None needed (pure refactoring)
**Az CLI**: None needed
**Success Criteria**:
- No CandidateAnonymizer imports remain
- 6+ tests pass
- Documentation updated

---

### Agent 2: Feature Flags & Telemetry Engineer
**Duration**: 30 minutes
**Branch**: `feature/feature-flags-telemetry`
**Files Owned**:
- `app/utils/telemetry.py` (CREATE)
- `app/config/feature_flags.py` (MODIFY)
- `.env.local` (MODIFY)

**Task**:
```
1. CREATE app/utils/telemetry.py with TelemetryHelper class:
   - Parse InstrumentationKey from connection string
   - Try/except guard on initialization
   - 15-second batch interval
   - track_zoho_call(duration_ms, success, module) method
2. ADD to app/config/feature_flags.py:
   USE_ZOHO_API = os.getenv('USE_ZOHO_API', 'false').lower() == 'true'
3. ADD to .env.local:
   USE_ZOHO_API=false
4. TEST telemetry initialization:
   python3 -c "from app.utils.telemetry import telemetry; print(telemetry.client)"
5. COMMIT: "Phase 2: Add USE_ZOHO_API flag and centralized telemetry"
6. UPDATE .claude/agent2_state.json
```

**MCP Servers**: Azure MCP (for testing App Insights connection)
**Az CLI**: None needed
**Success Criteria**:
- TelemetryHelper singleton initializes without errors
- USE_ZOHO_API flag accessible in feature_flags module

---

### Agent 3: Async Zoho Client Architect
**Duration**: 120 minutes (LONGEST - determines Wave 1 completion)
**Branch**: `feature/async-zoho-client`
**Files Owned**:
- `app/integrations.py` (MODIFY ZohoApiClient class)

**Task**:
```
1. ADD imports to integrations.py:
   from httpx import AsyncClient, Timeout, Limits, HTTPStatusError
   import time, re
   from typing import Tuple
   from app.utils.telemetry import telemetry

2. ADD lifecycle methods to ZohoApiClient:
   - async def initialize(self)
   - async def close(self)
   - Store self.http_client = None in __init__

3. REFACTOR _make_request to async:
   - Use httpx instead of requests
   - Add telemetry tracking (start/end timer)
   - Add HTTPStatusError exception handling
   - Add _sanitize_pii() helper for error logs
   - Log response body on errors (sanitized)

4. CREATE helper functions (outside class):
   - parse_location(location: str) -> Tuple[str, str]
   - map_to_vault_schema(zoho_candidate: Dict) -> Dict
     (29 fields matching PostgreSQL schema exactly)

5. ADD to ZohoApiClient:
   - _apply_filters(candidates, filters) -> List[Dict]
   - _parse_compensation(comp_str: str) -> int

6. UPDATE query_candidates method:
   - Add custom_filters parameter
   - Call _apply_filters if filters provided

7. CREATE tests/test_data_source_parity.py:
   - test_zoho_field_mapping()
   - test_parse_location()
   - test_parse_compensation()

8. RUN: pytest tests/test_data_source_parity.py::test_zoho_field_mapping -v

9. VERIFY schema mapping with database:
   PGPASSWORD='W3llDB2025Pass' psql -h well-intake-db-0903.postgres.database.azure.com \
     -U adminuser -d wellintake -c "\d vault_candidates"
   Confirm all 29 columns map correctly

10. COMMIT: "Phase 3: Migrate Zoho client to async httpx with 29-field schema mapping"
11. UPDATE .claude/agent3_state.json
```

**MCP Servers**:
- Azure MCP (database verification)
- Context7 (httpx documentation)
**Az CLI**: `az postgres` for schema verification
**Success Criteria**:
- ZohoApiClient fully async
- 29-field mapping matches PostgreSQL schema
- Tests pass
- No blocking HTTP calls remain

---

### Agent 4: Teams Bot Test Engineer
**Duration**: 30 minutes
**Branch**: `feature/teams-bot-tests`
**Files Owned**:
- `tests/test_teams_invoke.py` (CREATE)

**Task**:
```
1. READ app/api/teams/routes.py lines 654-678 to understand handler
2. CREATE tests/test_teams_invoke.py with 3 tests:
   - test_adaptive_card_nested_payload() - msteams.value unwrapping
   - test_adaptive_card_direct_payload() - direct value
   - test_adaptive_card_missing_action() - error handling
3. RUN: pytest tests/test_teams_invoke.py -v
4. VERIFY all 3 tests pass
5. COMMIT: "Phase 6: Add adaptive card invoke regression tests"
6. UPDATE .claude/agent4_state.json
```

**MCP Servers**: None needed
**Az CLI**: None needed
**Success Criteria**: 3 invoke tests pass

---

## Wave 2: Dependent Agents (Launch after Wave 1 completes)

### Agent 5: VaultAlertsGenerator Modernizer
**Duration**: 75 minutes
**Branch**: `feature/vault-alerts-dual-source`
**Dependencies**: Agent 2 (telemetry), Agent 3 (Zoho client)
**Files Owned**:
- `app/jobs/vault_alerts_generator.py`

**Task**:
```
1. WAIT for Agent 2 and Agent 3 completion signals
2. MERGE branches: feature/feature-flags-telemetry + feature/async-zoho-client
3. ADD lifecycle methods to VaultAlertsGenerator:
   - async def initialize(self)
   - async def close(self)
4. UPDATE _agent_database_loader:
   - Add USE_ZOHO_API conditional
   - Implement Zoho API path with cache (vault:zoho:v2:DATE)
   - Keep PostgreSQL path
   - Apply anonymize_candidate_data()
   - MUTATE state (don't return new dict)
5. ADD _fetch_from_database_internal() helper
6. RUN: pytest tests/test_data_source_parity.py::test_data_source_parity -v
7. VERIFY feature flag toggle works
8. COMMIT: "Phase 4: Add dual data source support to VaultAlertsGenerator"
9. UPDATE .claude/agent5_state.json
```

**MCP Servers**: Azure MCP (Redis verification)
**Az CLI**: Test Redis connection
**Success Criteria**: Parity test passes for both data sources

---

### Agent 6: QueryEngine Circuit Breaker Specialist
**Duration**: 30 minutes
**Branch**: `feature/query-engine-lazy-init`
**Dependencies**: Agent 2 (feature flags)
**Files Owned**:
- `app/api/teams/query_engine.py`

**Task**:
```
1. WAIT for Agent 2 completion signal
2. ADD to QueryEngine class:
   - self._initialized = False in __init__
   - async def _ensure_initialized(self)
3. UPDATE _classify_intent_with_llm:
   - Call await self._ensure_initialized()
   - Use redis_manager._is_circuit_breaker_open()
   - Use redis_manager._record_circuit_breaker_failure()
   - DO NOT call record_success()
4. UPDATE execute_query:
   - Add await self._ensure_initialized() at start
5. TEST: Instantiate QueryEngine without errors (lazy init works)
6. COMMIT: "Phase 5: Add lazy Redis initialization to QueryEngine"
7. UPDATE .claude/agent6_state.json
```

**MCP Servers**: Azure MCP (Redis)
**Az CLI**: None needed
**Success Criteria**: QueryEngine initializes without breaking existing call sites

---

## Wave 3: Integration Agents (Launch after Wave 2 completes)

### Agent 7: Boss Email API Developer
**Duration**: 45 minutes
**Branch**: `feature/boss-email-handler`
**Dependencies**: Agent 5 (VaultAlertsGenerator)
**Files Owned**:
- `app/api/teams/routes.py` (add endpoint)

**Task**:
```
1. WAIT for Agent 5 completion signal
2. CHECK WeeklyDigestScheduler signature:
   grep "def send_email" app/jobs/weekly_digest_scheduler.py -A 5
3. ADD endpoint to routes.py:
   @router.post("/admin/send_vault_alerts_to_bosses")
   async def send_vault_alerts_to_bosses(...)
4. IMPLEMENT handler:
   - Initialize VaultAlertsGenerator
   - Call generate_alerts(audience='both')
   - Map bosses to HTML (advisor_html, executive_html)
   - Send emails via WeeklyDigestScheduler.send_email() (NO await)
   - Return JSON with status, emails_sent, execution_time_ms
5. TEST with curl (dry run):
   curl -X POST "http://localhost:8000/api/teams/admin/send_vault_alerts_to_bosses?from_date=2025-01-01" \
     -H "X-API-Key: test"
6. COMMIT: "Phase 7: Add boss email approval endpoint"
7. UPDATE .claude/agent7_state.json
```

**MCP Servers**: Azure MCP (test email delivery)
**Az CLI**: None needed
**Success Criteria**: Endpoint returns 200 with valid JSON

---

### Agent 8: QA Test Engineer
**Duration**: 90 minutes
**Branch**: `feature/comprehensive-tests`
**Dependencies**: Agents 1-7 (all code complete)
**Files Owned**:
- `tests/test_anonymizer_consolidated.py` (Agent 1 created, Agent 8 expands)
- `tests/test_data_source_parity.py` (Agent 3 created, Agent 8 expands)

**Task**:
```
1. WAIT for Agents 1-7 completion signals
2. MERGE all feature branches to integration branch
3. EXPAND test_anonymizer_consolidated.py:
   - test_firm_anonymization()
   - test_location_normalization()
   - test_aum_rounding()
   - test_education_anonymization()
   - test_privacy_mode_disabled()
   - test_missing_fields()
   - test_compensation_anonymization()
4. EXPAND test_data_source_parity.py:
   - test_data_source_parity() (with flag reset in finally)
   - test_zoho_field_mapping() (verify all 29 fields)
5. RUN full test suite:
   pytest tests/test_anonymizer_consolidated.py -v
   pytest tests/test_data_source_parity.py -v
   pytest tests/test_teams_invoke.py -v
   pytest tests/ -k vault -v
6. RUN coverage:
   pytest --cov=app --cov-report=term-missing
7. VERIFY coverage ≥85%
8. COMMIT: "Phase 8: Add comprehensive test coverage (85%+)"
9. UPDATE .claude/agent8_state.json
```

**MCP Servers**: Azure MCP (test database queries)
**Az CLI**: Database verification
**Success Criteria**: All tests pass, coverage ≥85%

---

## Wave 4: Documentation (Launch after Wave 3)

### Agent 9: Technical Writer
**Duration**: 45 minutes
**Branch**: `feature/documentation`
**Dependencies**: Agent 8 (tests confirm everything works)
**Files Owned**:
- `VAULT_ALERTS_GUIDE.md`
- `ANONYMIZER_QUICKSTART.md`
- `ANONYMIZATION_TEST_SUMMARY.md`
- `API_ENDPOINTS.md` (CREATE)

**Task**:
```
1. WAIT for Agent 8 completion signal
2. UPDATE VAULT_ALERTS_GUIDE.md:
   - Add "Data Source Configuration" section
   - Document USE_ZOHO_API flag
   - Document Zoho API limitations
   - Add parity test command
3. UPDATE ANONYMIZER_QUICKSTART.md:
   - Replace all class-based examples with function calls
   - Update import statements
4. UPDATE ANONYMIZATION_TEST_SUMMARY.md:
   - Remove CandidateAnonymizer references
   - Document new test structure
5. CREATE API_ENDPOINTS.md:
   - Document /admin/send_vault_alerts_to_bosses
   - Include curl examples
   - Document response format
6. COMMIT: "Phase 9: Update documentation for Zoho API migration"
7. UPDATE .claude/agent9_state.json
```

**MCP Servers**: None needed
**Az CLI**: None needed
**Success Criteria**: All documentation updated and consistent

---

## Coordination Protocol

### State File Format (`.claude/agentN_state.json`)
```json
{
  "agent_id": 1,
  "phase": "Anonymizer Consolidation",
  "status": "completed",
  "started_at": "2025-10-14T10:00:00Z",
  "completed_at": "2025-10-14T11:00:00Z",
  "branch": "feature/anonymizer-consolidation",
  "files_modified": [
    "app/jobs/anonymizer.py (DELETED)",
    "app/jobs/vault_alerts_generator.py",
    "generate_boss_format_langgraph.py",
    "tests/test_anonymizer.py"
  ],
  "tests_passing": [
    "pytest tests/test_anonymizer_consolidated.py -v (7 passed)"
  ],
  "commit_sha": "abc123def456",
  "blocking_others": false,
  "ready_for_merge": true
}
```

### Dependency Checking
Agents check for dependency completion:
```bash
# Agent 5 checks before starting
if [ -f .claude/agent2_state.json ] && [ -f .claude/agent3_state.json ]; then
  agent2_done=$(jq -r '.status' .claude/agent2_state.json)
  agent3_done=$(jq -r '.status' .claude/agent3_state.json)

  if [ "$agent2_done" == "completed" ] && [ "$agent3_done" == "completed" ]; then
    # Start Wave 2 work
  fi
fi
```

### Merge Strategy
```bash
# After Wave 1 completes
git checkout main
git merge feature/anonymizer-consolidation
git merge feature/feature-flags-telemetry
git merge feature/async-zoho-client
git merge feature/teams-bot-tests

# After Wave 2 completes
git merge feature/vault-alerts-dual-source
git merge feature/query-engine-lazy-init

# After Wave 3 completes
git merge feature/boss-email-handler
git merge feature/comprehensive-tests

# After Wave 4 completes
git merge feature/documentation
```

---

## Timeline Estimate

| Wave | Agents | Duration | Work Done |
|------|--------|----------|-----------|
| Wave 1 | 1, 2, 3, 4 | **120 min** | Anonymizer, flags, Zoho client, tests |
| Wave 2 | 5, 6 | **75 min** | Generator, QueryEngine |
| Wave 3 | 7, 8 | **90 min** | Boss email, comprehensive tests |
| Wave 4 | 9 | **45 min** | Documentation |

**Sequential Total**: 9.25 hours (555 minutes)
**Parallel Total**: ~3.5 hours (210 minutes max path)
**Speedup**: 2.6x faster

---

## Failure Recovery

If any agent fails:
1. Check `.claude/agentN_state.json` for error details
2. Read agent's git branch for partial work
3. Fix issues on that branch
4. Restart that specific agent only
5. Other agents continue unaffected

---

## Launch Commands

### Wave 1 (Launch all simultaneously)
```bash
# Launch 4 agents in parallel
Task(agent_type="general-purpose", description="Anonymizer consolidation", prompt="...")
Task(agent_type="general-purpose", description="Feature flags telemetry", prompt="...")
Task(agent_type="general-purpose", description="Async Zoho client", prompt="...")
Task(agent_type="general-purpose", description="Teams bot tests", prompt="...")
```

### Waves 2-4 (Launch after dependencies complete)
Wait for state files to show "completed", then launch next wave.

---

**Coordinator**: Main Claude instance monitors all agent state files
**Communication**: File-based state + git branches (no race conditions)
**Rollback**: Each agent works on isolated branch (safe to abandon)
