"""
Core validation logic for SWE-bench data points.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback

from rich.console import Console

try:
    from swebench.harness.run_evaluation import run_evaluation
    from swebench.harness.constants import SWEbenchInstance
except ImportError as e:
    raise ImportError(
        "SWE-bench library not installed. Install with: pip install swebench>=4.0.4"
    ) from e

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
        # run_evaluation may return results in different formats
        # Try to find results for this instance
        instance_results = {}
        if isinstance(evaluation_results, dict):
            # Direct instance_id key
            instance_results = evaluation_results.get(instance_id, {})
            # Or results might be nested under 'results' or similar
            if not instance_results and "results" in evaluation_results:
                instance_results = evaluation_results["results"].get(instance_id, {})
            # Or results might be a list of result dicts
            if not instance_results and isinstance(evaluation_results.get("results"), list):
                for result in evaluation_results["results"]:
                    if result.get("instance_id") == instance_id:
                        instance_results = result
                        break

        # Check FAIL_TO_PASS tests (should pass after patch)
        for test in fail_to_pass_tests:
            # Test results might be nested or flat
            test_result = instance_results.get(test, {})
            if not test_result and "test_results" in instance_results:
                test_result = instance_results["test_results"].get(test, {})
            
            # Check status - might be "PASS", "pass", True, or in different format
            status = test_result.get("status") if isinstance(test_result, dict) else None
            if status:
                status = str(status).upper()
            else:
                # Try alternative status fields
                status = str(test_result.get("result", test_result.get("passed", "UNKNOWN"))).upper()
            
            if status != "PASS" and status != "TRUE":
                error_msg = (
                    f"FAIL_TO_PASS test '{test}' did not pass. "
                    f"Status: {test_result.get('status', 'UNKNOWN')}"
                )
                if test_result.get("stderr"):
                    error_msg += f"\nError output: {test_result.get('stderr')[:500]}"
                errors.append(error_msg)

        # Check PASS_TO_PASS tests (should still pass)
        for test in pass_to_pass_tests:
            # Test results might be nested or flat
            test_result = instance_results.get(test, {})
            if not test_result and "test_results" in instance_results:
                test_result = instance_results["test_results"].get(test, {})
            
            # Check status - might be "PASS", "pass", True, or in different format
            status = test_result.get("status") if isinstance(test_result, dict) else None
            if status:
                status = str(status).upper()
            else:
                # Try alternative status fields
                status = str(test_result.get("result", test_result.get("passed", "UNKNOWN"))).upper()
            
            if status != "PASS" and status != "TRUE":
                error_msg = (
                    f"PASS_TO_PASS test '{test}' failed after patch. "
                    f"Status: {test_result.get('status', 'UNKNOWN')}"
                )
                if test_result.get("stderr"):
                    error_msg += f"\nError output: {test_result.get('stderr')[:500]}"
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

            # Convert to prediction format
            prediction = self.convert_to_prediction_format(data_point)

            # Run evaluation using SWE-bench harness
            if self.config.verbose:
                console.print(
                    f"[cyan]Running evaluation for {instance_id}...[/cyan]"
                )

            try:
                evaluation_results = run_evaluation(
                    instances=[prediction],
                    swe_bench_tasks=self.config.swe_bench_tasks,
                    log_dir=str(self.log_dir),
                    timeout=self.config.default_timeout,
                    verbose=self.config.verbose,
                )
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

