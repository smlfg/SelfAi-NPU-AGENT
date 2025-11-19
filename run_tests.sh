#!/bin/bash
# ==============================================================================
# SelfAI NPU Agent - Test Suite Runner
# ==============================================================================
#
# Quick script to run the test suite with common configurations
#
# Usage:
#   ./run_tests.sh                 # Run all tests
#   ./run_tests.sh --coverage      # Run with coverage report
#   ./run_tests.sh --fast          # Run only fast tests
#   ./run_tests.sh --help          # Show help
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

show_help() {
    cat << EOF
SelfAI NPU Agent Test Suite Runner

Usage: ./run_tests.sh [OPTIONS]

Options:
    (none)          Run all tests with standard configuration
    --coverage      Run tests with coverage report
    --html          Run tests and generate HTML coverage report
    --fast          Run only fast tests (skip slow/integration)
    --verbose       Run tests with verbose output
    --markers       Show available test markers
    --failed        Re-run only failed tests from last run
    --debug         Run tests with debugging output
    --parallel      Run tests in parallel (faster)
    --help          Show this help message

Examples:
    ./run_tests.sh                      # Standard run
    ./run_tests.sh --coverage           # With coverage
    ./run_tests.sh --fast --parallel    # Fast parallel run
    ./run_tests.sh --failed --verbose   # Debug failures

For more options, run: pytest --help
EOF
}

check_dependencies() {
    print_header "Checking Dependencies"

    # Check if pytest is installed
    if ! python -m pytest --version &> /dev/null; then
        print_error "pytest is not installed"
        print_info "Installing test dependencies..."
        pip install -r requirements-test.txt
    else
        print_success "pytest is installed"
    fi

    # Check if main dependencies are installed
    if ! python -c "import yaml" &> /dev/null; then
        print_warning "Main dependencies not installed"
        print_info "Installing main dependencies..."
        pip install -r requirements.txt
    fi

    print_success "All dependencies ready"
    echo ""
}

run_standard_tests() {
    print_header "Running All Tests"
    python -m pytest tests/
}

run_with_coverage() {
    print_header "Running Tests with Coverage"
    python -m pytest \
        --cov=selfai \
        --cov=config_loader \
        --cov-report=term-missing \
        tests/
}

run_with_html_coverage() {
    print_header "Running Tests with HTML Coverage Report"
    python -m pytest \
        --cov=selfai \
        --cov=config_loader \
        --cov-report=html \
        --cov-report=term \
        tests/

    if [ -d "htmlcov" ]; then
        print_success "HTML coverage report generated in htmlcov/"
        print_info "Open htmlcov/index.html in your browser"

        # Try to open in browser (platform-specific)
        if command -v xdg-open &> /dev/null; then
            xdg-open htmlcov/index.html &
        elif command -v open &> /dev/null; then
            open htmlcov/index.html &
        fi
    fi
}

run_fast_tests() {
    print_header "Running Fast Tests Only"
    python -m pytest -m "not slow" tests/
}

run_verbose() {
    print_header "Running Tests (Verbose)"
    python -m pytest -vv tests/
}

show_markers() {
    print_header "Available Test Markers"
    python -m pytest --markers
}

run_failed_only() {
    print_header "Re-running Failed Tests"
    python -m pytest --lf -v tests/
}

run_debug() {
    print_header "Running Tests (Debug Mode)"
    python -m pytest -vv -s --log-cli-level=DEBUG tests/
}

run_parallel() {
    print_header "Running Tests in Parallel"

    # Check if pytest-xdist is installed
    if ! python -c "import xdist" &> /dev/null; then
        print_warning "pytest-xdist not installed"
        print_info "Installing pytest-xdist for parallel execution..."
        pip install pytest-xdist
    fi

    python -m pytest -n auto tests/
}

# Main script
main() {
    # Parse arguments
    case "${1:-}" in
        --help|-h)
            show_help
            exit 0
            ;;
        --coverage)
            check_dependencies
            run_with_coverage
            ;;
        --html)
            check_dependencies
            run_with_html_coverage
            ;;
        --fast)
            check_dependencies
            run_fast_tests
            ;;
        --verbose|-v)
            check_dependencies
            run_verbose
            ;;
        --markers)
            check_dependencies
            show_markers
            ;;
        --failed)
            check_dependencies
            run_failed_only
            ;;
        --debug)
            check_dependencies
            run_debug
            ;;
        --parallel)
            check_dependencies
            run_parallel
            ;;
        "")
            check_dependencies
            run_standard_tests
            ;;
        *)
            print_error "Unknown option: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac

    # Show summary
    echo ""
    print_header "Test Summary"
    print_info "To see detailed results, scroll up or check test_output.log"
    print_info "For coverage report, run: ./run_tests.sh --html"
    echo ""
}

# Run main function
main "$@"
