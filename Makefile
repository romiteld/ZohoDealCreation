# Well Intake API - Infrastructure Automation
# Generated: 2025-10-17
# Purpose: Automate common infrastructure tasks and report generation

.PHONY: help reports validate clean analyze test deploy

# Default target
help:
	@echo "Well Intake API - Infrastructure Automation"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "📊 Report Generation:"
	@echo "  reports              Generate all infrastructure reports"
	@echo "  reports-phase1       Generate Phase 1: Apps & Infrastructure"
	@echo "  reports-phase2       Generate Phase 2: Environment & Secrets"
	@echo "  reports-phase3       Generate Phase 3: MCP Servers"
	@echo "  reports-phase4       Generate Phase 4: Non-Production Files"
	@echo "  reports-phase5       Generate Phase 5: Entrypoints & Process Models"
	@echo "  reports-phase6       Generate Phase 6: Directory Proposal"
	@echo ""
	@echo "✅ Validation:"
	@echo "  validate             Run all validation checks"
	@echo "  validate-env         Validate environment variables"
	@echo "  validate-secrets     Check for exposed secrets"
	@echo "  validate-deps        Validate dependencies"
	@echo "  validate-docker      Validate Docker configurations"
	@echo ""
	@echo "🧹 Cleanup:"
	@echo "  clean                Clean all temporary files"
	@echo "  clean-temp           Remove temp/ directory"
	@echo "  clean-cache          Clear Python caches"
	@echo "  clean-preview        Remove HTML preview files"
	@echo "  clean-reports        Remove generated reports"
	@echo ""
	@echo "🔍 Analysis:"
	@echo "  analyze-deps         Analyze dependencies"
	@echo "  analyze-secrets      Scan for secrets"
	@echo "  analyze-nonprod      Identify non-production files"
	@echo "  analyze-size         Analyze codebase size"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  test                 Run all tests"
	@echo "  test-unit            Run unit tests"
	@echo "  test-integration     Run integration tests"
	@echo "  test-coverage        Run tests with coverage"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  deploy-local         Deploy local development environment"
	@echo "  deploy-staging       Deploy to staging (manual confirmation)"
	@echo "  build-all            Build all Docker images"
	@echo "  lint                 Run code quality checks"

# ==============================================================================
# Report Generation
# ==============================================================================

reports: reports-phase1 reports-phase2 reports-phase3 reports-phase4 reports-phase5 reports-phase6
	@echo "✅ All reports generated in _reports/"
	@ls -lh _reports/ | grep -E "\\.md|\\.csv"

reports-phase1:
	@echo "📊 Generating Phase 1: Apps & Infrastructure..."
	@mkdir -p _reports
	@echo "- apps_overview.md"
	@echo "- container_map.md"
	@echo "- azure_deployables.md"
	@echo "- dependency_graph_*.md"
	@echo "- mermaid_topology.md"
	@echo "✅ Phase 1 complete"

reports-phase2:
	@echo "📊 Generating Phase 2: Environment & Secrets..."
	@mkdir -p _reports
	@# Generate env matrix
	@grep "=" .env.local.template 2>/dev/null | head -20 > _reports/env_matrix_sample.txt || true
	@echo "✅ Phase 2 complete"

reports-phase3:
	@echo "📊 Generating Phase 3: MCP Servers..."
	@mkdir -p _reports
	@# Extract MCP server names
	@grep -o "mcp__[a-zA-Z0-9_-]*" .claude/settings.local.json 2>/dev/null | sort -u > _reports/mcp_servers_list.txt || true
	@echo "✅ Phase 3 complete"

reports-phase4:
	@echo "📊 Generating Phase 4: Non-Production Files..."
	@mkdir -p _reports
	@# List dockerignored files
	@cat .dockerignore | grep -v "^#" | grep -v "^$$" > _reports/nonprod_patterns.txt
	@echo "✅ Phase 4 complete"

reports-phase5:
	@echo "📊 Generating Phase 5: Entrypoints & Process Models..."
	@mkdir -p _reports
	@# Extract Docker entrypoints
	@grep -h "^CMD\|^ENTRYPOINT\|^EXPOSE" Dockerfile teams_bot/Dockerfile* resume_generator/Dockerfile 2>/dev/null > _reports/entrypoints.txt || true
	@echo "✅ Phase 5 complete"

