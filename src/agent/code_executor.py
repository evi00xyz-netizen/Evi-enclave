"""
Code execution module for chat interface.

Executes Python and shell code in a subprocess with timeout.
"""

import subprocess
import tempfile
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionResult:
    """Result of code execution."""
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    max_output_size: int = 10000
) -> ExecutionResult:
    """
    Execute code in a subprocess with timeout.

    Args:
        code: The code to execute
        language: "python" or "shell"
        timeout: Execution timeout in seconds
        max_output_size: Maximum output size in characters

    Returns:
        ExecutionResult with stdout, stderr, exit_code, and timed_out flag
    """
    script_path: Optional[str] = None

    try:
        if language == "python":
            # Write Python code to temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False
            ) as f:
                f.write(code)
                script_path = f.name
            cmd = ["python3", script_path]

        elif language == "shell":
            cmd = ["bash", "-c", code]

        else:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=1
            )

        # Execute with restricted environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1"
            }
        )

        return ExecutionResult(
            stdout=result.stdout[:max_output_size],
            stderr=result.stderr[:max_output_size],
            exit_code=result.returncode
        )

    except subprocess.TimeoutExpired:
        return ExecutionResult(
            stdout="",
            stderr=f"Execution timed out after {timeout} seconds",
            exit_code=-1,
            timed_out=True
        )

    except Exception as e:
        return ExecutionResult(
            stdout="",
            stderr=f"Execution error: {str(e)}",
            exit_code=-1
        )

    finally:
        # Clean up temp file
        if script_path and os.path.exists(script_path):
            try:
                os.unlink(script_path)
            except Exception:
                pass
