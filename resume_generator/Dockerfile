# Well Resume Generator - Dockerfile
# Use official Playwright Python image with all dependencies pre-installed

FROM mcr.microsoft.com/playwright/python:v1.48.0-noble

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for PDF generation)
# Note: System deps already included in base image
RUN playwright install chromium

# Copy application code
COPY app/ ./app/

# Create static directory if it doesn't exist
RUN mkdir -p /app/app/static /app/app/templates

# Copy logo CSS file
COPY logo-css.txt ./logo-css.txt

# Copy static assets
COPY app/static/ ./app/static/
COPY app/templates/ ./app/templates/

# Expose port 8002
EXPOSE 8002

# Health check (using httpx which is already in requirements)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8002/health', timeout=5)"

# Run the application with increased timeout (60s for PDF generation)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--timeout-keep-alive", "75"]
