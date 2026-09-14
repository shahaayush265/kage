"""Sandboxed in-guest shell command execution."""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, Optional


class GuestShellExecutor:
    """Executes arbitrary bash commands inside the VM environment."""

    @classmethod
    def execute(
        cls,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Execute command in bash shell and return structured result."""
        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        start_time = time.time()
        try:
            proc = subprocess.run(
                ["/bin/bash", "-c", command],
                cwd=cwd or os.path.expanduser("~"),
                env=proc_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                start_new_session=True,
                check=False,
            )
            duration = time.time() - start_time
            return {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "exit_code": proc.returncode,
                "duration": round(duration, 3),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            return {
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": f"Command timed out after {timeout} seconds",
                "exit_code": 124,
                "duration": round(duration, 3),
                "timed_out": True,
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
                "duration": round(duration, 3),
                "timed_out": False,
            }
