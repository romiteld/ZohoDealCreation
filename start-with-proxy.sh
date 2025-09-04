#!/bin/bash
# Start nginx in background
nginx -g 'daemon off;' &

# Start the FastAPI app on port 8001
export PORT=8001
uvicorn app.main:app --host 0.0.0.0 --port 8001
