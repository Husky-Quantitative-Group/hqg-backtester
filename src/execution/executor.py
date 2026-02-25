# executor.py
import os
import subprocess
import logging

from ..models.request import BacktestRequestError
from ..models.execution import ExecutionPayload, RawExecutionResult
from ..config.settings import settings

logger = logging.getLogger(__name__)

DOCKER_IMAGE = "hqg-backtester-sandbox"

class Executor:
    """
    Runs validated user strategies inside a hardened Docker container.
    Communicates via stdin/stdout JSON.
    """

    def __init__(self, image: str = DOCKER_IMAGE, timeout: int = settings.MAX_EXECUTION_TIME):
        self.image = image
        self.timeout = timeout

    def execute(self, payload: ExecutionPayload) -> RawExecutionResult:
        """
        Spawn a Docker container, send ExecutionPayload via stdin,
        read RawExecutionResult from stdout.
        """
        errors = BacktestRequestError()
        payload_json = payload.model_dump_json()

        profile = os.environ.get("HQG_PROFILE", "0")

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
            "-e", f"HQG_PROFILE={profile}",
            self.image,
            "python", "-m", "src.execution.container.entrypoint",  # run our execution container, not the web-app
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
                if "CONTAINER PROFILE" in result.stderr:
                    logger.info(f"Container stderr:\n{result.stderr}")
                else:
                    logger.warning(f"Container stderr: {result.stderr[:500]}")

            if not result.stdout.strip():
                errors.add(f"Container returned empty output. stderr: {result.stderr[:500]}")
                return RawExecutionResult(
                    trades=[],
                    equity_curve={},
                    ohlc={},
                    final_value=0.0,
                    final_cash=0.0,
                    final_positions={},
                    execution_time=0.0,
                    errors=errors,
                    bar_size=payload.bar_size
                )

            return RawExecutionResult.model_validate_json(result.stdout)

        except subprocess.TimeoutExpired:
            errors.add(f"Container timed out after {self.timeout}s")
            return RawExecutionResult(
                trades=[],
                equity_curve={},
                ohlc={},
                final_value=0.0,
                final_cash=0.0,
                final_positions={},
                execution_time=0.0,
                errors=errors,
                bar_size=payload.bar_size
            )
        except Exception as e:
            errors.add(f"Container execution failed: {str(e)}")
            return RawExecutionResult(
                trades=[],
                equity_curve={},
                ohlc={},
                final_value=0.0,
                final_cash=0.0,
                final_positions={},
                execution_time=0.0,
                errors=errors,
                bar_size=payload.bar_size
            )
