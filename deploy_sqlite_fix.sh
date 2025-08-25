#!/bin/bash

echo "========================================="
echo "Azure Deployment with SQLite Fix"
echo "========================================="

# Set variables
RESOURCE_GROUP="TheWell-App-East"
APP_NAME="well-intake-api"

echo ""
echo "1. Setting Azure App Service startup command..."
az webapp config set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --startup-file "./startup_robust.sh"

echo ""
echo "2. Setting app settings for build..."
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --settings \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true \
    ENABLE_ORYX_BUILD=true \
    ORYX_BUILD_COMMANDS="pip install pysqlite3-binary==0.5.4" \
    PRE_BUILD_COMMAND="pip install pysqlite3-binary==0.5.4" \
    POST_BUILD_COMMAND="pip install pysqlite3-binary==0.5.4 && python -c 'import pysqlite3; print(f\"pysqlite3 version: {pysqlite3.sqlite_version}\")'"

echo ""
echo "3. Creating deployment package..."
# Clean up old files
rm -f deploy.zip

# Create the deployment package
echo "Creating deployment ZIP..."
zip -r deploy.zip . \
    -x "*.git*" \
    -x "zoho/*" \
    -x "__pycache__/*" \
    -x "*.pyc" \
    -x ".env*" \
    -x "test_*.py" \
    -x "deploy.zip" \
    -x "server.log" \
    -x "*.log"

echo ""
echo "4. Deploying to Azure..."
az webapp deploy \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --src-path deploy.zip \
    --type zip \
    --async false

echo ""
echo "5. Restarting app..."
az webapp restart \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME

echo ""
echo "6. Checking logs..."
echo "Waiting 10 seconds for app to start..."
sleep 10

echo ""
echo "Recent logs:"
az webapp log tail \
    --resource-group $RESOURCE_GROUP \
    --name $APP_NAME \
    --provider http \
    --max-log-size 2048 &

# Let it run for 30 seconds then stop
sleep 30
kill $!

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="
echo ""
echo "Check the app at: https://$APP_NAME.azurewebsites.net/health"
echo ""
echo "To monitor logs:"
echo "  az webapp log tail --resource-group $RESOURCE_GROUP --name $APP_NAME"
echo ""
echo "To check SQLite version:"
echo "  curl https://$APP_NAME.azurewebsites.net/health | python -m json.tool"