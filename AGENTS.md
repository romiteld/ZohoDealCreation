# Repository Guidelines

## 1. Repository Overview
This monorepo powers TalentWell’s Outlook and Teams automation platform. It blends FastAPI services, LangGraph-powered conversational agents, a Teams bot, Outlook add-ins, background digest jobs, and integration clients for Zoho CRM and Zoom. Every component lives here—from the bot webhook (Azure Container Apps) to the Node-based taskpane UI that surfaces weekly digests. Contributors should treat the repo as a coordinated suite: updates often cross Python services, JavaScript front-ends, SQL migrations, and infrastructure scripts.

## 2. Architecture & Project Layout
- `app/` – Primary FastAPI application. Key submodules:
  - `app/api/teams/` – Teams bot endpoints (`routes.py`), conversation memory (`conversation_memory.py`), clarification engine, adaptive card builders, query engine, and supporting managers.
  - `app/langgraph_manager.py` – Central orchestration for LangGraph pipelines that chain LLM tools.
  - `app/jobs/` – Background jobs (e.g., `talentwell_curator.py`) for weekly digest generation.
  - `app/zoom_client.py` – Async Zoom REST client with retry logic.
  - `app/integrations/ZohoApiClient` (imported) uses asset files in `/zoho` to query CRM modules.
  - `app/prompts/` – Prompt templates for LLM interactions (e.g., deal summaries).
  - `app/templates/` – Jinja/email templates, including `email/weekly_digest_v1.html`.
  - `app/static/` – Static assets (logos, CSS) referenced by FastAPI routes.
- `addin/` – Outlook taskpane client. Contains `taskpane.js`, HTML shell, manifest assets, localized strings, and the webpack/npm config for building or sideloading.
- `oauth_service/` – Flask microservice issuing Zoho/internal tokens for other services.
- `well_shared/` – Shared configuration and infrastructure helpers (VoIT model mapping, Redis cache manager, telemetry).
- `teams_bot/` – Additional Teams bot deployment configuration, including manifest packaging.
- `migrations/` – Ordered SQL scripts (e.g., `007_conversation_state_enhancements.sql`, `008_clarification_taxonomy_fix.sql`). Run via psql or scripted pipeline.
- `tests/` & `tests/integration/` – Pytest suites, manual browser harnesses, and fixtures.
- `scripts/` – Operational utilities (Azure environment sync, GitHub secret setup, DNS/DKIM checks, container updates).
- `zoho/` – JSON mappings for Zoho CRM modules, sample payloads, and payment module descriptions used by ingestion jobs.
- Supporting root assets include container manifests (`weekly-digest-job.yaml`), deployment helpers (`deploy.sh`, `startup.sh`, `update-container-env.sh`), and data exports (CSV/PDF) for local validation.

## 3. Services & Execution Flow
1. **Teams Bot API** (`app/api/teams/routes.py`): Receives webhook messages, stores to `teams_conversations`, classifies intent through `QueryEngine`, delegates to conversation memory and clarification engine, and issues Zoho/Zoom queries.
2. **Conversation Memory & Clarification**: `conversation_memory.py` handles Redis hot storage w/ PostgreSQL fallbacks; `clarification_engine.py` runs GPT-5 prompts for disambiguation, manages sessions, and orchestrates adaptive cards.
3. **LangGraph Pipelines**: `langgraph_manager.py` harnesses the LangGraph framework to define agent workflows, enabling multi-step reasoning and tool invocations.
4. **Weekly Digest Jobs**: `app/jobs/talentwell_curator.py`, `run_talentwell_with_real_twav.py`, and `weekly-digest-job.yaml` orchestrate multi-stage candidate selection, Zoom transcript enrichment, and digest rendering.
5. **Outlook Taskpane (addin/)**: Presents digests, filter controls, and preferences via React-like components that consume the FastAPI endpoints.
6. **OAuth Proxy**: `oauth_service` secures Zoho access tokens and reduces surface area for credentials inside the Teams bot.
7. **Shared Utilities**: `well_shared` ensures consistent configuration across services (e.g., `VoITConfig`, Redis clients, App Insights telemetry instrumentation).

