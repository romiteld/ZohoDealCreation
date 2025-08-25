#!/bin/bash
# Azure App Service Deployment Script
# Handles staged dependency installation

echo "========================================="
echo "Azure App Service Deployment Starting..."
echo "========================================="

# Set Python path
export PYTHONPATH="${PYTHONPATH}:/home/site/wwwroot"

# Function to install requirements with retry
install_requirements() {
    local req_file=$1
    local max_attempts=3
    local attempt=1
    
    echo "Installing from $req_file..."
    
    while [ $attempt -le $max_attempts ]; do
        echo "Attempt $attempt of $max_attempts..."
        
        if pip install --no-cache-dir --upgrade -r "$req_file"; then
            echo "✓ Successfully installed $req_file"
            return 0
        else
            echo "✗ Failed attempt $attempt"
            attempt=$((attempt + 1))
            
            if [ $attempt -le $max_attempts ]; then
                echo "Retrying in 5 seconds..."
                sleep 5
            fi
        fi
    done
    
    echo "ERROR: Failed to install $req_file after $max_attempts attempts"
    return 1
}

# Upgrade pip first
echo "Upgrading pip..."
python -m pip install --upgrade pip setuptools wheel

# Install SQLite binary for ChromaDB compatibility
echo "Installing SQLite binary..."
pip install pysqlite3-binary

# Override sqlite3 with pysqlite3
echo "Setting up SQLite override..."
cat > /home/site/wwwroot/sqlite_override.py << 'EOF'
import sys
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
except ImportError:
    pass
EOF

# Stage 1: Core dependencies
echo ""
echo "Stage 1: Installing core dependencies..."
install_requirements "requirements_stage1.txt"

# Stage 2: Database and Azure
echo ""
echo "Stage 2: Installing database and Azure dependencies..."
install_requirements "requirements_stage2.txt"

# Stage 3: AI/ML dependencies
echo ""
echo "Stage 3: Installing AI/ML dependencies..."
install_requirements "requirements_stage3.txt"

# Stage 4: CrewAI and remaining
echo ""
echo "Stage 4: Installing CrewAI and remaining dependencies..."
install_requirements "requirements_stage4.txt"

# Verify installation
echo ""
echo "Verifying installation..."
python verify_imports.py

if [ $? -eq 0 ]; then
    echo "✓ All dependencies installed successfully"
else
    echo "✗ Some dependencies failed verification"
    echo "Attempting fallback installation..."
    pip install --no-cache-dir -r requirements.txt
fi

echo ""
echo "========================================="
echo "Deployment Script Completed"
echo "========================================="
