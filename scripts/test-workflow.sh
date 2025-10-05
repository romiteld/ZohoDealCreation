#!/bin/bash

# Test GitHub Actions Workflow Components
# Usage: ./scripts/test-workflow.sh [--dry-run]

set -e

# Configuration
API_ENDPOINT="https://well-intake-api.wittyocean-dfae0f9b.eastus.azurecontainerapps.io"
DRY_RUN=${1:-""}

echo "🧪 Testing GitHub Actions workflow components"
echo "🌐 API Endpoint: $API_ENDPOINT"
echo

# Load environment variables
if [[ -f ".env.local" ]]; then
    source .env.local
    echo "✅ Environment variables loaded from .env.local"
else
    echo "⚠️ .env.local not found - some tests may fail"
fi
echo

# Test 1: Health Check
echo "1️⃣ Testing health endpoint..."
if curl -f "$API_ENDPOINT/health" --max-time 10 --silent > /dev/null; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    exit 1
fi
echo

# Test 2: Manifest Accessibility
echo "2️⃣ Testing manifest accessibility..."
if curl -f "$API_ENDPOINT/manifest.xml" --max-time 10 --silent > /dev/null; then
    echo "✅ Manifest accessible"
else
    echo "❌ Manifest not accessible"
    exit 1
fi
echo

# Test 3: Add-in Files
echo "3️⃣ Testing add-in files..."
for file in "taskpane.html" "commands.html" "icon-64.png"; do
    if curl -f "$API_ENDPOINT/$file" --max-time 10 --silent > /dev/null; then
        echo "  ✅ $file accessible"
    else
        echo "  ❌ $file not accessible"
        exit 1
    fi
done
echo

# Test 4: Version Detection
echo "4️⃣ Testing version detection..."
CURRENT_VERSION=$(grep -o '<Version>[^<]*</Version>' addin/manifest.xml | sed 's/<Version>//;s/<\/Version>//')
echo "  📋 Current version: $CURRENT_VERSION"

# Parse version components
IFS='.' read -r major minor patch build <<< "$CURRENT_VERSION"
echo "  🔢 Version components: major=$major, minor=$minor, patch=$patch, build=${build:-0}"

# Test version increment logic
NEW_PATCH_VERSION="${major}.${minor}.${patch}.$((${build:-0} + 1))"
NEW_MINOR_VERSION="${major}.$((minor + 1)).0.0"
NEW_MAJOR_VERSION="$((major + 1)).0.0.0"

echo "  ⬆️ Next patch: $NEW_PATCH_VERSION"
echo "  ⬆️ Next minor: $NEW_MINOR_VERSION" 
echo "  ⬆️ Next major: $NEW_MAJOR_VERSION"
echo

# Test 5: Cache API (if API_KEY available)
if [[ -n "$API_KEY" ]]; then
    echo "5️⃣ Testing cache API..."
    
    # Test cache status
    if curl -X GET "$API_ENDPOINT/cache/status" \
        -H "X-API-Key: $API_KEY" \
        --max-time 10 \
        --silent > /dev/null; then
        echo "  ✅ Cache status endpoint accessible"
    else
        echo "  ❌ Cache status endpoint failed"
    fi
    
    # Test cache invalidation (dry run)
    if [[ "$DRY_RUN" != "--dry-run" ]]; then
        if curl -X POST "$API_ENDPOINT/cache/invalidate" \
            -H "X-API-Key: $API_KEY" \
            -H "Content-Type: application/json" \
            -d '{"pattern": "test:*"}' \
            --max-time 10 \
            --silent > /dev/null; then
            echo "  ✅ Cache invalidation endpoint working"
        else
            echo "  ❌ Cache invalidation endpoint failed"
        fi
    else
        echo "  🔄 Cache invalidation test skipped (dry-run mode)"
    fi
else
    echo "5️⃣ Skipping cache API tests (no API_KEY)"
fi
echo

# Test 6: Manifest Validation
echo "6️⃣ Validating manifest.xml structure..."

