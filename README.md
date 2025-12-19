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
├── swe_bench_downloader/            # Data downloader module
├── swe_bench_validator/              # Validator module
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                        # CLI interface
│   ├── config.py                     # Configuration
│   └── validator.py                  # Core validation logic
├── scripts/
│   └── download_swe_bench.sh         # Downloader script
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

### Docker Issues

If you see Docker-related errors:
1. Ensure Docker is running: `docker ps`
2. Check Docker permissions
3. Verify Docker has enough resources (memory, disk space)

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

