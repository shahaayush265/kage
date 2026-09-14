# Kage Host Bridge API Reference

The Host Bridge API provides a standardized REST and WebSocket interface for programmatic VM orchestration, GUI automation, and agent tool-calling.

Interactive Swagger documentation is available at `http://127.0.0.1:<api_port>/docs`.

---

## Endpoints

### 1. Instances Lifecycle

#### `GET /api/v1/instances`
List all instances with runtime status, ports, and resource consumption.

#### `GET /api/v1/instances/{name}`
Retrieve full state record and resource metrics (CPU %, RSS Memory MB, Uptime).

#### `POST /api/v1/instances/{name}/stop`
Halt an active instance cleanly.

---

### 2. Shell Execution

#### `POST /api/v1/instances/{name}/shell/exec`
Execute a bash command in the guest VM.

**Request Body:**
```json
{
  "command": "uname -a",
  "cwd": "/home/kage",
  "timeout": 30.0
}
```

**Response Body:**
```json
{
  "stdout": "Linux alpha 6.8.0 #1 SMP x86_64\n",
  "stderr": "",
  "exit_code": 0,
  "duration": 0.04,
  "timed_out": false
}
```

---

### 3. GUI Automation & Accessibility

#### `GET /api/v1/instances/{name}/gui/tree`
Retrieve the AT-SPI2 accessibility tree hierarchy of the active desktop.

**Response Body:**
```json
{
  "tree": {
    "node_id": "root",
    "name": "Desktop",
    "role": "desktop",
    "children": [
      {
        "node_id": "node_1",
        "name": "Terminal",
        "role": "window",
        "bounds": {"x": 100, "y": 100, "width": 800, "height": 500},
        "center": {"x": 500, "y": 350}
      }
    ]
  },
  "compact_text": "- [root] <desktop> [0,0,1280x800]\n  - [node_1] <window> \"Terminal\" [100,100,800x500]"
}
```

#### `POST /api/v1/instances/{name}/gui/click`
Synthesize a mouse click by coordinates `(x, y)` or `node_id`.

**Request Body:**
```json
{
  "node_id": "node_1",
  "button": 1,
  "double": false
}
```

#### `POST /api/v1/instances/{name}/gui/type`
Type text or send key combinations.

**Request Body:**
```json
{
  "text": "echo 'Hello World'",
  "keys": ["Return"]
}
```

#### `GET /api/v1/instances/{name}/gui/screenshot?format=binary|base64`
Capture a desktop screenshot.

---

### 4. VNC WebSocket Streaming

#### `WS /ws/vnc/{name}`
Bidirectional binary WebSocket forwarding directly to the VM's VNC backend for noVNC desktop clients.
