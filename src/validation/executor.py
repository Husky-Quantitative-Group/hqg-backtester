# executor.py
import subprocess
import logging
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "hqg-backtester-sandbox"
CONTAINER_TIMEOUT = 300  # 5 minutes


class ExecutionPayload(BaseModel):
    strategy_code: str = Field(..., description="Raw Python strategy code to execute", min_length=10)
    name: Optional[str] = Field(default="Unnamed Backtest", description="Name for this backtest run")
    start_date: datetime
    end_date: datetime
    initial_capital: float = Field(default=100000.0, description="Starting cash of Python strategy", gt=0)
    market_data: Dict[str, Any] = Field(..., description="Pre-fetched OHLC data")


class RawExecutionResult(BaseModel):

    trades: List[Dict[str, Any]] = Field(default_factory=list, description="Raw trade data")
    equity_curve: Dict[str, float] = Field(default_factory=dict, description="Timestamp -> equity mapping")
    ohlc: Dict[str, Dict[str, float]] = Field(default_factory=dict, description="Timestamp -> portfolio OHLC")
    final_value: float = Field(..., description="Final portfolio value")
    final_cash: float = Field(..., description="Final cash balance")
    final_positions: Dict[str, float] = Field(default_factory=dict, description="Final positions held")

    execution_time: Optional[float] = Field(default=None, description="Execution time in seconds")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered during execution")


class Executor:
    """
    Runs validated user strategies inside a hardened Docker container.
    Communicates via stdin/stdout JSON.
    """

    def __init__(self, image: str = DOCKER_IMAGE, timeout: int = CONTAINER_TIMEOUT):
        self.image = image
        self.timeout = timeout

    def execute(self, payload: ExecutionPayload) -> RawExecutionResult:
        """
        Spawn a Docker container, send ExecutionPayload via stdin,
        read RawExecutionResult from stdout.
        """
        payload_json = payload.model_dump_json()

        cmd = [
            "docker", "run",
            "--rm",                         # remove container after exit
            "--interactive",                # keep stdin open
            "--network=none",               # no network access
            "--read-only",                  # read-only filesystem
            "--tmpfs", "/tmp:size=64m",     # small writable /tmp
            "--memory=512m",                # memory limit
            "--cpus=1",                     # cpu limit
            "--pids-limit=64",              # process limit
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",
            self.image,
        ]

        logger.info(f"Spawning container with image {self.image}")

        try:
            result = subprocess.run(
                cmd,
                input=payload_json,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.stderr:
                logger.warning(f"Container stderr: {result.stderr[:500]}")

            if not result.stdout.strip():
                return RawExecutionResult(
                    final_value=0.0,
                    final_cash=0.0,
                    errors=[f"Container returned empty output. stderr: {result.stderr[:500]}"],
                )

            return RawExecutionResult.model_validate_json(result.stdout)

        except subprocess.TimeoutExpired:
            return RawExecutionResult(
                final_value=0.0,
                final_cash=0.0,
                errors=[f"Container timed out after {self.timeout}s"],
            )
        except Exception as e:
            return RawExecutionResult(
                final_value=0.0,
                final_cash=0.0,
                errors=[f"Container execution failed: {str(e)}"],
            )
