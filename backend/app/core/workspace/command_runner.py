import subprocess
import time

from app.shared.errors import ExecutionError
from app.shared.logging import get_logger

logger = get_logger(__name__)


async def run_command(
    command: str,
    cwd: str,
    timeout: int = 300,
    env: dict | None = None,
) -> dict:
    start_time = time.time()

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            shell=True,
            env=env,
        )
        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": duration_ms,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Command execution error: {e}")
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration_ms": duration_ms,
        }
