#!/bin/bash

# ============================================
# Azure Infrastructure Test Runner
# ============================================
# Comprehensive test runner for migrated resources
# Usage: ./run_tests.sh [option]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f ".env.local" ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
    echo -e "${GREEN}✓ Loaded environment variables from .env.local${NC}"
else
    echo -e "${YELLOW}⚠ Warning: .env.local not found${NC}"
fi

# Function to print header
print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

# Function to run tests with category
run_category_tests() {
    local category="$1"
    local marker="$2"
    
    print_header "Running $category Tests"
    
    if [ -z "$marker" ]; then
        pytest tests/test_migrated_infrastructure.py -v --tb=short
    else
        pytest tests/test_migrated_infrastructure.py -v -m "$marker" --tb=short
    fi
}

# Main menu
show_menu() {
    print_header "Azure Infrastructure Test Runner"
    
    echo "Select test option:"
    echo ""
    echo "  1) Quick Health Check (curl-based)"
    echo "  2) Full Infrastructure Test (Python)"
    echo "  3) Container App Tests Only"
    echo "  4) Database Tests Only"
    echo "  5) Cache Tests Only"
    echo "  6) Storage Tests Only"
    echo "  7) Service Bus Tests Only"
    echo "  8) Critical Tests Only"
    echo "  9) Performance Tests"
    echo "  10) Generate Test Report"
    echo "  11) Install Test Dependencies"
    echo "  0) Exit"
    echo ""
}

# Function to install dependencies
install_dependencies() {
    print_header "Installing Test Dependencies"
    
    echo "Creating virtual environment..."
    python3 -m venv test_env
    source test_env/bin/activate
    
    echo "Installing requirements..."
    pip install --upgrade pip
    pip install -r tests/requirements-test.txt
    
    echo -e "${GREEN}✓ Dependencies installed successfully${NC}"
    echo -e "${YELLOW}Note: Activate virtual environment with: source test_env/bin/activate${NC}"
}

# Function to run quick health check
quick_health_check() {
    print_header "Quick Health Check"
    ./test_migration.sh "$API_KEY"
}

# Function to run full test suite
full_test_suite() {
    print_header "Full Infrastructure Test Suite"
    
    # Check if pytest is installed
    if ! command -v pytest &> /dev/null; then
        echo -e "${RED}pytest not found. Installing dependencies...${NC}"
        install_dependencies
        source test_env/bin/activate
    fi
    
    # Run all tests
    pytest tests/test_migrated_infrastructure.py -v --tb=short --html=test_report.html --self-contained-html
    
    echo ""
    echo -e "${GREEN}Test report generated: test_report.html${NC}"
}

# Function to generate comprehensive report
generate_report() {
    print_header "Generating Test Report"
    
    # Create reports directory
    mkdir -p reports
    
    # Run tests with coverage and reporting
    pytest tests/test_migrated_infrastructure.py \
        --cov=app \
        --cov-report=html:reports/coverage \
        --cov-report=term \
        --html=reports/test_results.html \
        --self-contained-html \
        --junit-xml=reports/junit.xml \
        -v
    
    echo ""
    echo -e "${GREEN}Reports generated:${NC}"
    echo "  - HTML Test Results: reports/test_results.html"
    echo "  - Coverage Report: reports/coverage/index.html"
    echo "  - JUnit XML: reports/junit.xml"
}

# Function to run performance tests
performance_tests() {
    print_header "Performance Tests"
    
    echo "Testing response times..."
    
    # Test health endpoint performance
    echo -e "${YELLOW}Health Endpoint Performance:${NC}"
    for i in {1..10}; do
        start_time=$(date +%s%N)
        curl -s -o /dev/null "$CONTAINER_APP_URL/health"
        end_time=$(date +%s%N)
        elapsed_ms=$(((end_time - start_time) / 1000000))
        echo "  Request $i: ${elapsed_ms}ms"
    done
    
    echo ""
    echo -e "${YELLOW}Concurrent Request Test:${NC}"
    echo "Sending 50 concurrent requests..."
    
    # Use curl with parallel processing
    seq 1 50 | xargs -P 10 -I {} curl -s -o /dev/null -w "Request {}: %{http_code} in %{time_total}s\n" "$CONTAINER_APP_URL/health"
}

# Parse command line arguments
if [ "$1" ]; then
    case $1 in
        quick)
            quick_health_check
            ;;
        full)
            full_test_suite
            ;;
        container)
            run_category_tests "Container App" "container_app"
            ;;
        db|database)
            run_category_tests "Database" "postgresql"
            ;;
        cache|redis)
            run_category_tests "Cache" "redis"
            ;;
        storage)
            run_category_tests "Storage" "storage"
            ;;
        servicebus|bus)
            run_category_tests "Service Bus" "service_bus"
            ;;
        critical)
            run_category_tests "Critical" "critical"
            ;;
        performance|perf)
            performance_tests
            ;;
        report)
            generate_report
            ;;
        install)
            install_dependencies
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Usage: ./run_tests.sh [quick|full|container|db|cache|storage|servicebus|critical|performance|report|install]"
            exit 1
            ;;
    esac
else
    # Interactive mode
    while true; do
        show_menu
        read -p "Enter choice [0-11]: " choice
        
        case $choice in
            1)
                quick_health_check
                ;;
            2)
                full_test_suite
                ;;
            3)
                run_category_tests "Container App" "container_app"
                ;;
            4)
                run_category_tests "Database" "postgresql"
                ;;
            5)
                run_category_tests "Cache" "redis"
                ;;
            6)
                run_category_tests "Storage" "storage"
                ;;
            7)
                run_category_tests "Service Bus" "service_bus"
                ;;
            8)
                run_category_tests "Critical" "critical"
                ;;
            9)
                performance_tests
                ;;
            10)
                generate_report
                ;;
            11)
                install_dependencies
                ;;
            0)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
fi