# Implementation Plan: SWE-bench Data Point Validator

## Overview

This document outlines the implementation plan for building a SWE-bench data point validation system with GitHub Actions integration.

## Task Breakdown

### 1. SWE-bench Docker Architecture Documentation

**Objective**: Create comprehensive documentation explaining SWE-bench's Docker evaluation system.

**Approach**:
- Research SWE-bench evaluation harness source code and documentation
- Study the 3-layer Docker architecture (Base → Environment → Instance)
- Document image building process and dependency installation
- Explain test execution flow with concrete examples
- Document integration points for the validator

**Deliverable**: `swe-bench-docker-architecture.md` (100-300 lines)

**Key Sections**:
- Docker Architecture Overview (3-layer system)
- Image Building Process
- Test Execution Flow
- Integration Points
- When/where requirements are installed

### 2. SWE-bench Data Point Validator Implementation

**Objective**: Create a Python validator that uses SWE-bench's official evaluation harness.

**Structure**:
```
swe_bench_validator/
├── __init__.py
├── __main__.py
├── validator.py          # Core validation logic
├── cli.py                # CLI interface using Click
└── config.py             # Configuration management
```

**Key Components**:

1. **Data Point Loader** (`validator.py`):
   - Load JSON files from `data_points/` directory
   - Validate JSON structure and required fields
   - Parse `FAIL_TO_PASS` and `PASS_TO_PASS` test lists

2. **Patch Converter** (`validator.py`):
   - Convert data point to SWE-bench prediction format
   - Extract `patch` field as golden patch
   - Format for `swebench.harness.run_evaluation`

3. **Evaluation Runner** (`validator.py`):
   - Call `swebench.harness.run_evaluation` with proper parameters
   - Handle Docker container execution
   - Parse evaluation results

4. **Result Validator** (`validator.py`):
   - Check that all `FAIL_TO_PASS` tests pass
   - Check that all `PASS_TO_PASS` tests still pass
   - Generate detailed error messages

5. **Error Handling**:
   - Structural errors: JSON parsing, missing fields, invalid format
   - Execution errors: Docker failures, test failures, timeouts
   - Clear, actionable error messages

6. **Timeout Management** (`config.py`):
   - Configurable timeouts per data point type
   - Default timeout values
   - Timeout handling in evaluation

**CLI Interface** (`cli.py`):
```bash
# Validate single file
python -m swe_bench_validator data_points/astropy__astropy-11693.json

# Validate directory
python -m swe_bench_validator data_points/

# Validate with custom timeout
python -m swe_bench_validator --timeout 600 data_points/
```

**Dependencies**:
- `swebench>=4.0.4` (already in pyproject.toml)
- `click>=8.0.0` (already in pyproject.toml)
- `rich>=12.0.0` (already in pyproject.toml)

### 3. GitHub Action Workflow

**Objective**: Create CI/CD workflow that validates changed data points.

**File**: `.github/workflows/validate-datapoints.yml`

**Key Features**:

1. **Triggers**:
   - `on.push`: paths `data_points/**`
   - `on.pull_request`: paths `data_points/**`

2. **Changed Files Detection**:
   - Use `dorny/paths-filter@v2` or `git diff` to detect changed files
   - Only process files in `data_points/` directory
   - Filter for `.json` files

3. **Validation Steps**:
   - Setup Python environment (using UV)
   - Install dependencies
   - Run validator on changed files
   - Report results as status checks

4. **Error Reporting**:
   - Detailed logs for failures
   - Status check messages
   - Annotations for each failed file

**Workflow Structure**:
```yaml
name: Validate Data Points

on:
  push:
    paths:
      - 'data_points/**'
  pull_request:
    paths:
      - 'data_points/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
      - name: Install UV
        run: pip install uv
      - name: Install dependencies
        run: uv sync
      - name: Detect changed files
        id: changed-files
        run: |
          # Detect changed JSON files in data_points/
      - name: Validate data points
        run: |
          uv run python -m swe_bench_validator ${{ steps.changed-files.outputs.files }}
      - name: Report results
        # Report validation results
```

### 4. Project Structure Updates

**Files to Create**:
- `swe_bench_validator/__init__.py`
- `swe_bench_validator/__main__.py`
- `swe_bench_validator/validator.py`
- `swe_bench_validator/cli.py`
- `swe_bench_validator/config.py`
- `.github/workflows/validate-datapoints.yml`
- `swe-bench-docker-architecture.md`
- `README.md`

**Files to Update**:
- `pyproject.toml`: Add validator package to packages.find

### 5. Testing Strategy

**Local Testing**:
1. Test with valid data point: `astropy__astropy-11693.json`
2. Test with invalid data point: `astropy__astropy-11693-fail.json`
3. Test with multiple files
4. Test error handling (malformed JSON, missing fields)

**GitHub Action Testing**:
- Create test PR with valid data point (should pass)
- Create test PR with invalid data point (should fail with clear errors)

## Implementation Order

1. **Phase 1: Research & Documentation** (Task 1)
   - Research SWE-bench Docker architecture
   - Create `swe-bench-docker-architecture.md`

2. **Phase 2: Core Validator** (Tasks 2-7)
   - Implement validator module
   - Create CLI interface
   - Add error handling and timeouts
   - Test locally

3. **Phase 3: GitHub Action** (Tasks 8-9)
   - Create workflow file
   - Implement changed-files detection
   - Test in GitHub environment

4. **Phase 4: Documentation & Polish** (Tasks 10-11)
   - Update pyproject.toml
   - Create README.md
   - Final testing

## Technical Considerations

### SWE-bench Evaluation Harness Integration

The validator will use `swebench.harness.run_evaluation` which:
- Takes instances in prediction format
- Builds Docker containers
- Applies patches
- Runs tests
- Returns evaluation results

**Prediction Format**:
```python
{
    "instance_id": "astropy__astropy-11693",
    "model_name": "golden",
    "patch": "<patch content>",
    "prediction": "<patch content>"
}
```

### Docker Requirements

- Docker must be available in the environment
- GitHub Actions runners have Docker support
- Local testing requires Docker daemon

### Error Categories

1. **Structural Errors**:
   - Invalid JSON format
   - Missing required fields (`patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, etc.)
   - Invalid test list format

2. **Execution Errors**:
   - Docker build failures
   - Patch application failures
   - Test execution failures
   - Timeout errors

3. **Validation Errors**:
   - `FAIL_TO_PASS` tests still failing
   - `PASS_TO_PASS` tests broken

## Success Criteria

- ✅ Validator successfully validates valid data points
- ✅ Validator correctly rejects invalid data points with clear errors
- ✅ GitHub Action triggers on data point changes
- ✅ GitHub Action only validates changed files
- ✅ Status checks provide clear feedback
- ✅ Documentation is comprehensive and accurate