## 4. Data Integrations & Asset Inventory
### 4.1 Zoho CRM Assets (`zoho/`)
- `zoho_custom_views.json` – Custom view definitions for CRM modules; consumed when building query filters.
- `zoho_leads_custom_views.json` – Lead-specific view metadata.
- `zoho_deals_fields.json` – Field schema for Deals module (names, labels, API keys).
- `zoho_lead_fields.json`, `zoho_leads_fields.json`, `zoho_leads_all_fields_complete.json` – Comprehensive lead field inventories, enabling validation and auto-mapping.
- `zoho_notes_fields.json` – Schema for Notes module, used when appending timeline entries.
- `zoho_payment_findings.json` & `zoho_payment_modules.json` – Payment module enumerations and audit findings for finance feature sets.
- `zoho_sample_vault_candidate.json`, `zoho_vault_candidates_detailed.json` – Sample payloads for candidate digests.
- `zoho_leads_view.json`, `zoho_api modules field mappings.md`, and other JSON/Markdown documents provide reverse-engineered module metadata.
- Time-series exports (`Deals_*.csv`, `Candidates_*.csv`, etc.) validate migrations and offline transformations (keep sanitized or git-ignored when containing PII).
### 4.2 Zoom Integration
- `app/zoom_client.py` handles listing recordings, participant/topic searches, transcript retrieval, and URL parsing. Retry logic uses exponential backoff with jitter. Related helper scripts (`list_zoom_recordings.py`, `store_zoom_meetings_enhanced.py`) support ad-hoc reconciliation.
### 4.3 Outlook & Teams Manifests
- `teams-app-manifest.json` & `teams-app-package/` package the Teams app; `addin/manifest.xml` is sideloaded for Outlook.
### 4.4 Telemetry & Monitoring
- `well_shared/config/voit_config.py` resolves actual GPT models (e.g., `gpt-5-mini`, `gpt-5-nano`); metrics emitted through `monitoring.gpt_request_counter` track clarifications, fallbacks, and classification requests.

