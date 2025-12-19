# SWE-bench Docker Architecture Documentation

## Overview

SWE-bench uses a sophisticated 3-layer Docker image architecture to ensure reproducible, isolated test environments for evaluating AI-generated code patches. This document explains how the Docker system works, how images are built, how tests are executed, and how the validator integrates with this infrastructure.

## Docker Architecture: 3-Layer System

SWE-bench employs a hierarchical Docker image system that maximizes efficiency through layer reuse while maintaining isolation between different test scenarios.

### Layer 1: Base Images

**Purpose**: Foundation layer containing common system dependencies and tools.

**Contents**:
- Base operating system (typically Ubuntu or Debian)
- System-level packages (git, curl, wget, build tools)
- Python runtime environment
- Common development tools

**Characteristics**:
- Shared across all repositories
- Rarely rebuilt (only when system dependencies change)
- Tagged with OS and Python version (e.g., `swe-bench-base:ubuntu22.04-python3.10`)

**Example**:
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y \
    git curl wget build-essential \
    python3.10 python3-pip python3-venv
```

### Layer 2: Environment Images

**Purpose**: Repository-specific environment setup with dependencies installed.

**Contents**:
- Base image (Layer 1)
- Repository codebase at the base commit
- All repository dependencies (requirements.txt, setup.py, etc.)
- Pre-installed Python packages and system libraries
- Repository-specific build tools and configurations

**Characteristics**:
- One per repository (e.g., `astropy/astropy`, `django/django`)
- Built from the `base_commit` specified in each data point
- Contains the exact dependency versions needed for that repository
- Tagged with repository and commit hash (e.g., `swe-bench-env:astropy-astropy-3832210580`)

**When Built**:
- Built once per repository when first data point from that repo is evaluated
- Rebuilt if `base_commit` changes or dependencies are updated
- Cached and reused for all instances from the same repository

**Dependency Installation**:
- Requirements are installed during image build time
- This includes all packages from `requirements.txt`, `setup.py`, `pyproject.toml`, etc.
- System-level dependencies are also installed (e.g., C libraries, database servers)

**Example Build Process**:
```dockerfile
FROM swe-bench-base:ubuntu22.04-python3.10
WORKDIR /opt/swe-bench
# Clone repository at base commit
RUN git clone https://github.com/astropy/astropy.git . && \
    git checkout 3832210580d516365ddae1a62071001faf94d416
# Install dependencies
RUN pip install -r requirements.txt && \
    pip install -e . && \
    pip install pytest pytest-cov
