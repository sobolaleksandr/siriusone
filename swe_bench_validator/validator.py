"""
Core validation logic for SWE-bench data points.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback

from rich.console import Console

# Import SWE-bench evaluation function
# SWE-bench 4.0.4 uses run_instances (plural) instead of run_evaluation
try:
    import swebench.harness.run_evaluation as run_eval_module
    
    # Try to find the evaluation function
    # SWE-bench 4.0.4 uses 'run_instances' (plural) for batch evaluation
    # Also try 'run_instance' (singular) and legacy names
    run_evaluation = None
    for func_name in ['run_instances', 'run_instance', 'run_evaluation', 'evaluate', 'evaluate_instances']:
        if hasattr(run_eval_module, func_name):
            attr = getattr(run_eval_module, func_name)
            # Check if it's callable (a function)
            if callable(attr):
                run_evaluation = attr
                # Prefer run_instances if available (it's the batch version)
                if func_name == 'run_instances':
                    break
    
    if run_evaluation is None:
        # If no function found, inspect the module and provide helpful error
        available = [attr for attr in dir(run_eval_module) 
                     if not attr.startswith('_') and callable(getattr(run_eval_module, attr, None))]
        available_all = [attr for attr in dir(run_eval_module) if not attr.startswith('_')]
        raise ImportError(
            f"Could not find evaluation function in swebench.harness.run_evaluation.\n"
            f"Callable functions found: {available}\n"
            f"All attributes: {available_all}\n"
            f"Please check SWE-bench installation and version. "
            f"You may need to update the import statement based on your SWE-bench version."
        )
    
except ImportError as e:
    # Provide more helpful error message
    error_msg = str(e)
    if "cannot import name" in error_msg:
        # Try to provide diagnostic info
        try:
            import swebench.harness.run_evaluation as mod
            available = [attr for attr in dir(mod) if not attr.startswith('_')]
            error_msg += f"\nAvailable in module: {available}"
        except:
            pass
    raise ImportError(
        f"SWE-bench library import failed.\n"
        f"Error: {error_msg}\n"
        f"Please ensure swebench>=4.0.4 is installed: pip install swebench>=4.0.4"
    ) from e

# Import constants and utility functions
try:
    from swebench.harness.constants import SWEbenchInstance
    from swebench.harness.run_evaluation import (
        load_swebench_dataset,
        make_test_spec,
        RUN_EVALUATION_LOG_DIR,
    )
    from swebench.harness.grading import get_eval_report
except ImportError:
    SWEbenchInstance = None
    load_swebench_dataset = None
    get_eval_report = None
    make_test_spec = None
    RUN_EVALUATION_LOG_DIR = None

from .config import ValidatorConfig, DEFAULT_CONFIG

console = Console()
logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Base exception for validation errors."""

    pass


class StructuralError(ValidationError):
    """Error in data point structure (JSON, missing fields, etc.)."""

    pass


class ExecutionError(ValidationError):
    """Error during test execution (Docker, test failures, etc.)."""

    pass


class ValidationResult:
    """Result of validating a single data point."""

    def __init__(
        self,
        instance_id: str,
        file_path: Path,
        success: bool,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        evaluation_results: Optional[Dict[str, Any]] = None,
    ):
        self.instance_id = instance_id
        self.file_path = file_path
        self.success = success
        self.errors = errors or []
        self.warnings = warnings or []
        self.evaluation_results = evaluation_results

    def __str__(self) -> str:
        status = "✓ PASSED" if self.success else "✗ FAILED"
        return f"{status}: {self.instance_id} ({self.file_path.name})"

    def __repr__(self) -> str:
        return (
            f"ValidationResult(instance_id={self.instance_id!r}, "
            f"success={self.success}, errors={len(self.errors)})"
        )