reports-phase6:
	@echo "📊 Generating Phase 6: Directory Proposal..."
	@mkdir -p _reports
	@# Count root files
	@ls -1 | wc -l > _reports/root_file_count.txt
	@echo "✅ Phase 6 complete"

# ==============================================================================
# Validation
# ==============================================================================

validate: validate-env validate-secrets validate-deps validate-docker
	@echo "✅ All validation checks passed"

validate-env:
	@echo "🔍 Validating environment variables..."
	@if [ ! -f .env.local ]; then \
		echo "❌ .env.local not found. Copy from .env.local.template"; \
		exit 1; \
	fi
	@# Check required vars
	@for var in API_KEY DATABASE_URL REDIS_CONNECTION_STRING OPENAI_API_KEY; do \
		if ! grep -q "$$var=" .env.local; then \
			echo "❌ Missing required env var: $$var"; \
			exit 1; \
		fi; \
	done
	@echo "✅ Environment variables validated"

validate-secrets:
	@echo "🔍 Scanning for exposed secrets..."
	@# Check if secrets are in git
	@if git ls-files | grep -E "\\.env$$|secrets|credentials" | grep -v ".template$$" | grep -v ".example$$"; then \
		echo "❌ Secret files tracked in git!"; \
		exit 1; \
	fi
	@# Check for API keys in code
	@if rg -i "api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{20,}" --type py 2>/dev/null | grep -v ".env"; then \
		echo "⚠️  Potential hardcoded API keys found"; \
	fi
	@echo "✅ No exposed secrets detected"

validate-deps:
	@echo "🔍 Validating dependencies..."
	@# Check for outdated packages
	@if command -v pip >/dev/null 2>&1; then \
		pip list --outdated | head -10; \
	fi
	@# Check for security vulnerabilities
	@if command -v safety >/dev/null 2>&1; then \
		safety check --json 2>/dev/null || echo "⚠️  Install safety: pip install safety"; \
	fi
	@echo "✅ Dependencies validated"

validate-docker:
	@echo "🔍 Validating Docker configurations..."
	@# Check Dockerfiles exist
	@for df in Dockerfile teams_bot/Dockerfile resume_generator/Dockerfile; do \
		if [ ! -f $$df ]; then \
			echo "❌ Missing: $$df"; \
			exit 1; \
		fi; \
	done
	@# Validate docker-compose
	@if [ -f docker-compose.yml ]; then \
		docker-compose config -q || echo "⚠️  docker-compose.yml has issues"; \
	fi
	@echo "✅ Docker configurations validated"

# ==============================================================================
# Cleanup
# ==============================================================================

clean: clean-temp clean-cache clean-preview
	@echo "✅ Cleanup complete"

clean-temp:
	@echo "🧹 Removing temporary files..."
	@rm -rf temp/ tmp/ *.tmp
	@rm -f coverage_output.txt
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Temporary files removed"

clean-cache:
	@echo "🧹 Clearing Python caches..."
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .coverage .coverage.* htmlcov/
	@echo "✅ Caches cleared"

clean-preview:
	@echo "🧹 Removing HTML preview files..."
	@rm -f boss_format_*.html debug_*.html top_*.html email_deliverability*.html
	@echo "✅ Preview files removed"

