#!/bin/bash

# Azure Cosmos DB for PostgreSQL Setup Script
# Run this script to verify your database connection and setup

echo "🐘 Azure Cosmos DB for PostgreSQL Setup Verification"
echo "=================================================="

# Check if environment variables are set
if [ -z "$POSTGRES_CONNECTION_STRING" ]; then
    echo "❌ POSTGRES_CONNECTION_STRING not set"
    echo "Please add this to your .env.local:"
    echo "POSTGRES_CONNECTION_STRING=postgresql://citus:your-password@c-well-intake-db.kaj3v6jxajtw66.postgres.cosmos.azure.com:5432/citus?sslmode=require"
    exit 1
fi

# Test connection using psql (if available)
echo "🔗 Testing PostgreSQL connection..."
if command -v psql &> /dev/null; then
    psql "$POSTGRES_CONNECTION_STRING" -c "SELECT version();" &> /dev/null
    if [ $? -eq 0 ]; then
        echo "✅ PostgreSQL connection successful"
    else
        echo "❌ PostgreSQL connection failed"
        echo "Please verify your connection string and credentials"
        exit 1
    fi
else
    echo "⚠️  psql not found, skipping connection test"
    echo "Install PostgreSQL client to test connection: apt-get install postgresql-client"
fi

# Check if Python dependencies are installed
echo "🐍 Checking Python dependencies..."
python3 -c "import asyncpg; print('✅ asyncpg installed')" 2>/dev/null || echo "❌ asyncpg not installed - run: pip install asyncpg"
python3 -c "import fastapi; print('✅ fastapi installed')" 2>/dev/null || echo "❌ fastapi not installed - run: pip install -r requirements.txt"

# Check Azure CLI commands for your cluster
echo "☁️  Azure CLI commands for your cluster:"
echo "Check cluster status:"
echo "az cosmosdb postgres cluster show --cluster-name well-intake-db --resource-group TheWell-Infra-East --query state"
echo ""
echo "Get connection strings:"
echo "az cosmosdb postgres cluster show-connection-strings --cluster-name well-intake-db --resource-group TheWell-Infra-East"
echo ""
echo "Monitor performance:"
echo "az monitor metrics list --resource /subscriptions/\$(az account show --query id -o tsv)/resourceGroups/TheWell-Infra-East/providers/Microsoft.DBforPostgreSQL/serverGroupsv2/well-intake-db --metric-names cpu_percent memory_percent --output table"

echo ""
echo "🚀 Next Steps:"
echo "1. Update your .env.local with the correct POSTGRES_CONNECTION_STRING"
echo "2. Install dependencies: pip install -r requirements.txt"  
echo "3. Start the API: uvicorn app.main:app --reload"
echo "4. Tables will be auto-created on first startup"
echo "5. Test with: curl http://localhost:8000/health"

echo ""
echo "📊 Your PostgreSQL cluster will provide:"
echo "• Email deduplication and processing history"
echo "• Company enrichment caching"
echo "• Zoho record mapping for faster lookups" 
echo "• Vector similarity search capabilities"
echo "• Analytics and reporting endpoints"
