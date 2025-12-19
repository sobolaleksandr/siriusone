"""
Configuration management for the SWE-bench validator.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidatorConfig:
    """Configuration for data point validation."""

    # Timeout settings (in seconds)
    default_timeout: int = 600  # 10 minutes per instance
    timeout_per_test: int = 300  # 5 minutes per test
    
    # Evaluation settings
    log_dir: str = "./validation_logs"
    verbose: bool = False
    
    # SWE-bench dataset settings
    swe_bench_tasks: str = "swe-bench"
    
    # Docker namespace for pulling instance images
    # Set to None to build locally, or to a Docker Hub username to pull pre-built images
    # Can be overridden via DOCKER_NAMESPACE environment variable
    docker_namespace: Optional[str] = None  # None = build locally, "sobolav" = pull from Docker Hub
    
    # Error handling
    continue_on_error: bool = False  # Stop on first error or continue
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "ValidatorConfig":
        """Create config from dictionary."""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__annotations__})


# Default configuration instance
DEFAULT_CONFIG = ValidatorConfig()