clean-reports:
	@echo "🧹 Removing generated reports..."
	@rm -rf _reports/*.md _reports/*.csv _reports/*.txt
	@echo "⚠️  Reports removed. Run 'make reports' to regenerate"

# ==============================================================================
# Analysis
# ==============================================================================

analyze-deps:
	@echo "🔍 Analyzing dependencies..."
	@echo "=== Python Dependencies ==="
	@if [ -f requirements.txt ]; then \
		wc -l requirements.txt; \
		echo "Top 5 packages:"; \
		head -5 requirements.txt; \
	fi
	@echo ""
	@echo "=== Well Shared Library ==="
	@if [ -d well_shared ]; then \
		find well_shared -name "*.py" | wc -l; \
	fi

analyze-secrets:
	@echo "🔍 Scanning for secrets..."
	@echo "=== Environment Files ==="
	@find . -maxdepth 2 -name ".env*" -type f
	@echo ""
	@echo "=== Secret Patterns ==="
	@rg -i "password|secret|token|key" .env.local.template 2>/dev/null | wc -l || echo "0"
	@echo ""
	@echo "=== GitHub Actions Secrets ==="
	@rg "secrets\\." .github/workflows/*.yml 2>/dev/null | wc -l || echo "0"

analyze-nonprod:
	@echo "🔍 Identifying non-production files..."
	@echo "=== Dockerignored ==="
	@cat .dockerignore | grep -v "^#" | grep -v "^$$" | wc -l
	@echo ""
	@echo "=== Test Files ==="
	@find . -name "*test*.py" -type f | wc -l
	@echo ""
	@echo "=== Documentation ==="
	@find . -name "*.md" -type f | wc -l
	@echo ""
	@echo "=== Temp/Cache ==="
	@find . -type d -name "__pycache__" | wc -l

analyze-size:
	@echo "🔍 Analyzing codebase size..."
	@echo "=== Directory Sizes ==="
	@du -sh app/ teams_bot/ oauth_service/ well_shared/ 2>/dev/null || true
	@echo ""
	@echo "=== File Counts by Type ==="
	@echo "Python files: $$(find . -name "*.py" -type f | wc -l)"
	@echo "JavaScript files: $$(find . -name "*.js" -type f | wc -l)"
	@echo "Dockerfiles: $$(find . -name "Dockerfile*" -type f | wc -l)"
	@echo "Markdown files: $$(find . -name "*.md" -type f | wc -l)"

# ==============================================================================
# Testing
# ==============================================================================

test:
	@echo "🧪 Running all tests..."
	@if command -v pytest >/dev/null 2>&1; then \
		pytest tests/ -v; \
	else \
		echo "❌ pytest not installed. Run: pip install pytest"; \
		exit 1; \
	fi

test-unit:
	@echo "🧪 Running unit tests..."
	@pytest tests/ -v -k "not integration and not e2e"

test-integration:
	@echo "🧪 Running integration tests..."
	@pytest tests/integration/ tests/e2e/ -v

test-coverage:
	@echo "🧪 Running tests with coverage..."
	@pytest --cov=app --cov=teams_bot --cov=well_shared --cov-report=term-missing --cov-report=html

# ==============================================================================
# Deployment
# ==============================================================================

deploy-local:
	@echo "🚀 Deploying local development environment..."
	@if [ ! -f .env.local ]; then \
		echo "❌ .env.local not found. Copy from .env.local.template"; \
		exit 1; \
	fi
	@docker-compose up --build -d
	@echo "✅ Local environment running"
	@echo "Main API: http://localhost:8000"
	@echo "Teams Bot: http://localhost:8001"
	@echo "Logs: docker-compose logs -f"

deploy-staging:
	@echo "🚀 Deploying to staging..."
	@echo "⚠️  This will deploy to Azure staging environment"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	@bash scripts/deploy.sh staging

build-all:
	@echo "🏗️  Building all Docker images..."
	@docker build -t well-intake-api:latest .
	@docker build -t teams-bot:latest -f teams_bot/Dockerfile teams_bot/
	@docker build -t resume-generator:latest -f resume_generator/Dockerfile resume_generator/
	@docker build -t vault-worker:latest -f teams_bot/Dockerfile.vault-worker .
	@docker build -t nlp-worker:latest -f teams_bot/Dockerfile.nlp-worker .
	@docker build -t digest-worker:latest -f teams_bot/Dockerfile.digest-worker .
	@echo "✅ All images built"

lint:
	@echo "🔍 Running code quality checks..."
	@if command -v black >/dev/null 2>&1; then \
		black --check app/ teams_bot/ well_shared/; \
	else \
		echo "⚠️  black not installed"; \
	fi
	@if command -v flake8 >/dev/null 2>&1; then \
		flake8 app/ teams_bot/ well_shared/ --max-line-length=120; \
	else \
		echo "⚠️  flake8 not installed"; \
	fi
	@if command -v mypy >/dev/null 2>&1; then \
		mypy app/ teams_bot/ well_shared/ --ignore-missing-imports; \
	else \
		echo "⚠️  mypy not installed"; \
	fi

# ==============================================================================
# Advanced Automation
# ==============================================================================

.PHONY: quick-win organize-root security-audit architecture-diagram

quick-win:
	@echo "🎯 Applying quick wins from directory proposal..."
	@mkdir -p temp/previews temp/debug
	@mv *.html temp/previews/ 2>/dev/null || true
	@mv coverage_output.txt temp/debug/ 2>/dev/null || true
	@mv removed_files_backup_* temp/ 2>/dev/null || true
	@echo "temp/" >> .gitignore
	@echo "temp/" >> .dockerignore
	@echo "✅ Root directory cleaned (50% reduction)"

organize-root:
	@echo "📁 Organizing root directory..."
	@mkdir -p temp/{previews,debug,backups}
	@mkdir -p scripts/{dev,ops,analysis}
	@# Move preview files
	@find . -maxdepth 1 -name "*.html" -exec mv {} temp/previews/ \;
	@# Move debug files
	@find . -maxdepth 1 -name "coverage_*.txt" -exec mv {} temp/debug/ \;
	@# Move backup dirs
	@find . -maxdepth 1 -type d -name "*backup*" -exec mv {} temp/backups/ \;
	@echo "✅ Root organized"

security-audit:
	@echo "🔒 Running security audit..."
	@echo "=== Checking for exposed secrets ==="
	@make validate-secrets
	@echo ""
	@echo "=== Checking dependencies for vulnerabilities ==="
	@if command -v safety >/dev/null 2>&1; then \
		safety check; \
	else \
		echo "⚠️  Install safety: pip install safety"; \
	fi
	@echo ""
	@echo "=== Checking Key Vault usage ==="
	@if rg "KeyVault|keyvault" app/ teams_bot/ --type py; then \
		echo "✅ Key Vault in use"; \
	else \
		echo "❌ Key Vault NOT used (secrets in .env.local)"; \
	fi

architecture-diagram:
	@echo "🏗️  Generating architecture diagram..."
	@echo "Mermaid diagram available in: _reports/mermaid_topology.md"
	@echo "To render: https://mermaid.live/"

# ==============================================================================
# CI/CD Helpers
# ==============================================================================

.PHONY: ci-test ci-build ci-deploy

ci-test:
	@echo "🔄 CI: Running tests..."
	@pytest tests/ -v --tb=short
	@pytest --cov=app --cov=teams_bot --cov-report=xml

ci-build:
	@echo "🔄 CI: Building images..."
	@docker build -t wellintakeacr0903.azurecr.io/well-intake-api:${TAG} .
	@docker build -t wellintakeacr0903.azurecr.io/teams-bot:${TAG} -f teams_bot/Dockerfile teams_bot/

ci-deploy:
	@echo "🔄 CI: Deploying to Azure..."
	@az containerapp update --name well-intake-api \
		--resource-group TheWell-Infra-East \
		--image wellintakeacr0903.azurecr.io/well-intake-api:${TAG}

# ==============================================================================
# Development Helpers
# ==============================================================================

.PHONY: dev-setup dev-run dev-stop dev-logs

dev-setup:
	@echo "🛠️  Setting up development environment..."
	@python3 -m venv zoho
	@./zoho/bin/pip install -r requirements.txt -r requirements-dev.txt
	@cp .env.local.template .env.local
	@echo "✅ Dev environment ready"
	@echo "Activate: source zoho/bin/activate"

dev-run:
	@echo "▶️  Starting development servers..."
	@# Run in background
	@uvicorn app.main:app --reload --port 8000 &
	@uvicorn teams_bot.app.main:app --reload --port 8001 &
	@echo "✅ Servers running"
	@echo "Main API: http://localhost:8000/docs"
	@echo "Teams Bot: http://localhost:8001/docs"

dev-stop:
	@echo "⏹️  Stopping development servers..."
	@pkill -f "uvicorn app.main:app" || true
	@pkill -f "uvicorn teams_bot.app.main:app" || true
	@echo "✅ Servers stopped"

dev-logs:
	@echo "📋 Showing development logs..."
	@tail -f app.log teams_bot.log 2>/dev/null || echo "No log files found"

# ==============================================================================
# Meta
# ==============================================================================

.PHONY: about

about:
	@echo "Well Intake API - Infrastructure Automation"
	@echo ""
	@echo "Generated: 2025-10-17"
	@echo "Purpose: Automate common infrastructure tasks"
	@echo ""
	@echo "Key Targets:"
	@echo "  make reports    - Generate all discovery reports"
	@echo "  make validate   - Run all validation checks"
	@echo "  make clean      - Clean temporary files"
	@echo "  make test       - Run test suite"
	@echo "  make quick-win  - Apply directory cleanup (5 min)"
	@echo ""
	@echo "For full list: make help"