## 5. Build, Run, and Test Workflows
### 5.1 Environment Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
npm install --prefix addin
```
Set environment variables via `.env.local` templates or Azure Key Vault (`scripts/setup-github-secrets.sh`).

### 5.2 Local Development
- **FastAPI**: `uvicorn app.main:app --reload --port 8000`
- **Outlook Add-in**: `npm run dev --prefix addin`
- **OAuth proxy**: `python oauth_service/app.py`
- **LangGraph**: custom runs through `python app/langgraph_manager.py` or service wrappers.

### 5.3 Quality Gates
- Python formatting: `black .`, `isort .`, `ruff check .`
- JS linting: `npm run lint --prefix addin`
- Type-checking (if TS introduced): `npx tsc --noEmit --project addin/tsconfig.json`

### 5.4 Testing
- Unit: `pytest`
- Coverage: `pytest --cov=app --cov-report=term-missing`
- Integration: `pytest tests/integration/test_real_outlook_scenario.py`
- Regression suite: `./run_tests.sh` (mirrors CI pipeline) and `python run_all_tests.py`
- Manual flows: Sideload `addin/manifest.xml` into an O365 dev account; use Teams test tenant for Bot commands; run `weekly-digest-job.yaml` via `az containerapp job start`.

### 5.5 Deployment & Ops
- Container builds: `docker build -f teams_bot/Dockerfile ...`
- Push to Azure Container Registry: `docker push wellintakeacr0903.azurecr.io/...`
- Update Azure Container App: `az containerapp update --name teams-bot --resource-group TheWell-Infra-East --image ...`
- Job updates (weekly digest): `az containerapp job update --name weekly-digest --resource-group ...`
- Logs/insights: `az containerapp logs show --name teams-bot --resource-group ... --follow` and Application Insights dashboards.

## 6. Coding Standards & Conventions
### 6.1 Python
- Structure modules by domain (API, jobs, integrations).
- Use `snake_case` for variables/functions, `CamelCase` for classes.
- Annotate public functions with type hints; add docstrings (Google-style or reST) for complex logic.
- Avoid tight coupling between API endpoints and integrations—use service classes (e.g., QueryEngine) for abstractions.
- Enforce formatting with `black`/`isort` and static analysis via `ruff` (handles lint, complexity, import hygiene).

### 6.2 JavaScript/TypeScript (addin)
- 2-space indentation, `camelCase` variable names, `PascalCase` components.
- Keep UI logic modular; reuse helper utilities inside `addin/src/utils/` (if present).
- Manage state with React hooks or context (depending on current architecture).
- Run `npm run lint --prefix addin` prior to commits; follow ESLint/Prettier output.

### 6.3 Configuration & Prompts
- Lower-hyphen file names (`deal_summary.txt`, `weekly_digest_v1.html`).
- Keep prompts versioned; note LLM model dependencies inside comments.
- YAML: 2-space indentation, descriptive keys (e.g., `jobs.weekly-digest`).

### 6.4 Commit Standards
- `Add redis cache guard` (imperative, short). Provide descriptive bodies when changes cross services or require infra steps.
- Reference ticket IDs in commit body or PR description if policy requires.

## 7. Detailed Testing Strategy
- **Unit Tests**: Most Python modules expose unit tests inside `tests/app/...` or `tests/teams/...`. When altering conversation logic, update `tests/teams/test_conversation_flow.py` to cover new branches (low/med/high confidence, clarification sessions, rate limiting, override intents).
- **Integration Tests**: Browser-based HTML harnesses ensure Outlook UI features remain stable (`tests/test_ui_improvements.html`). Use Selenium/Playwright as needed for automated coverage.
- **Coverage Targets**: Maintain ≥85% on `app/api/teams/*`; additional modules should hover near that threshold unless justified.
- **Test Data**: Use sanitized CSVs/JSONs stored in `tests/fixtures/`; do not pull raw PII exports into version control.
- **CI Hook**: `./run_tests.sh` packages Python, Node, and integration checks; ensure this passes before merging.

## 8. Deployment Workflow & Infrastructure Notes
1. **Migrations**: Apply sequentially using `psql` or migration tooling. Mark PRs with new migrations; coordinate DB updates with DevOps.
2. **Secrets**: Manage through Azure Key Vault. Local `.env.local` templates instruct developers which values to supply. For CI, run `scripts/setup-github-secrets.sh` to sync.
3. **Containers**: Both Teams bot and weekly digest job run on Azure Container Apps. Use `startup.sh` and `Dockerfile` as canonical build scripts.
4. **Monitoring**: App Insights collects metrics; `monitoring.gpt_request_counter` records classification, clarification, and fallback events. Alerting dashboards should track rates for `clarification_triggered`, `clarification_resolved`, `clarification_expired`, `redis_fallback`.
5. **Cron Jobs**: Azure Container App jobs trigger digests; ensure timezone alignment and environment variables (e.g., Zoho credentials) loaded from Key Vault.
6. **Rollback**: Container images tagged with commit IDs allow redeploy with `az containerapp update --revision-suffix <previous>`.

## 9. Security, Compliance, and Data Handling
- **Secrets Management**: `.env` files are excluded by default; never commit tokens/keys. All long-lived credentials (Zoho, Zoom, Azure) rotate via Key Vault.
- **Data Protection**: CSV/PDF exports under root are sanitized; when ingesting new data files, anonymize identifiers before committing.
- **OAuth Proxy**: `oauth_service/` isolates token exchange logic; ensure TLS termination and origin checks when deploying.
- **Rate Limiting**: Clarification engine enforces per-user limits (3 per 5 minutes). Adjust logic carefully; ensure tests cover new bounds.
- **Redis Isolation**: Use namespace prefixes per developer/test environment. Production uses `ENABLE_AZURE_MAPS` toggles and unique caches to avoid collisions.
- **Compliance Scripts**: DNS/DKIM verification (`verify_azure_dns.sh`, `verify_dmarc_fix.sh`) ensure email deliverability and security posture.

## 10. Additional Assets & Utilities
- **Operations Scripts**: `update-container-env.sh`, `deploy.sh`, `startup.sh`, `run_teams_migration.py`, `run_all_tests.py` provide wrappers for frequent tasks.
- **Validation Tools**: `validate_manifest.py`, `validate_fa_extraction.py`, `find_zoho_contact.py` support QA/troubleshooting.
- **Data Harvesters**: `store_zoom_meeting_ids.py`, `store_zoom_meetings_enhanced.py`, `generate_real_brandon_digest.py` extend core functionality—update responsibly when API contracts change.
- **Documentation**: `docs/` holds ADRs, developer onboarding, and architectural outlines; `CLAUDE.md` may include AI-specific instructions.

## 11. Contributor Expectations
- Understand cross-service coupling: e.g., a change in `conversation_memory.py` impacts Teams bot flows, LangGraph state, migrations, and analytics views.
- Maintain parity between runtime code and SQL migrations; update views/functions when altering schema or telemetry.
- Provide comprehensive PR descriptions, referencing affected modules (`app/api/teams/routes.py`, `app/zoom_client.py`, `zoho/*.json`) and steps to reproduce/validate.
- Coordinate with DevOps when altering Azure resources or secrets. Document manual steps in `deployment.log` or PR comments.

## 12. Appendices
### A. Zoho Module Inventory (Summary)
- **Deals**: Fields described in `zoho_deals_fields.json`; includes pipeline stage metadata, owner info, and custom attributes used to populate digests.
- **Leads**: Refer to `zoho_lead_fields.json` and `zoho_leads_all_fields_complete.json` for API field names, data types, and mandatory flags.
- **Notes**: `zoho_notes_fields.json` enumerates note content fields and relationships.
- **Payments**: Data captured in `zoho_payment_modules.json` and analyzed in `zoho_payment_findings.json` to surface anomalies.
- **Vault Candidates**: Sample payloads in `zoho_sample_vault_candidate.json`/`zoho_vault_candidates_detailed.json` demonstrate the shape consumed by digest jobs.

### B. Key Environment Variables
- `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`
- `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
- `REDIS_URL`, `ENABLE_AZURE_MAPS`
- `OPENAI_API_KEY`, `VOIT_MODEL_OVERRIDE`
- `WEEKLY_DIGEST_AUDIENCE`, `DIGEST_TEMPLATE_VERSION`

### C. Troubleshooting Checklist
1. **Teams Bot errors**: Inspect `app/api/teams/routes.py` logs via `az containerapp logs show`; confirm Redis connectivity.
2. **Clarification not triggering**: Verify confidence thresholds in `app/api/teams/conversation_state.py` and session TTL in Redis; run `pytest tests/teams/test_conversation_flow.py`.
3. **Zoom transcript failures**: Ensure `_request_with_retry` in `app/zoom_client.py` returns success; check Zoom credentials via `python list_zoom_recordings.py`.
4. **Zoho schema drift**: Regenerate JSON mappings by hitting Zoho describe endpoints; update `zoho/*.json` and align ingestion logic.
5. **Digest styling issues**: Validate `app/templates/email/weekly_digest_v1.html` against audit requirements; run preview via `python run_talentwell_with_real_twav.py`.

---
Maintain this document as the canonical contributor reference. Update sections when new services, migrations, or integrations launch so future agents have a reliable, exhaustive guide to the repository.