class DataPointValidator:
    """Validates SWE-bench data points using the official evaluation harness."""

    REQUIRED_FIELDS = [
        "instance_id",
        "repo",
        "base_commit",
        "patch",
        "FAIL_TO_PASS",
        "PASS_TO_PASS",
    ]

    def __init__(self, config: Optional[ValidatorConfig] = None):
        """
        Initialize the validator.

        Args:
            config: Validator configuration. Uses default if not provided.
        """
        self.config = config or DEFAULT_CONFIG
        self.log_dir = Path(self.config.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load_data_point(self, file_path: Path) -> Dict[str, Any]:
        """
        Load and validate structure of a data point JSON file.

        Args:
            file_path: Path to the JSON data point file.

        Returns:
            Parsed data point dictionary.

        Raises:
            StructuralError: If JSON is invalid or required fields are missing.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise StructuralError(
                f"Invalid JSON in {file_path}: {str(e)}"
            ) from e
        except FileNotFoundError:
            raise StructuralError(f"File not found: {file_path}")
        except Exception as e:
            raise StructuralError(
                f"Error reading {file_path}: {str(e)}"
            ) from e

        # Validate required fields
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in data]
        if missing_fields:
            raise StructuralError(
                f"Missing required fields in {file_path}: {', '.join(missing_fields)}"
            )

        # Validate test lists are strings (JSON arrays as strings)
        for test_list_field in ["FAIL_TO_PASS", "PASS_TO_PASS"]:
            if not isinstance(data[test_list_field], str):
                raise StructuralError(
                    f"Field {test_list_field} must be a JSON string array, "
                    f"got {type(data[test_list_field]).__name__}"
                )

            # Try to parse the JSON string
            try:
                test_list = json.loads(data[test_list_field])
                if not isinstance(test_list, list):
                    raise StructuralError(
                        f"Field {test_list_field} must be a JSON array, "
                        f"got {type(test_list).__name__}"
                    )
            except json.JSONDecodeError as e:
                raise StructuralError(
                    f"Invalid JSON in {test_list_field}: {str(e)}"
                ) from e

        # Validate patch is not empty
        if not data.get("patch") or not data["patch"].strip():
            raise StructuralError(f"Patch field is empty in {file_path}")

        return data

    def convert_to_prediction_format(
        self, data_point: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert data point to SWE-bench prediction format.

        Args:
            data_point: Data point dictionary.

        Returns:
            Prediction format dictionary for run_evaluation.
        """
        return {
            "instance_id": data_point["instance_id"],
            "model_name": "golden",  # Using golden patch from data point
            "patch": data_point["patch"],
            "prediction": data_point["patch"],  # Same as patch for golden validation
        }

    def parse_test_list(self, test_list_str: str) -> List[str]:
        """
        Parse test list from JSON string.

        Args:
            test_list_str: JSON string array of test paths.

        Returns:
            List of test paths.
        """
        try:
            return json.loads(test_list_str)
        except json.JSONDecodeError as e:
            raise StructuralError(f"Invalid test list JSON: {str(e)}") from e

    def validate_evaluation_results(
        self,
        data_point: Dict[str, Any],
        evaluation_results: Dict[str, Any],
    ) -> tuple[bool, List[str]]:
        """
        Validate that evaluation results meet requirements.

        Args:
            data_point: Original data point.
            evaluation_results: Results from run_evaluation.

        Returns:
            Tuple of (is_valid, list_of_errors).
        """
        errors = []
        instance_id = data_point["instance_id"]

        # Parse test lists
        fail_to_pass_tests = self.parse_test_list(data_point["FAIL_TO_PASS"])
        pass_to_pass_tests = self.parse_test_list(data_point["PASS_TO_PASS"])

        # Get results for this instance
        # Results format from get_eval_report: {instance_id: {test_name: {status: ...}}}
        instance_results = evaluation_results.get(instance_id, {})
        
        # If results are nested differently, try to find them
        if not instance_results and isinstance(evaluation_results, dict):
            # Try direct access
            if "tests" in evaluation_results:
                instance_results = evaluation_results["tests"]
            # Or results might be nested under 'results'
            elif "results" in evaluation_results:
                instance_results = evaluation_results["results"].get(instance_id, {})

        # Check FAIL_TO_PASS tests (should pass after patch)
        for test in fail_to_pass_tests:
            # Test results format from get_eval_report: {test_name: {status: "PASS"/"FAIL", ...}}
            test_result = instance_results.get(test, {})
            
            # Handle different result formats
            if not isinstance(test_result, dict):
                # If test_result is a string or boolean
                status = str(test_result).upper()
            else:
                # Extract status from dict
                status = test_result.get("status", test_result.get("result", "UNKNOWN"))
                status = str(status).upper()
            
            # Check if test passed
            if status not in ["PASS", "PASSED", "TRUE", "1"]:
                error_msg = f"FAIL_TO_PASS test '{test}' did not pass. Status: {status}"
                if isinstance(test_result, dict):
                    if test_result.get("stderr"):
                        error_msg += f"\nError output: {test_result.get('stderr')[:500]}"
                    elif test_result.get("error"):
                        error_msg += f"\nError: {test_result.get('error')[:500]}"
                errors.append(error_msg)

        # Check PASS_TO_PASS tests (should still pass)
        for test in pass_to_pass_tests:
            # Test results format from get_eval_report: {test_name: {status: "PASS"/"FAIL", ...}}
            test_result = instance_results.get(test, {})
            
            # Handle different result formats
            if not isinstance(test_result, dict):
                # If test_result is a string or boolean
                status = str(test_result).upper()
            else:
                # Extract status from dict
                status = test_result.get("status", test_result.get("result", "UNKNOWN"))
                status = str(status).upper()
            
            # Check if test passed
            if status not in ["PASS", "PASSED", "TRUE", "1"]:
                error_msg = f"PASS_TO_PASS test '{test}' failed after patch. Status: {status}"
                if isinstance(test_result, dict):
                    if test_result.get("stderr"):
                        error_msg += f"\nError output: {test_result.get('stderr')[:500]}"
                    elif test_result.get("error"):
                        error_msg += f"\nError: {test_result.get('error')[:500]}"
                errors.append(error_msg)

        return len(errors) == 0, errors

    def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate a single data point file.

        Args:
            file_path: Path to the JSON data point file.

        Returns:
            ValidationResult object with validation outcome.
        """
        instance_id = "unknown"
        errors = []
        warnings = []
        evaluation_results = None

        try:
            # Load and validate structure
            data_point = self.load_data_point(file_path)
            instance_id = data_point["instance_id"]

            # Run evaluation using SWE-bench harness
            if self.config.verbose:
                console.print(
                    f"[cyan]Running evaluation for {instance_id}...[/cyan]"
                )

            try:
                # Load the instance from the dataset
                if load_swebench_dataset is None:
                    raise ExecutionError(
                        "load_swebench_dataset not available. "
                        "Please ensure swebench>=4.0.4 is installed."
                    )
                
                # Load instance from dataset
                try:
                    instances = load_swebench_dataset(
                        name=self.config.swe_bench_tasks,
                        instance_ids=[instance_id]
                    )
                except ValueError as e:
                    # Handle case where instance doesn't exist in dataset
                    if "not found in dataset" in str(e) or "Missing IDs" in str(e):
                        raise ExecutionError(
                            f"Instance {instance_id} not found in SWE-bench dataset {self.config.swe_bench_tasks}.\n"
                            f"This usually means:\n"
                            f"  1. The instance_id in the data point doesn't exist in the dataset\n"
                            f"  2. For testing invalid patches, use the same instance_id as a valid data point\n"
                            f"     but with a broken patch (e.g., use 'astropy__astropy-11693' with a bad patch)\n"
                            f"  3. Check that the instance_id matches an actual SWE-bench instance\n\n"
                            f"Error: {str(e)}"
                        ) from e
                    raise
                
                if not instances:
                    raise ExecutionError(
                        f"Instance {instance_id} not found in dataset {self.config.swe_bench_tasks}.\n"
                        f"Available instances can be checked using the downloader:\n"
                        f"  scripts/download_swe_bench.sh --repo astropy/astropy --limit 5"
                    )
                
                instance = instances[0]
                
                # Convert to prediction format
                prediction_dict = self.convert_to_prediction_format(data_point)
                
                # Format predictions dict: {instance_id: {model_name_or_path: ..., model_patch: ...}}
                # run_instances expects predictions to be dicts, not strings
                predictions = {
                    instance_id: {
                        "model_name_or_path": "golden",
                        "model_patch": prediction_dict["patch"],
                    }
                }
                
                # Call run_instances with correct signature
                # run_instances expects: predictions (dict), instances (list), and other params
                run_id = f"validation-{instance_id}"
                model_name = "golden"  # Match the model_name_or_path in predictions
                try:
                    run_evaluation(
                        predictions=predictions,
                        instances=[instance],
                        cache_level="none",  # Don't cache for validation
                        clean=False,
                        force_rebuild=True,  # Build images locally instead of pulling
                        max_workers=1,  # Single instance validation
                        run_id=run_id,
                        timeout=self.config.default_timeout,
                        namespace=self.config.swe_bench_tasks,
                    )
                except Exception as run_error:
                    # run_instances might fail, but we still want to check if logs were written
                    # Store the error to include in the final error message if log parsing fails
                    run_error_msg = str(run_error)
                    if self.config.verbose:
                        console.print(
                            f"[yellow]Warning: run_instances raised an exception: {run_error_msg}[/yellow]"
                        )
                    # Continue to try to read logs - sometimes partial logs are written
                    # But if it's a Docker image build error, we'll catch it below
                
                # Parse results from log files
                # run_instances writes logs, we need to parse them
                if get_eval_report is None or make_test_spec is None:
                    raise ExecutionError(
                        "get_eval_report or make_test_spec not available. "
                        "Please ensure swebench>=4.0.4 is installed."
                    )
                
                # Get log path
                import os
                # Use RUN_EVALUATION_LOG_DIR if available, otherwise use log_dir
                if RUN_EVALUATION_LOG_DIR:
                    log_base_dir = RUN_EVALUATION_LOG_DIR
                else:
                    log_base_dir = str(self.log_dir)
                
                # Log path structure: logs/run_evaluation/{run_id}/{model_name}/{instance_id}/test_output.log
                # Or sometimes: logs/run_evaluation/{run_id}/{model_name}/{instance_id}/run_instance.log
                test_log_path = os.path.join(
                    log_base_dir, run_id, model_name, instance_id, "test_output.log"
                )
                
                # Check if log file exists (run_instances might have failed)
                if not os.path.exists(test_log_path):
                    # Try alternative log locations and file names
                    alt_paths = [
                        # Standard path with test_output.log
                        os.path.join(log_base_dir, run_id, model_name, instance_id, "test_output.log"),
                        # Alternative with run_instance.log (might contain test output)
                        os.path.join(log_base_dir, run_id, model_name, instance_id, "run_instance.log"),
                        # Flattened paths
                        os.path.join(log_base_dir, run_id, f"{instance_id}.test_output.log"),
                        os.path.join(log_base_dir, f"{instance_id}.test_output.log"),
                        os.path.join(self.log_dir, run_id, model_name, instance_id, "test_output.log"),
                        os.path.join(self.log_dir, run_id, f"{instance_id}.test_output.log"),
                        os.path.join(self.log_dir, f"{instance_id}.test_output.log"),
                    ]
                    found = False
                    for alt_path in alt_paths:
                        if os.path.exists(alt_path):
                            test_log_path = alt_path
                            found = True
                            break
                    
                    if not found:
                        # List what files actually exist for debugging
                        log_dir = os.path.join(log_base_dir, run_id, model_name, instance_id)
                        existing_files = []
                        if os.path.exists(log_dir):
                            existing_files = os.listdir(log_dir)
                        
                        # Check if there's a run_instance.log that might have error info
                        run_instance_log = os.path.join(log_dir, "run_instance.log")
                        error_details = ""
                        if os.path.exists(run_instance_log):
                            try:
                                with open(run_instance_log, 'r') as f:
                                    log_content = f.read()
                                    # Extract error messages from log
                                    if "Error" in log_content or "Exception" in log_content:
                                        # Get last few lines with errors
                                        lines = log_content.split('\n')
                                        error_lines = [l for l in lines if any(kw in l for kw in ['Error', 'Exception', 'Failed', '404'])]
                                        if error_lines:
                                            error_details = "\n\nDocker/Execution errors from log:\n" + "\n".join(error_lines[-10:])
                            except Exception:
                                pass
                        
                        # Include run_error if available
                        run_error_info = ""
                        if 'run_error_msg' in locals():
                            run_error_info = f"\n\nRun error: {run_error_msg}"
                        
                        raise ExecutionError(
                            f"Evaluation log file not found. Expected at: {test_log_path}\n"
                            f"Tried alternative paths: {alt_paths}\n"
                            f"Files in log directory ({log_dir}): {existing_files}"
                            f"{error_details}"
                            f"{run_error_info}\n"
                            f"\nThis usually means run_instances failed before writing test logs. "
                            f"Common causes:\n"
                            f"  - Docker image build/pull failed (check Docker is running)\n"
                            f"  - Missing base Docker images (may need to build them first)\n"
                            f"  - Network issues preventing image download\n"
                            f"Check the run_instance.log file for detailed error information."
                        )
                
                # Create test spec from instance
                test_spec = make_test_spec(instance)
                
                # Format prediction for get_eval_report
                eval_prediction = {
                    "instance_id": instance_id,
                    "model_name_or_path": "golden",
                    "model_patch": prediction_dict["patch"],
                }
                
                # Check if log file contains build errors before trying to parse
                run_instance_log = os.path.join(log_base_dir, run_id, model_name, instance_id, "run_instance.log")
                build_failed = False
                if os.path.exists(run_instance_log):
                    try:
                        with open(run_instance_log, 'r') as f:
                            log_content = f.read()
                            # Check for Docker build errors
                            if "BuildImageError" in log_content or "Error building image" in log_content:
                                build_failed = True
                                # Extract the error message
                                if "BuildImageError" in log_content:
                                    error_match = log_content.split("BuildImageError")[-1].split("\n")[0:3]
                                    build_error = "\n".join(error_match).strip()
                                else:
                                    build_error = "Docker image build failed - see run_instance.log for details"
                    except Exception:
                        pass
                
                if build_failed:
                    raise ExecutionError(
                        f"Docker image build failed for {instance_id}.\n"
                        f"SWE-bench tried to pull/build the Docker image but failed.\n"
                        f"This is expected on first run - SWE-bench needs to build images from scratch.\n\n"
                        f"To fix this:\n"
                        f"  1. Ensure Docker is running: docker ps\n"
                        f"  2. Check you have sufficient disk space (images can be several GB)\n"
                        f"  3. The first run may take 10-30 minutes to build images\n"
                        f"  4. Check logs at: {run_instance_log}\n\n"
                        f"Note: SWE-bench will attempt to build images locally when pre-built images aren't available.\n"
                        f"This is normal behavior and the build will happen automatically on first run."
                    )
                
                # Get evaluation report
                eval_report = get_eval_report(
                    test_spec=test_spec,
                    prediction=eval_prediction,
                    test_log_path=test_log_path,
                    include_tests_status=True,
                )
                
                # Convert to format expected by validate_evaluation_results
                # get_eval_report returns a dict with keys like "tests" containing test results
                # Format: {instance_id: {test_name: {status: "PASS"/"FAIL", ...}}}
                test_results = eval_report.get("tests", {})
                
                # Check if all tests have UNKNOWN status (indicates tests didn't run)
                if test_results:
                    unknown_count = sum(
                        1 for test_result in test_results.values()
                        if (isinstance(test_result, dict) and 
                            str(test_result.get("status", "")).upper() == "UNKNOWN")
                        or (not isinstance(test_result, dict) and str(test_result).upper() == "UNKNOWN")
                    )
                    if unknown_count == len(test_results):
                        # All tests are UNKNOWN - container likely didn't run
                        raise ExecutionError(
                            f"All tests returned UNKNOWN status for {instance_id}.\n"
                            f"This usually means the Docker container failed to run or tests didn't execute.\n"
                            f"Check the run_instance.log file for Docker/build errors:\n"
                            f"  {run_instance_log}\n\n"
                            f"Common causes:\n"
                            f"  - Docker image build failed (check logs above)\n"
                            f"  - Container failed to start\n"
                            f"  - Test execution was interrupted\n"
                        )
                
                evaluation_results = {
                    instance_id: test_results
                }
                
            except Exception as e:
                raise ExecutionError(
                    f"Docker evaluation failed for {instance_id}: {str(e)}\n"
                    f"Traceback: {traceback.format_exc()}"
                ) from e

            # Validate results
            is_valid, validation_errors = self.validate_evaluation_results(
                data_point, evaluation_results
            )

            if validation_errors:
                errors.extend(validation_errors)
            else:
                if self.config.verbose:
                    console.print(
                        f"[green]✓ All tests passed for {instance_id}[/green]"
                    )

        except StructuralError as e:
            errors.append(f"Structural error: {str(e)}")
        except ExecutionError as e:
            errors.append(f"Execution error: {str(e)}")
        except Exception as e:
            errors.append(
                f"Unexpected error: {str(e)}\nTraceback: {traceback.format_exc()}"
            )

        success = len(errors) == 0
        return ValidationResult(
            instance_id=instance_id,
            file_path=file_path,
            success=success,
            errors=errors,
            warnings=warnings,
            evaluation_results=evaluation_results,
        )

    def validate_directory(
        self, directory: Path, pattern: str = "*.json"
    ) -> List[ValidationResult]:
        """
        Validate all data point files in a directory.

        Args:
            directory: Directory containing data point JSON files.
            pattern: File pattern to match (default: "*.json").

        Returns:
            List of ValidationResult objects.
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        json_files = sorted(directory.glob(pattern))
        if not json_files:
            console.print(f"[yellow]No JSON files found in {directory}[/yellow]")
            return []

        results = []
        for file_path in json_files:
            result = self.validate_file(file_path)
            results.append(result)

            if not result.success and not self.config.continue_on_error:
                console.print(
                    f"[red]Validation failed for {result.instance_id}. "
                    f"Stopping (use --continue-on-error to continue).[/red]"
                )
                break

        return results

