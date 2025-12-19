# Testing Guide for SWE-bench Data Point Validator

This guide explains how to test your validator implementation.

## Prerequisites

1. **Docker must be running**:
   ```bash
   docker ps  # Should not error
   ```

2. **Dependencies installed**:
   ```bash
   uv sync
   ```

3. **Note**: First run will build Docker images (10-30 minutes). Subsequent runs will be faster.

## Local Testing

### 1. Test with Valid Data Point

Test with the provided valid data point:

```bash
uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json --verbose
```

**Expected Result**: 
- ✅ Should pass validation (all tests pass)
- ⚠️ First run: May take 10-30 minutes to build Docker images
- ⚠️ First run: May show Docker build messages (this is normal)

**If it fails**:
- Check Docker is running: `docker ps`
- Check logs: `logs/run_evaluation/*/run_instance.log`
- Ensure sufficient disk space (images can be several GB)

### 2. Test with Invalid Data Point

Test with the provided invalid data point:

```bash
uv run python -m swe_bench_validator data_points/astropy__astropy-11693-fail.json --verbose
```

**Expected Result**:
- ❌ Should fail validation
- Should show clear error messages about which tests failed
- Should explain why validation failed

**Note**: The invalid data point uses the same `instance_id` as the valid one (`astropy__astropy-11693`) but with a broken patch. This is the correct approach - SWE-bench requires the instance to exist in the dataset, so invalid patches should use real instance IDs with broken patches.

### 3. Test Multiple Files

Test validation of multiple files:

```bash
uv run python -m swe_bench_validator data_points/ --verbose
```

**Expected Result**:
- Valid file should pass
- Invalid file should fail
- Summary table showing results for both

### 4. Test Error Handling

#### Test with non-existent file:
```bash
uv run python -m swe_bench_validator data_points/nonexistent.json
```

**Expected**: Clear error message about file not found

#### Test with malformed JSON:
```bash
echo '{"invalid": json}' > /tmp/test.json
uv run python -m swe_bench_validator /tmp/test.json
```

**Expected**: Clear error message about invalid JSON

#### Test with missing required fields:
```bash
echo '{"instance_id": "test"}' > /tmp/incomplete.json
uv run python -m swe_bench_validator /tmp/incomplete.json
```

**Expected**: Clear error message listing missing fields

### 5. Test CLI Options

```bash
# Test with custom timeout
uv run python -m swe_bench_validator --timeout 1200 data_points/astropy__astropy-11693.json

# Test JSON output
uv run python -m swe_bench_validator --json-output data_points/astropy__astropy-11693.json

# Test continue on error
uv run python -m swe_bench_validator --continue-on-error data_points/
```

## GitHub Actions Testing

### 1. Test Workflow Locally (Using act)

If you have `act` installed, you can test the workflow locally:

```bash
# Install act (if not installed)
# See: https://github.com/nektos/act

# Test the workflow
act pull_request -W .github/workflows/validate-datapoints.yml
```

### 2. Test on GitHub

#### Step 1: Push to GitHub

```bash
git add .
git commit -m "Add SWE-bench validator implementation"
git push origin main
```

#### Step 2: Create Test PR #1 - Valid Data Point

1. Create a new branch:
   ```bash
   git checkout -b test-valid-datapoint
   ```

2. Copy the valid data point (if not already committed):
   ```bash
   cp data_points/astropy__astropy-11693.json data_points/test_valid.json
   git add data_points/test_valid.json
   git commit -m "Add valid test data point"
   git push origin test-valid-datapoint
   ```

3. Create a Pull Request on GitHub

4. **Expected Result**:
   - ✅ GitHub Action should trigger
   - ✅ Should show green status check
   - ✅ Validation should pass

#### Step 3: Create Test PR #2 - Invalid Data Point

1. Create another branch:
   ```bash
   git checkout -b test-invalid-datapoint
   ```

2. Copy the invalid data point:
   ```bash
   cp data_points/astropy__astropy-11693-fail.json data_points/test_invalid.json
   git add data_points/test_invalid.json
   git commit -m "Add invalid test data point"
   git push origin test-invalid-datapoint
   ```

3. Create a Pull Request on GitHub

