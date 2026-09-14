"""In-guest HTTP agent service running on port 9000 inside the VM."""

from __future__ import annotations

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from kage.guest.atspi_tree import AccessibilityTreeParser
from kage.guest.input_synth import InputSynthesizer
from kage.guest.screen import ScreenCapture
from kage.guest.shell_exec import GuestShellExecutor

START_TIME = time.time()


class GuestAgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for in-guest agent bridge."""

    def _set_headers(self, content_type: str = "application/json", status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(status=204)

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            return {}

    def _send_json(self, data: Any, status: int = 200):
        self._set_headers("application/json", status=status)
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health" or path == "/":
            self._send_json(
                {
                    "status": "ok",
                    "uptime": round(time.time() - START_TIME, 1),
                    "service": "kage-guest-agent",
                }
            )

        elif path == "/gui/tree":
            try:
                tree = AccessibilityTreeParser.get_tree()
                self._send_json(
                    {
                        "tree": tree.to_dict(),
                        "compact_text": tree.to_compact_str(),
                    }
                )
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)

        elif path == "/gui/screenshot":
            query = parse_qs(parsed.query)
            as_base64 = query.get("format", ["binary"])[0] == "base64"

            try:
                cap = ScreenCapture()
                if as_base64:
                    b64 = cap.capture_base64()
                    self._send_json({"screenshot_base64": b64})
                else:
                    raw_png = cap.capture()
                    self._set_headers("image/png", status=200)
                    self.wfile.write(raw_png)
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)

        else:
            self._send_json({"error": f"Endpoint not found: {path}"}, status=404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_json_body()

        if path == "/shell/exec":
            cmd = body.get("command") or body.get("cmd", "")
            cwd = body.get("cwd")
            timeout = float(body.get("timeout", 60.0))
            env = body.get("env")

            if not cmd:
                self._send_json({"error": "Missing 'command' in request body"}, status=400)
                return

            res = GuestShellExecutor.execute(cmd, cwd=cwd, env=env, timeout=timeout)
            self._send_json(res)

        elif path == "/gui/click":
            x = body.get("x")
            y = body.get("y")
            button = int(body.get("button", 1))
            double = bool(body.get("double", False))

            synth = InputSynthesizer()
            success = synth.mouse_click(x=x, y=y, button=button, double=double)
            self._send_json({"success": success, "clicked_at": {"x": x, "y": y}})

        elif path == "/gui/type":
            text = body.get("text")
            keys = body.get("keys")
            delay_ms = int(body.get("delay_ms", 12))

            synth = InputSynthesizer()
            success = True
            if text:
                success = synth.type_text(text, delay_ms=delay_ms)
            if keys:
                success = success and synth.key_combo(keys)

            self._send_json({"success": success})

        elif path == "/gui/drag":
            start_x = int(body.get("start_x", 0))
            start_y = int(body.get("start_y", 0))
            end_x = int(body.get("end_x", 0))
            end_y = int(body.get("end_y", 0))

            synth = InputSynthesizer()
            success = synth.mouse_drag(start_x, start_y, end_x, end_y)
            self._send_json({"success": success})

        elif path == "/gui/scroll":
            direction = body.get("direction", "down")
            clicks = int(body.get("clicks", 3))

            synth = InputSynthesizer()
            success = synth.scroll(direction=direction, clicks=clicks)
            self._send_json({"success": success})

        else:
            self._send_json({"error": f"Endpoint not found: {path}"}, status=404)

    def log_message(self, format, *args):
        # Quiet default logging
        pass


def run_guest_agent(port: int = 9000, host: str = "0.0.0.0"):
    """Run the in-guest HTTP agent server."""
    server_addr = (host, port)
    httpd = HTTPServer(server_addr, GuestAgentHandler)
    print(f"[kage-guest-agent] Listening on {host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_guest_agent()
