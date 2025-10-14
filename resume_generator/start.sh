#!/bin/bash

# Well Resume Generator Startup Script

echo "🚀 Starting Well Resume Generator API..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies if needed
if [ ! -f "venv/.installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt

    # Install Playwright browsers
    echo "🌐 Installing Playwright browsers..."
    playwright install chromium

    touch venv/.installed
fi

# Check for .env.local file
if [ ! -f ".env.local" ]; then
    echo "⚠️  Warning: .env.local not found"
    echo "📝 Creating from template..."
    cp .env.template .env.local
    echo ""
    echo "⚠️  IMPORTANT: Edit .env.local with your Azure credentials"
    echo "You can copy values from: ../../../.env.local"
    echo ""
    read -p "Press Enter to continue when ready..."
fi

# Start the API
echo "✅ Starting API on port 8002..."
echo "📖 API docs available at: http://localhost:8002/docs"
echo ""

uvicorn app.main:app --reload --port 8002 --host 0.0.0.0
