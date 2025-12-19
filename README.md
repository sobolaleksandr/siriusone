# SWE-bench Data Point Validator

A validation system for SWE-bench data points that ensures the quality and correctness of data points when they are committed to a repository. This project includes a command-line validator and GitHub Actions integration.

## Features

- ✅ **Validates data points** using SWE-bench's official evaluation harness
- ✅ **Docker-based evaluation** with proper isolation and reproducibility
- ✅ **GitHub Actions integration** for automatic validation on PRs and pushes
- ✅ **Changed-files detection** - only validates modified data points (performance optimized)
- ✅ **Comprehensive error reporting** with detailed failure messages
- ✅ **Timeout handling** for long-running evaluations

## Installation

This project uses [UV](https://github.com/astral-sh/uv) for dependency management.

### Prerequisites

- Python 3.10+
- [UV](https://github.com/astral-sh/uv) package manager
- Docker (required for running evaluations)

### Setup

1. **Install UV** (if not already installed):
   ```bash
   pip install uv
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Verify Docker is running**:
   ```bash
   docker --version
   docker ps  # Should not error
   ```

4. **Note on Docker Images**: 
   SWE-bench will build Docker images on first run. This may take time and requires:
   - Sufficient disk space (several GB)
   - Network access to download base images (if available)
   - If base images aren't available, SWE-bench will build them from scratch
   - First validation run may take 10-30 minutes while images are built

## Usage

### Command-Line Validator

#### Validate a single file:
```bash
uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json
```

#### Validate all files in a directory:
```bash
uv run python -m swe_bench_validator data_points/
```

#### Validate multiple files:
```bash
uv run python -m swe_bench_validator data_points/*.json
```

#### With custom timeout (in seconds):
```bash
uv run python -m swe_bench_validator --timeout 1200 data_points/
```

#### Continue on error (validate all files even if one fails):
```bash
uv run python -m swe_bench_validator --continue-on-error data_points/
```

#### Verbose output:
```bash
uv run python -m swe_bench_validator --verbose data_points/
```

#### JSON output:
```bash
uv run python -m swe_bench_validator --json-output data_points/
```

### GitHub Actions

The validator automatically runs on:
- **Pushes** to branches that modify files in `data_points/**`
- **Pull requests** that modify files in `data_points/**`

The workflow:
1. Detects only changed JSON files in `data_points/` directory
2. Runs validation on modified files only (performance optimization)
3. Reports results as status checks
4. Provides detailed error messages for failures

## Creating Test Pull Requests

To demonstrate the validator working in GitHub Actions, create two test PRs:

### PR #1: Valid Data Point (Should Pass)

This PR adds a valid data point that passes all validation checks.

```bash
# Create a new branch for the valid data point PR
git checkout -b test-valid-datapoint

# Copy the valid data point (or create your own)
cp data_points/astropy__astropy-11693.json data_points/test_valid.json

# Commit and push
git add data_points/test_valid.json
git commit -m "Add valid test data point"
git push origin test-valid-datapoint

# Create PR on GitHub (or use GitHub CLI)
gh pr create --title "Test: Valid data point" --body "Testing validator with a valid data point"
```

**Expected Result**: 
- ✅ GitHub Actions workflow runs
- ✅ Environment images build successfully (1-2 minutes)
- ⚠️ Instance images may need to be pre-built (SWE-bench requirement)
- ✅ Validator correctly detects and reports status

### PR #2: Invalid Data Point (Should Fail)

This PR adds an invalid data point that triggers validation failures.

```bash
# Create a new branch for the invalid data point PR
git checkout -b test-invalid-datapoint

# Copy the invalid data point (or create your own)
cp data_points/astropy__astropy-11693-fail.json data_points/test_invalid.json

# Commit and push
git add data_points/test_invalid.json
git commit -m "Add invalid test data point"
git push origin test-invalid-datapoint

# Create PR on GitHub (or use GitHub CLI)
gh pr create --title "Test: Invalid data point" --body "Testing validator with an invalid data point"
```

**Expected Result**:
- ✅ GitHub Actions workflow runs
- ✅ Validator detects invalid patch
- ❌ Validation fails with clear error messages
- ✅ Status check shows red with detailed failure explanation

### Testing Locally Before Creating PRs

**Important**: The validator uses `namespace=None` to build instance images locally. On the first run, instance images will be built automatically (takes 5-15 minutes per instance). Subsequent runs will be faster as images are cached.

Before creating PRs, test locally:

```bash
# Test valid data point (uses Docker Hub image if DOCKER_NAMESPACE is set)
DOCKER_NAMESPACE=sobolav uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json --verbose

# Test invalid data point
DOCKER_NAMESPACE=sobolav uv run python -m swe_bench_validator data_points/astropy__astropy-11693-fail.json --verbose

# Or without Docker Hub (will build locally):
uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json --verbose
```

### Note on Instance Images

**Important**: The validator uses `namespace=None` to build instance images locally. This means:

- **Environment images**: Will build automatically ✅ (both locally and in CI)
- **Instance images**: Will build automatically on first run ✅ (takes 5-15 minutes per instance)
- **Subsequent runs**: Will be faster as images are cached ✅

**How it works**: When `namespace=None`, SWE-bench treats images as local and builds them automatically. The validator is configured to use this approach, so instance images will be built on first run without needing to pre-build them manually.

**For local testing**, instance images will be built automatically on first run. However, if you want to pre-build them manually (optional):

1. **Pre-build instance images** (optional, validator will build automatically):
   ```bash
   # Option A: Use project's virtual environment (recommended)
   cd /path/to/your/project
   
   # Install SWE-bench in the project's virtual environment using UV
   # First, clone SWE-bench repository (if not already cloned)
   git clone https://github.com/princeton-nlp/SWE-bench.git
   
   # Install SWE-bench using UV (this project uses UV for package management)
   uv pip install -e ./SWE-bench
   
   # Verify installation
   .venv/bin/python -c "import swebench; print('SWE-bench installed successfully')"
   
   # Build instance image using the venv Python
   # Note: astropy__astropy-11693 is in the "test" split
   # This will take 5-15 minutes to build the instance image
   # Use --namespace "" (empty) to build locally, or omit for default behavior
   .venv/bin/python -m swebench.harness.prepare_images \
     --dataset_name "princeton-nlp/SWE-bench" \
     --split "test" \
     --instance_ids astropy__astropy-11693 \
     --max_workers 1 \
     --force_rebuild False \
     --tag latest \
     --namespace ""
   
   # After building, verify the image exists
   docker images | grep astropy-11693
   ```
   
   ```bash
   # Option B: Install SWE-bench globally and use specific Python
   git clone https://github.com/princeton-nlp/SWE-bench.git
   cd SWE-bench
   python3.11 -m pip install --user -e .
   
   # Use the Python that has SWE-bench installed
   # Note: astropy__astropy-11693 is in the "test" split
   # This will take 5-15 minutes to build the instance image
   # Use --namespace "" (empty) to build locally
   python3.11 -m swebench.harness.prepare_images \
     --dataset_name "princeton-nlp/SWE-bench" \
     --split "test" \
     --instance_ids astropy__astropy-11693 \
     --max_workers 1 \
     --force_rebuild False \
     --tag latest \
     --namespace ""
   ```
   
   **Important**: Always use the Python where SWE-bench is installed:
   - ✅ `.venv/bin/python` (if installed in project venv)
   - ✅ `python3.11` (if installed with `python3.11 -m pip install`)
   - ❌ `/usr/bin/python` or `python3` (system Python, may not have SWE-bench)
   
   **Troubleshooting**: If you get `ModuleNotFoundError: No module named 'swebench'`:
   ```bash
   # Check which Python you're using
   which python
   python --version
   
   # Verify SWE-bench is installed in that Python
   python -c "import swebench; print('SWE-bench found')"
   
   # If not found, install it:
   python -m pip install -e /path/to/SWE-bench
   ```
   
   **Alternative**: You can also build instance images programmatically:
   ```python
   from swebench.harness.docker_build import build_instance_image
   from swebench.harness.test_spec.test_spec import make_test_spec
   from swebench.harness.utils import load_swebench_dataset
   import docker
   import logging
   
   # Load instance
   instances = load_swebench_dataset(
       name='princeton-nlp/SWE-bench',
       instance_ids=['astropy__astropy-11693']
   )
   instance = instances[0]
   
   # Create test spec
   test_spec = make_test_spec(instance, namespace="")
   
   # Build instance image
   client = docker.from_env()
   logger = logging.getLogger(__name__)
   build_instance_image(test_spec, client, logger, nocache=False)
   ```

2. **Use the validator to detect issues** (works without instance images):
   - Validator will build environment images ✅
   - Validator will detect missing instance images ✅
   - Validator will provide clear error messages ✅
   - This demonstrates the validator is working correctly

**For CI/GitHub Actions**: Instance images can be pre-built and published to a registry (e.g., Docker Hub) for faster runs. Set `DOCKER_NAMESPACE` environment variable to use pre-built images.

## Data Point Format

Each data point is a JSON file with the following required fields:

- `instance_id`: Unique identifier (e.g., `"astropy__astropy-11693"`)
- `repo`: Repository name (e.g., `"astropy/astropy"`)
- `base_commit`: Git commit hash for the base state
- `patch`: Git patch that fixes the issue
- `FAIL_TO_PASS`: JSON string array of test paths that should pass after patch
- `PASS_TO_PASS`: JSON string array of test paths that should still pass

Example:
```json
{
  "instance_id": "astropy__astropy-11693",
  "repo": "astropy/astropy",
  "base_commit": "3832210580d516365ddae1a62071001faf94d416",
  "patch": "diff --git a/...",
  "FAIL_TO_PASS": "[\"astropy/wcs/wcsapi/tests/test_fitswcs.py::test_non_convergence_warning\"]",
  "PASS_TO_PASS": "[\"astropy/wcs/wcsapi/tests/test_fitswcs.py::test_empty\", ...]"
}
```

## Validation Process

The validator:

1. **Loads and validates structure** of the JSON file
2. **Converts data point** to SWE-bench prediction format
3. **Runs evaluation** using `swebench.harness.run_evaluation`:
   - Builds Docker containers (if needed)
   - Applies the patch
   - Runs all tests in `FAIL_TO_PASS` and `PASS_TO_PASS`
4. **Validates results**:
   - All `FAIL_TO_PASS` tests must pass
   - All `PASS_TO_PASS` tests must still pass
5. **Reports errors** with detailed messages

## Examples

### Valid Data Point

The file `data_points/astropy__astropy-11693.json` is a valid data point:
- Patch applies successfully
- All `FAIL_TO_PASS` tests pass after patch
- All `PASS_TO_PASS` tests still pass

```bash
uv run python -m swe_bench_validator data_points/astropy__astropy-11693.json
# Output: ✓ PASSED: astropy__astropy-11693 (astropy__astropy-11693.json)
```

### Invalid Data Point

The file `data_points/astropy__astropy-11693-fail.json` is an invalid data point:
- Patch doesn't properly fix the issue (still raises exception)
- `FAIL_TO_PASS` test still fails

```bash
uv run python -m swe_bench_validator data_points/astropy__astropy-11693-fail.json
# Output: ✗ FAILED: astropy__astropy-11693-fail (astropy__astropy-11693-fail.json)
# Error: FAIL_TO_PASS test '...' did not pass. Status: FAIL
```

## Project Structure

```
.
├── .github/
│   └── workflows/
│       └── validate-datapoints.yml  # GitHub Action workflow
├── data_points/                      # Data point JSON files
│   ├── astropy__astropy-11693.json      # Valid example
│   └── astropy__astropy-11693-fail.json # Invalid example
├── swe_bench_validator/              # Validator module
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                        # CLI interface
│   ├── config.py                     # Configuration
│   └── validator.py                  # Core validation logic
├── .github/
│   └── workflows/
│       └── validate-datapoints.yml   # GitHub Actions workflow
├── swe-bench-docker-architecture.md  # Docker architecture docs
├── pyproject.toml                    # Project configuration
└── README.md                         # This file
```

## Docker Architecture

SWE-bench uses a 3-layer Docker image system for evaluation:

1. **Base Images**: Common system dependencies and tools
2. **Environment Images**: Repository-specific setup with dependencies
3. **Instance Containers**: Ephemeral containers with patches applied

See [swe-bench-docker-architecture.md](swe-bench-docker-architecture.md) for detailed documentation.

## Error Handling

The validator handles several types of errors:

### Structural Errors
- Invalid JSON format
- Missing required fields
- Invalid test list format
- Empty patch

### Execution Errors
- Docker build failures
- Patch application failures
- Test execution failures
- Timeout errors

### Validation Errors
- `FAIL_TO_PASS` tests still failing
- `PASS_TO_PASS` tests broken

All errors include detailed messages to help diagnose issues.

## Configuration

Default configuration can be customized:

- `default_timeout`: 600 seconds (10 minutes per instance)
- `timeout_per_test`: 300 seconds (5 minutes per test)
- `log_dir`: `./validation_logs`
- `swe_bench_tasks`: `"swe-bench"`

## Troubleshooting

### Import Errors

If you see `ImportError: cannot import name 'run_evaluation'`:
1. Check your SWE-bench version: `pip show swebench`
2. The validator tries to auto-detect the correct function name
3. Check SWE-bench installation and API compatibility
4. Update SWE-bench if needed: `pip install --upgrade swebench>=4.0.4`
5. Check SWE-bench documentation for API changes

### Docker Issues

If you see Docker-related errors:

1. **Image Build/Pull Failures**:
   - Ensure Docker is running: `docker ps`
   - Check Docker permissions (you may need to be in `docker` group)
   - Verify Docker has enough resources (memory, disk space)
   - If you see "404 Not Found" for images, SWE-bench will build them from scratch
   - First run may take 10-30 minutes while building images
   - Check validation logs in the log directory for detailed error messages

2. **Common Docker Errors**:
   - `ImageNotFound`: SWE-bench will attempt to build the image locally
   - `pull access denied`: Images will be built from scratch (this is normal)
   - `No space left on device`: Free up disk space or clean old Docker images

### Timeout Issues

If evaluations timeout:
- Increase timeout: `--timeout 1800` (30 minutes)
- Check if repository has heavy dependencies
- Verify network connectivity for dependency downloads

### Patch Application Failures

If patches fail to apply:
- Verify the `base_commit` is correct
- Check that the patch format is valid
- Ensure the patch matches the repository state at `base_commit`

## Contributing

1. Ensure all data points pass validation before committing
2. Use the validator locally before pushing
3. Check GitHub Actions status for CI validation

## License

This project is part of the SWE-bench infrastructure tools.

## References

- [SWE-bench Repository](https://github.com/princeton-nlp/SWE-bench)
- [SWE-bench Evaluation Guide](https://www.swebench.com/SWE-bench/guides/evaluation/)
- [SWE-bench Setup Guide](https://github.com/SWE-bench/SWE-bench?tab=readme-ov-file#-set-up)