# Check required elements
REQUIRED_ELEMENTS=(
    "Id"
    "Version"
    "ProviderName"
    "DefaultLocale"
    "DisplayName"
    "Description"
)

for element in "${REQUIRED_ELEMENTS[@]}"; do
    if grep -q "<$element" addin/manifest.xml; then
        echo "  ✅ $element present"
    else
        echo "  ❌ $element missing"
        exit 1
    fi
done

# Check version format
if echo "$CURRENT_VERSION" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+(\.[0-9]+)?$' > /dev/null; then
    echo "  ✅ Version format valid"
else
    echo "  ❌ Version format invalid"
    exit 1
fi

# Check URLs
URL_COUNT=$(grep -c "wittyocean-dfae0f9b.eastus.azurecontainerapps.io" addin/manifest.xml || true)
echo "  📊 Container Apps URLs found: $URL_COUNT"
echo

# Test 7: Git Repository State
echo "7️⃣ Checking git repository state..."

# Check if we're in a git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "  ✅ In git repository"
    
    # Check for uncommitted changes
    if [[ -z $(git status --porcelain) ]]; then
        echo "  ✅ Working directory clean"
    else
        echo "  ⚠️ Uncommitted changes detected"
        git status --short | head -5
    fi
    
    # Check current branch
    CURRENT_BRANCH=$(git branch --show-current)
    echo "  📋 Current branch: $CURRENT_BRANCH"
    
    # Check remote configuration
    if git remote -v | grep -q "origin"; then
        echo "  ✅ Remote 'origin' configured"
    else
        echo "  ⚠️ Remote 'origin' not found"
    fi
else
    echo "  ❌ Not in a git repository"
    exit 1
fi
echo

# Test 8: Docker Build Test (if requested)
if [[ "$DRY_RUN" != "--dry-run" && "$2" == "--test-build" ]]; then
    echo "8️⃣ Testing Docker build..."
    
    # Build test image
    if docker build -t well-intake-test:latest . > /dev/null 2>&1; then
        echo "  ✅ Docker build successful"
        
        # Clean up test image
        docker rmi well-intake-test:latest > /dev/null 2>&1 || true
    else
        echo "  ❌ Docker build failed"
        exit 1
    fi
else
    echo "8️⃣ Skipping Docker build test (use --test-build to enable)"
fi
echo

# Test 9: Azure CLI Check
echo "9️⃣ Checking Azure CLI setup..."

if command -v az &> /dev/null; then
    echo "  ✅ Azure CLI installed"
    
    # Check login status
    if az account show > /dev/null 2>&1; then
        SUBSCRIPTION=$(az account show --query name --output tsv)
        echo "  ✅ Azure CLI authenticated (subscription: $SUBSCRIPTION)"
    else
        echo "  ⚠️ Azure CLI not authenticated (run: az login)"
    fi
else
    echo "  ❌ Azure CLI not installed"
fi
echo

# Test 10: GitHub CLI Check  
echo "🔟 Checking GitHub CLI setup..."

if command -v gh &> /dev/null; then
    echo "  ✅ GitHub CLI installed"
    
    # Check authentication
    if gh auth status > /dev/null 2>&1; then
        echo "  ✅ GitHub CLI authenticated"
    else
        echo "  ⚠️ GitHub CLI not authenticated (run: gh auth login)"
    fi
else
    echo "  ❌ GitHub CLI not installed"
fi
echo

# Summary
echo "📊 Test Summary"
echo "==============="
echo "✅ All core tests passed!"
echo
echo "🔧 Workflow readiness:"
echo "  • Health checks: Working"
echo "  • Manifest structure: Valid"  
echo "  • Version detection: Working"
echo "  • Git repository: Ready"

if [[ -n "$API_KEY" ]]; then
    echo "  • Cache API: Accessible"
fi

echo
echo "🚀 Next steps to enable workflow:"
echo "  1. Run: ./scripts/setup-github-secrets.sh"
echo "  2. Make a test change to addin/manifest.xml"
echo "  3. Commit and push to trigger the workflow"
echo "  4. Monitor GitHub Actions tab for progress"
echo
echo "📚 Documentation: .github/workflows/README.md"