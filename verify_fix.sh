#!/bin/bash
# Verify the fix by installing in a fresh venv

echo "Creating test virtual environment..."
python -m venv test_fix_venv

echo "Activating virtual environment..."
source test_fix_venv/bin/activate 2>/dev/null || test_fix_venv\Scripts\activate

echo "Installing updated requirements..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Testing imports..."
python -c "
from crewai import Agent, Task, Crew
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
print('✅ All imports successful!')
"

echo "Cleaning up..."
deactivate 2>/dev/null || true
rm -rf test_fix_venv

echo "✅ Verification complete!"
