"""
Command-line interface for the SWE-bench data point validator.
"""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .validator import DataPointValidator, ValidationError
from .config import ValidatorConfig, DEFAULT_CONFIG

console = Console()


@click.command()
@click.argument(
    "paths",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--timeout",
    type=int,
    default=None,
    help=f"Timeout per instance in seconds (default: {DEFAULT_CONFIG.default_timeout})",
)
@click.option(
    "--log-dir",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Directory for evaluation logs (default: {DEFAULT_CONFIG.log_dir})",
)
@click.option(
    "--continue-on-error",
    is_flag=True,
    help="Continue validating remaining files even if one fails",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output results as JSON",
)
def main(
    paths: tuple[Path, ...],
    timeout: int | None,
    log_dir: Path | None,
    continue_on_error: bool,
    verbose: bool,
    json_output: bool,
):
    """
    Validate SWE-bench data point JSON files.

    PATHS can be one or more files or directories containing JSON data points.

    Examples:

    \b
    # Validate a single file
    python -m swe_bench_validator data_points/astropy__astropy-11693.json

    \b
    # Validate all files in a directory
    python -m swe_bench_validator data_points/

    \b
    # Validate multiple files
    python -m swe_bench_validator data_points/*.json

    \b
    # Validate with custom timeout
    python -m swe_bench_validator --timeout 1200 data_points/
    """
    try:
        # Build configuration
        config_dict = {}
        if timeout is not None:
            config_dict["default_timeout"] = timeout
        if log_dir is not None:
            config_dict["log_dir"] = str(log_dir)
        config_dict["continue_on_error"] = continue_on_error
        config_dict["verbose"] = verbose

        config = ValidatorConfig.from_dict(config_dict) if config_dict else DEFAULT_CONFIG
        if config_dict:
            config.continue_on_error = continue_on_error
            config.verbose = verbose

        # Initialize validator
        validator = DataPointValidator(config)

        # Collect files to validate
        files_to_validate = []
        for path in paths:
            path = Path(path)
            if path.is_file():
                if path.suffix.lower() == ".json":
                    files_to_validate.append(path)
                else:
                    console.print(
                        f"[yellow]Skipping non-JSON file: {path}[/yellow]"
                    )
            elif path.is_dir():
                json_files = sorted(path.glob("*.json"))
                files_to_validate.extend(json_files)
            else:
                console.print(f"[red]Path does not exist: {path}[/red]")
                sys.exit(1)

        if not files_to_validate:
            console.print("[red]No JSON files found to validate[/red]")
            sys.exit(1)

        if verbose:
            console.print(
                f"[cyan]Found {len(files_to_validate)} file(s) to validate[/cyan]"
            )

        # Validate files
        results = []
        for file_path in files_to_validate:
            result = validator.validate_file(file_path)
            results.append(result)

            # Print result immediately
            if json_output:
                # JSON output will be printed at the end
                pass
            else:
                if result.success:
                    console.print(f"[green]✓[/green] {result}")
                else:
                    console.print(f"[red]✗[/red] {result}")
                    for error in result.errors:
                        console.print(f"  [red]Error:[/red] {error}")

            # Stop on error if not continuing
            if not result.success and not config.continue_on_error:
                break

        # Print summary
        if json_output:
            import json as json_lib

            output = {
                "total": len(results),
                "passed": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
                "results": [
                    {
                        "instance_id": r.instance_id,
                        "file": str(r.file_path),
                        "success": r.success,
                        "errors": r.errors,
                        "warnings": r.warnings,
                    }
                    for r in results
                ],
            }
            console.print(json_lib.dumps(output, indent=2))
        else:
            # Print summary table
            table = Table(title="Validation Summary", show_header=True, header_style="bold")
            table.add_column("Instance ID", style="cyan")
            table.add_column("File", style="white")
            table.add_column("Status", justify="center")
            table.add_column("Errors", justify="right")

            for result in results:
                status = "[green]✓ PASS[/green]" if result.success else "[red]✗ FAIL[/red]"
                error_count = len(result.errors)
                table.add_row(
                    result.instance_id,
                    result.file_path.name,
                    status,
                    str(error_count),
                )

            console.print()
            console.print(table)

            # Print overall summary
            passed = sum(1 for r in results if r.success)
            failed = len(results) - passed

            if failed == 0:
                console.print(
                    f"\n[bold green]✓ All {len(results)} data point(s) validated successfully![/bold green]"
                )
            else:
                console.print(
                    f"\n[bold red]✗ Validation failed: {failed} of {len(results)} data point(s) failed[/bold red]"
                )

        # Exit with appropriate code
        all_passed = all(r.success for r in results)
        sys.exit(0 if all_passed else 1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Validation interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[bold red]Fatal error:[/bold red] {str(e)}")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

