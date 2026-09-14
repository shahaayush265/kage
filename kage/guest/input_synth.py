"""X11 input synthesis engine using xdotool for mouse and keyboard control."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import List, Optional, Union


class InputSynthesizer:
    """Controls mouse and keyboard inputs via xdotool."""

    def __init__(self, display: str = ":0"):
        self.display = display

    def _get_env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        if "XAUTHORITY" not in env:
            home_auth = os.path.expanduser("~/.Xauthority")
            if os.path.exists(home_auth):
                env["XAUTHORITY"] = home_auth
            else:
                import glob

                auth_files = sorted(
                    glob.glob("/tmp/serverauth.*"), key=os.path.getmtime, reverse=True
                )
                if auth_files:
                    env["XAUTHORITY"] = auth_files[0]
        return env

    def _run_xdotool(self, args: List[str]) -> bool:
        if not shutil.which("xdotool"):
            raise RuntimeError("xdotool is not installed on system")

        cmd = ["xdotool"] + args
        res = subprocess.run(
            cmd,
            env=self._get_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return res.returncode == 0

    def mouse_move(self, x: int, y: int) -> bool:
        """Move mouse pointer to (x, y)."""
        return self._run_xdotool(["mousemove", "--sync", str(x), str(y)])

    def mouse_click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: int = 1,
        double: bool = False,
    ) -> bool:
        """Click mouse button at current or specified coordinate."""
        args: List[str] = []
        if x is not None and y is not None:
            args.extend(["mousemove", "--sync", str(x), str(y)])

        if double:
            args.extend(["click", "--repeat", "2", "--delay", "100", str(button)])
        else:
            args.extend(["click", str(button)])

        return self._run_xdotool(args)

    def mouse_down(self, button: int = 1) -> bool:
        """Press and hold mouse button."""
        return self._run_xdotool(["mousedown", str(button)])

    def mouse_up(self, button: int = 1) -> bool:
        """Release mouse button."""
        return self._run_xdotool(["mouseup", str(button)])

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """Drag from (start_x, start_y) to (end_x, end_y)."""
        self.mouse_move(start_x, start_y)
        time.sleep(0.05)
        self.mouse_down(1)
        time.sleep(0.05)
        self.mouse_move(end_x, end_y)
        time.sleep(0.05)
        self.mouse_up(1)
        return True

    def type_text(self, text: str, delay_ms: int = 12) -> bool:
        """Type arbitrary text with optional key delay."""
        return self._run_xdotool(["type", "--delay", str(delay_ms), text])

    def key_combo(self, keys: Union[str, List[str]]) -> bool:
        """Send key press or key combination (e.g. 'ctrl+c', 'Return', 'alt+F4')."""
        if isinstance(keys, list):
            combo = "+".join(keys)
        else:
            combo = keys
        return self._run_xdotool(["key", combo])

    def scroll(self, direction: str = "down", clicks: int = 3) -> bool:
        """Scroll mouse wheel up or down."""
        btn = 5 if direction.lower() == "down" else 4
        args = ["click", "--repeat", str(clicks), str(btn)]
        return self._run_xdotool(args)
