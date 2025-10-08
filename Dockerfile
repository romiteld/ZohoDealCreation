# Multi-stage build for optimized production image
# Build stage
FROM python:3.11-slim AS builder

# Set working directory
WORKDIR /app

# Install build dependencies (headers + shared libs for premailer/lxml)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --user --no-cache-dir --upgrade pip && \
    pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user first
RUN useradd -m -u 1000 appuser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/appuser/.local/bin:$PATH

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    curl \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder to appuser's home
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser addin/ ./addin/
COPY --chown=appuser:appuser scripts/ ./scripts/
COPY --chown=appuser:appuser migrations/ ./migrations/
COPY --chown=appuser:appuser startup.sh ./startup.sh

# Create static directory (may not exist in repo due to .gitignore)
RUN mkdir -p ./static/icons && chown -R appuser:appuser ./static

# Create logs directory and make startup script executable
RUN mkdir -p /app/logs && \
    chmod +x /app/startup.sh && \
    chown -R appuser:appuser /app && \
    ls -la /app/startup.sh && \
    cat /app/startup.sh

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check using curl (more efficient than Python import)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run with startup script for environment variable capture
CMD ["bash", "/app/startup.sh"]