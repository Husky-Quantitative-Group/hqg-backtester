"""
Docker runner for executing backtests in hardened containers.
"""

import subprocess
import json
import os
from pathlib import Path
from datetime import datetime


def run_backtest_in_docker(
    code: str,
    tickers: list[str],
    start_date: datetime,
    end_date: datetime,
    initial_cash: float,
    commission_rate: float,
    parameters: dict | None = None,
    timeout: int = 300,  # 5 minutes default
):
    """
    Execute a backtest in a hardened Docker container.

    Args:
        code: Strategy code (Python string)
        tickers: List of ticker symbols
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_cash: Initial capital
        commission_rate: Commission rate (e.g., 0.005 for 0.5%)
        parameters: Optional parameters dict to pass to strategy
        timeout: Maximum execution time in seconds

    Returns:
        Results dict from backtest engine

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout
        RuntimeError: If Docker execution fails
        ValueError: If results cannot be parsed
    """
    # Get absolute path to data directory
    project_root = Path(__file__).parent.parent
    data_path = project_root / "data"

    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_path}")

    # Build Docker command with hardening flags
    cmd = [
        "docker", "run",
        "--rm",  # Remove container after execution
        "--network=none",  # No network access
        "--read-only",  # Immutable filesystem
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=256m",  # Writable temp (no exec)
        "--memory=512m",  # 512MB RAM limit
        "--memory-swap=512m",  # Disable swap
        "--cpus=1.0",  # 1 CPU core max
        "--pids-limit=100",  # Max 100 processes
        "--cap-drop=ALL",  # Drop all Linux capabilities
        "--security-opt=no-new-privileges",  # Prevent privilege escalation
        # Note: USER is set in Dockerfile, don't override here
        "-v", f"{data_path.absolute()}:/data:ro",  # Read-only data mount
        "-e", f"STRATEGY_CODE={code}",
        "-e", f"TICKERS={','.join(tickers)}",
        "-e", f"START_DATE={start_date.strftime('%Y-%m-%d')}",
        "-e", f"END_DATE={end_date.strftime('%Y-%m-%d')}",
        "-e", f"INITIAL_CASH={initial_cash}",
        "-e", f"COMMISSION_RATE={commission_rate}",
    ]

    # Add parameters if provided
    if parameters:
        cmd.extend(["-e", f"PARAMETERS={json.dumps(parameters)}"])

    # Add image name
    cmd.append("backtester-worker")

    try:
        # Run container with timeout
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # Don't raise on non-zero exit
        )

        # Parse JSON output
        if result.returncode != 0:
            # Try to parse error from stdout
            try:
                error_data = json.loads(result.stdout)
                raise RuntimeError(f"Backtest failed: {error_data.get('error', 'Unknown error')}")
            except json.JSONDecodeError:
                # Fallback to stderr
                raise RuntimeError(f"Docker execution failed: {result.stderr}")

        # Parse successful result
        try:
            backtest_results = json.loads(result.stdout)
            return backtest_results
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse results: {e}\nOutput: {result.stdout}")

    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired(
            cmd=cmd,
            timeout=timeout,
            output=f"Backtest execution exceeded {timeout} seconds"
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Docker not found. Make sure Docker is installed and running."
        )


def build_worker_image():
    """
    Build the worker Docker image.

    Returns:
        True if build successful

    Raises:
        RuntimeError: If build fails
    """
    project_root = Path(__file__).parent.parent

    cmd = [
        "docker", "build",
        "-f", str(project_root / "api" / "Dockerfile.worker"),
        "-t", "backtester-worker",
        str(project_root)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            raise RuntimeError(f"Docker build failed: {result.stderr}")

        return True

    except FileNotFoundError:
        raise RuntimeError("Docker not found. Make sure Docker is installed.")


def check_worker_image_exists():
    """
    Check if worker image exists.

    Returns:
        True if image exists, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "images", "-q", "backtester-worker"],
            capture_output=True,
            text=True,
            check=False
        )
        return bool(result.stdout.strip())
    except FileNotFoundError:
        return False
