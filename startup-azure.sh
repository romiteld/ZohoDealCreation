#!/bin/bash
echo "Azure App Service Startup"
echo "========================="
cd /home/site/wwwroot

# Set SQLite for ChromaDB
export __import__hook__=pysqlite3
export CHROMA_SQLITE_IMPL=pysqlite3

# Simple startup without dependency checks
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 1 --worker-class uvicorn.workers.UvicornWorker app.main:app
