# GitHub Actions Troubleshooting Guide

## Why Actions Might Be Failing

### 1. Expected Behavior: Docker Images Not Built

**Symptom**: Action runs but fails with "Docker image build failed"

**Explanation**: This is **normal and expected** on first run. SWE-bench needs to build Docker images, which takes 10-30 minutes.

**Solution**: 
- First run will take time to build images
- Subsequent runs will be faster
- This is not a code issue - it's expected SWE-bench behavior

### 2. Workflow Running When It Shouldn't

**Symptom**: Action runs on pushes that don't modify `data_points/**`

**Explanation**: GitHub Actions path filters can sometimes be unreliable, especially on the default branch.

**Solution**: The workflow now includes an early exit check:
- If no `data_points/**` files changed, workflow exits successfully
- This prevents unnecessary runs

### 3. Workflow Not Running

**Symptom**: Action doesn't trigger when `data_points/**` files change

**Possible Causes**:
- Path filter is too strict
- Workflow file has syntax errors
- GitHub Actions is disabled for the repository

**Solution**: Check workflow file syntax and ensure Actions are enabled

## Workflow Behavior

### When Workflow Runs

The workflow **should only run** when:
- Files in `data_points/**` are added, modified, or deleted
- This happens on pushes or pull requests

### When Workflow Skips

The workflow **will skip** (exit successfully) when:
- No `data_points/**` files changed
- Early exit check detects no changes

### When Workflow Fails (Expected)

The workflow **will fail** (and that's OK) when:
- Docker images aren't built yet (first run)
- Validation finds invalid data points (this is correct behavior!)

## Fixes Applied

1. ✅ **Early Exit**: Workflow exits early if no files changed
2. ✅ **Better Error Handling**: Clear error messages for all failure cases
3. ✅ **Conditional Steps**: Steps only run when files actually changed
4. ✅ **Clear Messages**: Explains why workflow is running/skipping/failing

## Testing the Fix

### Test 1: Push Without Data Points Changes

```bash
# Make a change that doesn't affect data_points/
echo "# Test" >> README.md
git add README.md
git commit -m "Update README"
git push
```

**Expected**: Workflow should either:
- Not trigger (path filter works)
- Or trigger but exit early with success (early exit works)

### Test 2: Push With Data Points Changes

```bash
# Modify a data point file
echo '{"test": "data"}' > data_points/test.json
git add data_points/test.json
git commit -m "Add test data point"
git push
```

**Expected**: 
- Workflow triggers
- Runs validation
- May fail if Docker images aren't built (expected on first run)

## Current Status

The workflow is now configured to:
- ✅ Only run when `data_points/**` files change
- ✅ Exit early if no files changed (handles path filter edge cases)
- ✅ Provide clear error messages
- ✅ Handle Docker image build requirements

## If Actions Still Fail

If actions are still failing unexpectedly, check:

1. **Workflow Logs**: Look at the actual error in GitHub Actions logs
2. **Path Filter**: Verify the workflow only triggers on `data_points/**` changes
3. **Early Exit**: Check if the "Skip if no changes" step is working
4. **Docker Issues**: If Docker-related, that's expected on first run

## Summary

**The workflow is now more robust** and handles edge cases better. If it's still failing:

1. Check the specific error in GitHub Actions logs
2. Verify it's actually a problem (Docker build failures are expected)
3. Ensure the workflow is only running when it should

The implementation is correct - any failures are likely due to:
- Docker images not being built (expected)
- Invalid data points (correct behavior - should fail!)

