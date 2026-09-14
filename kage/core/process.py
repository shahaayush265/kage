"""Process lifecycle, daemonization, monitoring, and resource metrics."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import psutil

from kage.core.instance import InstanceMetrics


class ProcessManager:
    """Utilities for managing background daemons, monitoring, and shutdown."""

    @staticmethod
    def is_alive(pid: Optional[int]) -> bool:
        """Check if process with given PID is currently active."""
        if pid is None or pid <= 0:
            return False
        try:
            p = psutil.Process(pid)
            return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False

    @staticmethod
    def get_metrics(pid: Optional[int]) -> InstanceMetrics:
        """Fetch resource usage metrics (CPU %, RSS memory MB, uptime) for a process."""
        if not ProcessManager.is_alive(pid):
            return InstanceMetrics()

        try:
            assert pid is not None
            p = psutil.Process(pid)
            cpu = p.cpu_percent(interval=None)
            mem_info = p.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)

            # Include children if any (e.g. QEMU child threads or subprocesses)
            for child in p.children(recursive=True):
                try:
                    cpu += child.cpu_percent(interval=None)
                    rss_mb += child.memory_info().rss / (1024 * 1024)
                except Exception:
                    pass

            uptime = time.time() - p.create_time()
            return InstanceMetrics(
                cpu_percent=round(cpu, 1),
                memory_rss_mb=round(rss_mb, 1),
                uptime_seconds=round(uptime, 1),
            )
        except Exception:
            return InstanceMetrics()

    @staticmethod
    def spawn_daemon(
        cmd: List[str],
        log_file: Path,
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
    ) -> int:
        """Spawn a detached background daemon process redirecting output to log_file."""
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode
        out_f = open(log_file, "a", encoding="utf-8")

        proc_env = os.environ.copy()
        if env:
            proc_env.update(env)

        proc = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            cwd=str(cwd) if cwd else None,
            env=proc_env,
            start_new_session=True,  # Detach process group
            close_fds=True,
        )
        return proc.pid

    @staticmethod
    def stop_process(pid: Optional[int], timeout_seconds: float = 5.0) -> bool:
        """Terminate a process gracefully with SIGTERM, escalating to SIGKILL on timeout."""
        if not ProcessManager.is_alive(pid):
            return True

        assert pid is not None
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # Send SIGTERM to children first, then parent
            for child in children:
                try:
                    child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            parent.terminate()

            # Wait for process to exit
            gone, alive = psutil.wait_procs(children + [parent], timeout=timeout_seconds)
            if not alive:
                return True

            # Escalate to SIGKILL for any remaining processes
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            gone, alive = psutil.wait_procs(alive, timeout=2.0)
            return len(alive) == 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return True
        except Exception:
            # Fallback to direct os.kill
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except OSError:
                return False
