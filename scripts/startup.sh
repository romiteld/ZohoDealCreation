#!/bin/bash
echo "=== Azure App Service Startup Script (Cosmos DB Mode) ==="
echo "=== No SQLite/Chroma dependencies! ==="

# Install base requirements
pip install --no-cache-dir -r requirements.txt

# No need for pysqlite3-binary or SQLite patches!
echo "=== Using Cosmos DB for PostgreSQL with pgvector ==="

echo "=== Starting application with Gunicorn ==="
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app
