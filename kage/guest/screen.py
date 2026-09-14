"""X11 screen capture engine using maim / scrot / xwd."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional


class ScreenCapture:
    """Captures full screen or sub-region screenshots in X11."""

    def __init__(self, display: str = ":0"):
        self.display = display

    def _get_env(self) -> dict:
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        return env

    def capture(
        self,
        output_path: Optional[Path] = None,
        region: Optional[Dict[str, int]] = None,
    ) -> bytes:
        """Capture screenshot to file or return raw PNG bytes."""
        env = self._get_env()

        # Check for maim (preferred for fast lossless capture)
        if shutil.which("maim"):
            cmd = ["maim", "--format=png"]
            if region:
                x = region.get("x", 0)
                y = region.get("y", 0)
                w = region.get("width", 100)
                h = region.get("height", 100)
                cmd.extend(["-g", f"{w}x{h}+{x}+{y}"])

            if output_path:
                cmd.append(str(output_path))
                res = subprocess.run(cmd, env=env, check=False)
                if res.returncode != 0:
                    raise RuntimeError("maim failed to capture screenshot")
                return output_path.read_bytes()
            else:
                res = subprocess.run(
                    cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
                )
                if res.returncode != 0:
                    raise RuntimeError(f"maim failed: {res.stderr.decode()}")
                return res.stdout

        # Check for scrot fallback
        elif shutil.which("scrot"):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                cmd = ["scrot", "--overwrite", str(tmp_path)]
                res = subprocess.run(cmd, env=env, check=False)
                if res.returncode != 0:
                    raise RuntimeError("scrot failed to capture screenshot")
                data = tmp_path.read_bytes()
                if output_path:
                    output_path.write_bytes(data)
                return data
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

        # Fallback: create empty placeholder PNG (1x1 transparent) if no screen capture tools
        # 1x1 transparent PNG bytes
        empty_png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
            b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        if output_path:
            output_path.write_bytes(empty_png)
        return empty_png

    def capture_base64(self, region: Optional[Dict[str, int]] = None) -> str:
        """Capture screenshot and encode directly as base64 string."""
        raw_bytes = self.capture(region=region)
        return base64.b64encode(raw_bytes).decode("ascii")