```

### Layer 3: Instance Images

**Purpose**: Test-specific container with the patch applied and ready for test execution.

**Contents**:
- Environment image (Layer 2)
- Applied patch from the data point
- Test files (if modified by patch)
- Test execution environment configured

**Characteristics**:
- One per data point instance
- Built on-demand when a specific instance is evaluated
- Contains the exact code state after patch application
- Tagged with instance ID (e.g., `swe-bench-instance:astropy__astropy-11693`)

**When Built**:
- Built dynamically when `run_evaluation` is called for a specific instance
- Built from the corresponding environment image
- Patch is applied during build or container startup

## Image Building Process

### Build Sequence

1. **Base Image Build** (if not exists):
   ```bash
   docker build -t swe-bench-base:ubuntu22.04-python3.10 -f Dockerfile.base .
   ```
   - Happens once per OS/Python combination
   - Cached indefinitely unless base OS changes

2. **Environment Image Build** (if not exists for repository):
   ```bash
   docker build \
     --build-arg BASE_COMMIT=3832210580d516365ddae1a62071001faf94d416 \
     -t swe-bench-env:astropy-astropy-3832210580 \
     -f Dockerfile.env .
   ```
   - Happens when first instance from a repository is evaluated
   - Includes full dependency installation
   - Can take 5-30 minutes depending on repository size

3. **Instance Container Creation** (on-demand):
   ```bash
   docker run --rm \
     -v /path/to/patch:/patch.diff \
     swe-bench-env:astropy-astropy-3832210580 \
     /bin/bash -c "git apply /patch.diff && <test-command>"
   ```
   - Created dynamically for each evaluation
   - Patch applied at runtime or during container initialization
   - Container is ephemeral (removed after test execution)

### Dependency Installation Timeline

**When**: Dependencies are installed during **Environment Image Build** (Layer 2)

**Where**: Inside the Dockerfile that builds the environment image

**Process**:
1. Repository is cloned at the `base_commit`
2. All dependency files are identified (`requirements.txt`, `setup.py`, `pyproject.toml`, `environment.yml`, etc.)
3. Dependencies are installed using appropriate package managers:
   - Python: `pip install -r requirements.txt`
   - Conda: `conda env create -f environment.yml`
   - System: `apt-get install` or `yum install`
4. Repository itself may be installed in development mode: `pip install -e .`
5. Test frameworks are installed: `pytest`, `unittest`, etc.

**Why at Layer 2**: Installing dependencies during environment image build ensures:
- Dependencies are cached and reused across all instances from the same repository
- Faster instance container creation (no dependency installation needed)
- Consistent dependency versions across all evaluations
- Isolation from host system dependencies

## Test Execution Flow

### Execution Process

When `swebench.harness.run_evaluation` is called, the following steps occur:

#### 1. Instance Preparation

```python
# Pseudo-code of what happens internally
instance = load_instance("astropy__astropy-11693.json")
prediction = {
    "instance_id": instance["instance_id"],
    "patch": instance["patch"],  # Golden patch from data point
    "model_name": "golden"
}
```

#### 2. Environment Image Selection/Verification

- Check if environment image exists for the repository and base commit
- If not exists, trigger environment image build (Layer 2)
- Wait for build completion

#### 3. Container Creation and Patch Application

```bash
# Container is created from environment image
docker create \
  --name swe-instance-astropy__astropy-11693 \
  swe-bench-env:astropy-astropy-3832210580

# Patch is applied inside container
docker exec swe-instance-astropy__astropy-11693 \
  git apply /tmp/patch.diff

# Or patch is applied during container startup via entrypoint script
```

**Patch Application Process**:
- Patch file is written to container filesystem
- `git apply` or `patch` command is executed
- If patch fails to apply, evaluation stops with error
- Modified files are now in the container

#### 4. Test Execution

**FAIL_TO_PASS Tests** (tests that should pass after patch):
```bash
docker exec swe-instance-astropy__astropy-11693 \
  pytest astropy/wcs/wcsapi/tests/test_fitswcs.py::test_non_convergence_warning \
  --timeout=300
```

**PASS_TO_PASS Tests** (tests that should still pass):
```bash
docker exec swe-instance-astropy__astropy-11693 \
  pytest astropy/wcs/wcsapi/tests/test_fitswcs.py::test_empty \
  astropy/wcs/wcsapi/tests/test_fitswcs.py::test_simple_celestial \
  # ... all other PASS_TO_PASS tests
