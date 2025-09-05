#!/bin/bash
# Script to inject API key into config.js during deployment

# Load environment variables from .env.local
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
fi

# Replace placeholder with actual API key
sed -i "s/{{API_KEY_PLACEHOLDER}}/$API_KEY/g" addin/config.js

echo "API key injected into config.js"