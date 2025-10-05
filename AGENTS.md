# Repository Guidelines

## Project Structure & Module Organization
- `app/` – FastAPI APIs, LangGraph pipelines, and integration clients; trace flows from `app/main.py` and `app/langgraph_manager.py`.
- `addin/` – Outlook taskpane JavaScript, HTML, and manifest assets; `addin/taskpane.js` anchors the front-end.
- `oauth_service/` – Flask proxy that brokers Zoho and internal tokens.
- `tests/` plus `tests/integration/` – pytest suites and browser harnesses like `tests/test_ui_improvements.html`.
- Supporting assets live in `docs/`, `scripts/`, `migrations/`, `static/`, and `templates/` for ADRs, deploy scripts, migrations, and shared UI resources.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate` – create and activate the virtualenv.
- `pip install -r requirements-dev.txt` – install FastAPI, LangGraph, and dev tooling.
- `uvicorn app.main:app --reload --port 8000` – run the API locally with autoreload.
- `npm install --prefix addin && npm run dev --prefix addin` – install taskpane dependencies and start the dev server.
- `pytest` or `pytest tests/integration/test_real_outlook_scenario.py` – execute the full suite or the Outlook integration path.
- `./run_tests.sh` – mirror CI automation before submitting multi-service changes.

## Coding Style & Naming Conventions
- Python: PEP 8, 4 spaces, `snake_case`, and type hints where practical.
- Front-end JS: 2-space indentation, `camelCase`, hyphen-free filenames.
- Prompts and config files: lower-hyphen names (`app/prompts/deal_summary.txt`).
- Format with `black`, `isort`, and `ruff`; lint the taskpane via `npm run lint --prefix addin`.

## Testing Guidelines
- Keep shared fixtures in `tests/fixtures/`; name files `test_<feature>.py`.
- Target ≥85% coverage on business-critical modules using `pytest --cov=app --cov-report=term-missing`.
- Validate manual Outlook flows by sideloading `addin/manifest.xml` into an Office 365 dev tenant.

## Commit & Pull Request Guidelines
- Write imperative subjects ≤65 characters (e.g., `Add redis cache guard`); add bodies when touching multiple services.
- PRs should summarize behavior changes, list impacted endpoints or manifests, link Azure Boards/Jira tickets, and attach taskpane screenshots/GIFs for UX updates.
- Document validation steps (`pytest`, `./run_tests.sh`, `npm run lint --prefix addin`) and flag configuration migrations or manual deployment tasks.

## Security & Configuration Tips
- Do not commit secrets; use `.env.local` templates and Azure Key Vault orchestration through `scripts/setup-github-secrets.sh`.
- Rotate Zoho and Azure tokens via the `oauth_service` configs and refresh manifest cache-bust values after key changes.
- When sharing sandboxes, enable `ENABLE_AZURE_MAPS` and allocate per-developer Redis namespaces to prevent collisions.
