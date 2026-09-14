"""Tests for process manager."""

import os
import sys

from kage.core.process import ProcessManager


def test_is_alive_and_stop(tmp_path):
    # Test with current process
    current_pid = os.getpid()
    assert ProcessManager.is_alive(current_pid)

    # Spawn a dummy process
    log_file = tmp_path / "proc.log"
    pid = ProcessManager.spawn_daemon(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        log_file=log_file,
    )
    assert ProcessManager.is_alive(pid)

    metrics = ProcessManager.get_metrics(pid)
    assert metrics.memory_rss_mb > 0

    # Terminate process
    stopped = ProcessManager.stop_process(pid, timeout_seconds=1.0)
    assert stopped
    assert not ProcessManager.is_alive(pid)
