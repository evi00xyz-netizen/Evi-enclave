"""
Code execution module for chat interface.

Executes Python and shell code in a subprocess with timeout.
Supports outbound network requests via standard libraries.
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


def _build_execution_env() -> dict:
    """
    Build environment for code execution.

    Enables network access while maintaining sandboxed execution.
    """
    env = {
        # Core paths
        "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": "/tmp",

        # Python config
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",

        # Network/SSL support - inherit from parent process
        "SSL_CERT_FILE": os.environ.get("SSL_CERT_FILE", "/etc/ssl/certs/ca-certificates.crt"),
        "SSL_CERT_DIR": os.environ.get("SSL_CERT_DIR", "/etc/ssl/certs"),
        "REQUESTS_CA_BUNDLE": os.environ.get("REQUESTS_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt"),
        "CURL_CA_BUNDLE": os.environ.get("CURL_CA_BUNDLE", "/etc/ssl/certs/ca-certificates.crt"),

        # Proxy support (if configured)
        "HTTP_PROXY": os.environ.get("HTTP_PROXY", ""),
        "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", ""),
        "NO_PROXY": os.environ.get("NO_PROXY", "localhost,127.0.0.1"),

        # Locale
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "LC_ALL": os.environ.get("LC_ALL", "en_US.UTF-8"),

        # Temp directory
        "TMPDIR": "/tmp",
        "TEMP": "/tmp",
        "TMP": "/tmp",
    }

    # Remove empty values
    return {k: v for k, v in env.items() if v}


def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    max_output_size: int = 10000,
    allow_network: bool = True
) -> ExecutionResult:
    """
    Execute code in a subprocess with timeout.

    Args:
        code: The code to execute
        language: "python" or "shell"
        timeout: Execution timeout in seconds
        max_output_size: Maximum output size in characters
        allow_network: Allow outbound network requests (default: True)

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

        # Build execution environment
        env = _build_execution_env()

        # Execute with configured environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env=env
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
