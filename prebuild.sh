#!/bin/bash
# Azure App Service Pre-Build Script
# This script runs before the main build process

echo "=========================================="
echo "Starting Pre-Build Process..."
echo "Python Version: $(python --version)"
echo "Pip Version: $(pip --version)"
echo "=========================================="

# Upgrade pip, setuptools, and wheel to latest versions
echo "Upgrading pip, setuptools, and wheel..."
python -m pip install --upgrade pip setuptools wheel

# Install build dependencies first
echo "Installing build dependencies..."
python -m pip install --no-cache-dir "Cython>=0.29.0"
python -m pip install --no-cache-dir "numpy>=1.26.0"

# Clean any existing installations that might cause conflicts
echo "Cleaning potentially conflicting packages..."
pip uninstall -y langchain langchain-core langchain-community 2>/dev/null || true

# Install critical dependencies with specific order to avoid conflicts
echo "Installing core dependencies in proper order..."
python -m pip install --no-cache-dir "pydantic>=2.0.0,<3.0.0"
python -m pip install --no-cache-dir "langchain-core==0.1.0"
python -m pip install --no-cache-dir "langchain==0.1.0"
python -m pip install --no-cache-dir "langchain-community==0.0.10"
python -m pip install --no-cache-dir "langchain-openai==0.0.5"

# Install OpenAI with the correct version
echo "Installing OpenAI SDK..."
python -m pip install --no-cache-dir "openai>=1.68.0"

# Handle SQLite for ChromaDB on Azure
echo "Setting up SQLite for ChromaDB..."
python -m pip install --no-cache-dir pysqlite3-binary

echo "=========================================="
echo "Pre-Build Process Completed!"
echo "=========================================="