4. **Expected Result**:
   - ✅ GitHub Action should trigger
   - ❌ Should show red status check
   - ❌ Should show clear error messages explaining why validation failed

### 3. Verify GitHub Action Behavior

Check that the workflow:
- ✅ Only runs on changes to `data_points/**` files
- ✅ Only validates changed files (not all files)
- ✅ Provides detailed error messages in the workflow logs
- ✅ Reports results as status checks

## Verification Checklist

### Validator Functionality

- [ ] Validates valid data points successfully
- [ ] Rejects invalid data points with clear errors
- [ ] Handles structural errors (malformed JSON, missing fields)
- [ ] Handles execution errors (Docker failures, test failures)
- [ ] Provides detailed error messages
- [ ] Handles timeouts appropriately
- [ ] Works with single files
- [ ] Works with directories
- [ ] CLI options work correctly

### GitHub Action

- [ ] Triggers on pushes to `data_points/**`
- [ ] Triggers on PRs affecting `data_points/**`
- [ ] Only validates changed files
- [ ] Provides clear status check messages
- [ ] Shows detailed logs for failures
- [ ] Doesn't run on unrelated file changes

### Documentation

- [ ] README.md has setup instructions
- [ ] README.md has usage examples
- [ ] README.md has troubleshooting section
- [ ] Docker architecture documentation is complete
- [ ] Code is well-commented

## Troubleshooting Tests

### Docker Issues

If Docker-related errors occur:

1. **Check Docker is running**:
   ```bash
   docker ps
   ```

2. **Check Docker permissions**:
   ```bash
   docker run hello-world  # Should work without sudo
   ```

3. **Check disk space**:
   ```bash
   df -h
   docker system df  # Check Docker disk usage
   ```

4. **Clean up old images** (if needed):
   ```bash
   docker system prune -a  # WARNING: Removes all unused images
   ```

### Image Build Issues

If Docker images fail to build:

1. **Check logs**:
   ```bash
   cat logs/run_evaluation/*/run_instance.log
   ```

2. **First run takes time**: Building images can take 10-30 minutes

3. **Network issues**: Ensure you have internet access for downloading base images

4. **Memory issues**: Ensure Docker has enough memory allocated

### Test Execution Issues

If tests show "UNKNOWN" status:

- This usually means the Docker container didn't run successfully
- Check `run_instance.log` for Docker build/execution errors
- Ensure Docker images were built successfully
- Check that the patch applies correctly

## Quick Test Script

Create a simple test script:

```bash
#!/bin/bash
# quick_test.sh

set -e

echo "=== Testing Validator ==="

# Test 1: Valid data point
echo "Test 1: Valid data point"
uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json || echo "⚠️  Test 1 failed (may be expected if Docker images not built)"

# Test 2: Invalid data point  
echo "Test 2: Invalid data point"
uv run python -m swe_bench_validator data_points/astropy__astropy-11693-fail.json || echo "✅ Test 2 passed (should fail)"

# Test 3: Non-existent file
echo "Test 3: Error handling - non-existent file"
uv run python -m swe_bench_validator data_points/nonexistent.json 2>&1 | grep -q "not found" && echo "✅ Test 3 passed" || echo "❌ Test 3 failed"

echo "=== Tests Complete ==="
```

Run it:
```bash
chmod +x quick_test.sh
./quick_test.sh
```

## Expected Test Results Summary

| Test Case | Expected Result | Notes |
|-----------|----------------|-------|
| Valid data point | ✅ PASS | May take time on first run |
| Invalid data point | ❌ FAIL with clear errors | Should explain why it failed |
| Malformed JSON | ❌ FAIL with JSON error | Should show parse error |
| Missing fields | ❌ FAIL with field list | Should list missing fields |
| Non-existent file | ❌ FAIL with file error | Should show file not found |
| GitHub Action - valid | ✅ Green status | Should pass validation |
| GitHub Action - invalid | ❌ Red status | Should fail with errors |

## Next Steps

After testing:

1. ✅ Fix any issues found during testing
2. ✅ Update documentation if needed
3. ✅ Create the two test PRs as required
4. ✅ Verify GitHub Actions work correctly
5. ✅ Submit your implementation

Good luck with your testing! 🚀

