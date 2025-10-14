# Teams Bot Service - Azure Container Apps deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy well_shared library first
COPY well_shared/ /tmp/well_shared/
RUN pip install --no-cache-dir -e /tmp/well_shared/

# Copy and install main app requirements first (includes langgraph, etc.)
COPY requirements.txt ./requirements-main.txt
RUN pip install --no-cache-dir -r requirements-main.txt

# Copy and install Teams Bot specific requirements
COPY teams_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Teams Bot application code
COPY teams_bot/app/ ./app/

# Copy shared routes and utilities from main app
# These will be moved to well_shared in Phase 2-3
# Note: teams_bot/app/api/teams/__init__.py contains import shim that re-exports
COPY app/api/ ./app/api/
COPY app/jobs/ ./app/jobs/
COPY app/templates/ ./app/templates/
COPY app/bandits/ ./app/bandits/
COPY app/config/ ./app/config/
COPY app/utils/ ./app/utils/
COPY app/integrations.py ./app/
COPY app/business_rules.py ./app/
COPY app/powerbi_integration.py ./app/
COPY app/monitoring.py ./app/

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
