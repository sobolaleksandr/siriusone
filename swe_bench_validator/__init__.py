"""
SWE-bench Data Point Validator

A command-line tool for validating SWE-bench data points using the official
SWE-bench evaluation harness to ensure golden patches work correctly.
"""

__version__ = "0.1.0"

from .validator import DataPointValidator, ValidationResult, ValidationError
from .cli import main

__all__ = ["DataPointValidator", "ValidationResult", "ValidationError", "main"]

