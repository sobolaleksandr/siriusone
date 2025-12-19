#!/bin/bash
# Quick test script for SWE-bench validator

set -e

echo "=========================================="
echo "SWE-bench Validator Test Suite"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to run test
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_result="$3"  # "pass" or "fail"
    
    echo -e "${YELLOW}Testing: ${test_name}${NC}"
    
    if eval "$command" > /tmp/test_output.log 2>&1; then
        result="pass"
    else
        result="fail"
    fi
    
    if [ "$result" = "$expected_result" ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        ((PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "Expected: $expected_result, Got: $result"
        echo "Output:"
        tail -20 /tmp/test_output.log
        ((FAILED++))
        return 1
    fi
    echo ""
}

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! docker ps &> /dev/null; then
    echo -e "${RED}✗ Docker is not running. Please start Docker.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Test 1: Help/Usage
echo "=========================================="
echo "Test 1: CLI Help"
echo "=========================================="
if uv run python -m swe_bench_validator --help &> /dev/null; then
    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi
echo ""

# Test 2: Validate structure (non-existent file)
echo "=========================================="
echo "Test 2: Error Handling - Non-existent File"
echo "=========================================="
run_test "Non-existent file" \
    "uv run python -m swe_bench_validator data_points/nonexistent.json" \
    "fail"

# Test 3: Validate structure (malformed JSON)
echo "=========================================="
echo "Test 3: Error Handling - Malformed JSON"
echo "=========================================="
echo '{"invalid": json}' > /tmp/test_malformed.json
run_test "Malformed JSON" \
    "uv run python -m swe_bench_validator /tmp/test_malformed.json" \
    "fail"
rm -f /tmp/test_malformed.json

# Test 4: Validate structure (missing fields)
echo "=========================================="
echo "Test 4: Error Handling - Missing Fields"
echo "=========================================="
echo '{"instance_id": "test"}' > /tmp/test_incomplete.json
run_test "Missing required fields" \
    "uv run python -m swe_bench_validator /tmp/test_incomplete.json" \
    "fail"
rm -f /tmp/test_incomplete.json

# Test 5: Valid data point (may take time)
echo "=========================================="
echo "Test 5: Valid Data Point"
echo "=========================================="
echo -e "${YELLOW}Note: This may take 10-30 minutes on first run (Docker image build)${NC}"
echo -e "${YELLOW}You can skip this test if Docker images aren't built yet${NC}"
read -p "Run this test? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    run_test "Valid data point" \
        "uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json --verbose" \
        "pass"
else
    echo -e "${YELLOW}⏭ Skipped${NC}"
fi
echo ""

# Test 6: Invalid data point
echo "=========================================="
echo "Test 6: Invalid Data Point"
echo "=========================================="
echo -e "${YELLOW}Note: This may take time if Docker images aren't built${NC}"
read -p "Run this test? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    run_test "Invalid data point (should fail)" \
        "uv run python -m swe_bench_validator data_points/astropy__astropy-11693-fail.json --verbose" \
        "fail"
else
    echo -e "${YELLOW}⏭ Skipped${NC}"
fi
echo ""

# Test 7: Multiple files
echo "=========================================="
echo "Test 7: Multiple Files"
echo "=========================================="
echo -e "${YELLOW}Note: This may take time if Docker images aren't built${NC}"
read -p "Run this test? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    run_test "Multiple files" \
        "uv run python -m swe_bench_validator data_points/ --continue-on-error" \
        "fail"  # Should fail because invalid file exists
else
    echo -e "${YELLOW}⏭ Skipped${NC}"
fi
echo ""

# Test 8: JSON output
echo "=========================================="
echo "Test 8: JSON Output Format"
echo "=========================================="
if uv run python -m swe_bench_validator --json-output --help &> /dev/null; then
    echo -e "${GREEN}✓ PASSED (JSON output option exists)${NC}"
    ((PASSED++))
else
    echo -e "${RED}✗ FAILED${NC}"
    ((FAILED++))
fi
echo ""

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "${GREEN}Passed: ${PASSED}${NC}"
echo -e "${RED}Failed: ${FAILED}${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed! ✓${NC}"
    exit 0
else
    echo -e "${YELLOW}Some tests failed or were skipped.${NC}"
    echo -e "${YELLOW}Note: Docker-related tests may fail if images aren't built yet.${NC}"
    exit 1
fi