```

**Timeout Handling**:
- Each test execution has a configurable timeout (default: 300 seconds)
- If test exceeds timeout, it's marked as failed/timed out
- Container continues to next test or is terminated

#### 5. Output Parsing and Result Extraction

- Test output (stdout/stderr) is captured
- Exit codes are checked (0 = pass, non-zero = fail)
- Test results are parsed from pytest/unittest output
- Results are aggregated into evaluation report

#### 6. Container Cleanup

```bash
docker rm -f swe-instance-astropy__astropy-11693
```

### Concrete Execution Example

**Data Point**: `astropy__astropy-11693.json`

**Step-by-step execution**:

1. **Load instance**:
   ```python
   instance = {
       "instance_id": "astropy__astropy-11693",
       "repo": "astropy/astropy",
       "base_commit": "3832210580d516365ddae1a62071001faf94d416",
       "patch": "diff --git a/astropy/wcs/wcsapi/fitswcs.py...",
       "FAIL_TO_PASS": ["astropy/wcs/wcsapi/tests/test_fitswcs.py::test_non_convergence_warning"],
       "PASS_TO_PASS": ["astropy/wcs/wcsapi/tests/test_fitswcs.py::test_empty", ...]
   }
   ```

2. **Check/Create environment image**:
   ```bash
   # Check if exists
   docker images | grep "swe-bench-env:astropy-astropy-3832210580"
   
   # If not exists, build it (includes dependency installation)
   docker build -t swe-bench-env:astropy-astropy-3832210580 .
   ```

3. **Create instance container and apply patch**:
   ```bash
   docker run -d --name instance-11693 \
     swe-bench-env:astropy-astropy-3832210580 \
     tail -f /dev/null  # Keep container running
   
   # Copy patch into container
   echo "$PATCH_CONTENT" | docker exec -i instance-11693 \
     bash -c "cat > /tmp/patch.diff"
   
   # Apply patch
   docker exec instance-11693 \
     git apply /tmp/patch.diff
   ```

4. **Execute FAIL_TO_PASS test**:
   ```bash
   docker exec instance-11693 \
     pytest astropy/wcs/wcsapi/tests/test_fitswcs.py::test_non_convergence_warning \
     -v --tb=short
   # Expected: PASS (test should now pass with patch)
   ```

5. **Execute PASS_TO_PASS tests**:
   ```bash
   docker exec instance-11693 \
     pytest astropy/wcs/wcsapi/tests/test_fitswcs.py::test_empty \
            astropy/wcs/wcsapi/tests/test_fitswcs.py::test_simple_celestial \
     # ... all other tests
   # Expected: All PASS (tests should still pass)
   ```

6. **Collect results**:
   ```python
   results = {
       "instance_id": "astropy__astropy-11693",
       "FAIL_TO_PASS": {"test_non_convergence_warning": "PASS"},
       "PASS_TO_PASS": {
           "test_empty": "PASS",
           "test_simple_celestial": "PASS",
           # ... all other tests
       },
       "all_passed": True
   }
   ```

7. **Cleanup**:
   ```bash
   docker rm -f instance-11693
   ```

## Integration Points for Validator

### How Validator Uses Docker Infrastructure

The validator integrates with SWE-bench's Docker system through the `swebench.harness.run_evaluation` function:

```python
from swebench.harness.run_evaluation import run_evaluation

# Validator converts data point to prediction format
prediction = {
    "instance_id": instance["instance_id"],
    "model_name": "golden",
    "patch": instance["patch"]  # Golden patch from data point
}

# Run evaluation (handles all Docker operations internally)
results = run_evaluation(
    instances=[prediction],
    swe_bench_tasks="swe-bench",
    log_dir="./logs",
    timeout=600,  # Per-instance timeout
    verbose=True
)
```

### What Happens Under the Hood

1. **Validator calls `run_evaluation`** with data point converted to prediction format
2. **`run_evaluation` handles**:
   - Environment image building (if needed)
   - Container creation
   - Patch application
   - Test execution
   - Result collection
3. **Validator validates results**:
   - Checks that all `FAIL_TO_PASS` tests passed
   - Checks that all `PASS_TO_PASS` tests passed
   - Reports any failures with detailed error messages

### Validator's Role

The validator acts as a **quality gate** that:
- Ensures data points have valid structure (JSON, required fields)
- Verifies that golden patches actually work (all tests pass)
- Provides clear error messages when validation fails
- Integrates with CI/CD to prevent invalid data points from being committed

## Summary

SWE-bench's Docker architecture provides:

1. **Efficiency**: Layer reuse minimizes build times and storage
2. **Isolation**: Each test runs in a clean, reproducible environment
3. **Reproducibility**: Same base commit + dependencies = same results
4. **Scalability**: Can evaluate thousands of instances efficiently

The 3-layer system ensures that:
- **Base images** provide common infrastructure (built once)
- **Environment images** contain repository-specific setup (built per repo)
- **Instance containers** are ephemeral and created on-demand (one per evaluation)

Dependencies are installed during **Environment Image Build** (Layer 2), ensuring they're cached and reused across all instances from the same repository, while maintaining consistency and isolation.

