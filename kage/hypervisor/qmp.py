"""QEMU Machine Protocol (QMP) client for runtime control and clean shutdown."""

from __future__ import annotations

import json
import socket
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union


class QMPClient:
    """Client for communicating with QEMU via QMP JSON socket."""

    def __init__(self, socket_path: Union[str, Path], timeout: float = 3.0):
        self.socket_path = Path(socket_path)
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None

    def connect(self) -> None:
        """Connect to QMP socket and negotiate capabilities."""
        if not self.socket_path.exists():
            raise FileNotFoundError(f"QMP socket not found at '{self.socket_path}'")

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(self.timeout)
        self._sock.connect(str(self.socket_path))

        # Read greeting
        greeting = self._read_response()
        if "QMP" not in greeting:
            raise RuntimeError(f"Unexpected QMP greeting: {greeting}")

        # Enable capabilities
        res = self.execute("qmp_capabilities")
        if "error" in res:
            raise RuntimeError(f"Failed to enable QMP capabilities: {res}")

    def execute(self, command: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a QMP command and return the JSON response."""
        if self._sock is None:
            raise RuntimeError("QMPClient is not connected")

        payload: Dict[str, Any] = {"execute": command}
        if arguments:
            payload["arguments"] = arguments

        msg = json.dumps(payload) + "\r\n"
        self._sock.sendall(msg.encode("utf-8"))

        while True:
            resp = self._read_response()
            # Ignore async events (e.g. {"event": "..."})
            if "event" in resp and "return" not in resp and "error" not in resp:
                continue
            return resp

    def _read_response(self) -> Dict[str, Any]:
        """Read a single newline-delimited JSON line from socket."""
        assert self._sock is not None
        buf = bytearray()
        while True:
            chunk = self._sock.recv(1)
            if not chunk:
                raise ConnectionResetError("QMP connection closed by remote peer")
            if chunk == b"\n":
                line = buf.decode("utf-8").strip()
                if line:
                    return json.loads(line)
                continue
            buf.extend(chunk)

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def system_powerdown(self) -> Dict[str, Any]:
        """Trigger ACPI graceful shutdown."""
        return self.execute("system_powerdown")

    def quit(self) -> Dict[str, Any]:
        """Terminate QEMU immediately."""
        return self.execute("quit")

    def query_status(self) -> Dict[str, Any]:
        """Query current VM status (e.g. running, paused, shutdown)."""
        return self.execute("query-status")

    def __enter__(self) -> QMPClient:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def graceful_shutdown(socket_path: Union[str, Path], timeout_seconds: float = 10.0) -> bool:
    """Attempt ACPI shutdown via QMP, polling until QEMU process exits."""
    sock_p = Path(socket_path)
    if not sock_p.exists():
        return False

    try:
        with QMPClient(sock_p, timeout=2.0) as qmp:
            qmp.system_powerdown()
    except Exception:
        return False

    # Wait for socket to disappear or VM to stop
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        if not sock_p.exists():
            return True
        time.sleep(0.5)

    return False
