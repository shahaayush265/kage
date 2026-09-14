# Kage Architecture & Subsystem Specification

Kage is engineered as a high-density, low-latency virtualization engine designed specifically for autonomous AI agents and OS-world automation benchmarks.

---

## 1. High-Level Architecture

```
                                  +-------------------------------------------------------------+
                                  |                     Kage CLI / Web App                      |
                                  |       (kage init | up | list | connect | shell | agent)     |
                                  +------------------------------+------------------------------+
                                                                 |
                                                                 v
                                  +-------------------------------------------------------------+
                                  |                    Host Bridge API Server                   |
                                  |              (FastAPI + WebSockets + noVNC Proxy)           |
                                  +---------------+------------------------------+--------------+
                                                  |                              |
                                                  v                              v
+---------------------------------------------------+      +------------------------------------+
|               LiteLLM Agent Loop                  |      |         QEMU/KVM Orchestrator      |
|  - Tool calling (shell, click, tree, screenshot)  |      |  - Copy-on-Write Qcow2 Overlays    |
|  - Vision + Accessibility Hybrid Grounding        |      |  - Dynamic Port Allocation         |
|  - Multi-provider (Claude, OpenAI, Ollama, etc.)  |      |  - Virtio-fs / 9p Shared Folder    |
+---------------------------------------------------+      |  - Cloud-Init NoCloud Generation   |
                                                           +-----------------+------------------+
                                                                             |
                                                                             v
+-----------------------------------------------------------------------------------------------+
|                                     Guest VM Instance (QEMU)                                  |
|                                                                                               |
|  +-------------------------------------------------+     +---------------------------------+  |
|  |           XFCE4 Desktop Session                 |     |       In-Guest Agent Bridge     |  |
|  |  - X11 Display (:0)                             | <-> |  - AT-SPI2 Accessibility Tree   |  |
|  |  - TigerVNC / x11vnc -> noVNC (Host)            |     |  - xdotool Input Synthesizer    |  |
|  |  - Mounted /workspace (Virtio-9p)               |     |  - maim Screenshot Engine       |  |
|  |                                                 |     |  - Sandboxed Shell Execution    |  |
|  +-------------------------------------------------+     +---------------------------------+  |
+-----------------------------------------------------------------------------------------------+
```

---

## 2. Subsystem Deep-Dive

### 2.1 Hypervisor Orchestrator & Storage Layer
- **Copy-on-Write Qcow2 Backing Chains**:
  Each VM instance runs on top of a shared, read-only base Ubuntu 24.04 XFCE image. When an instance is provisioned with `kage up`, Kage generates an overlay qcow2 file in `~/.kage/instances/<name>/overlay.qcow2`.
  - Initial disk overhead per instance: **~5 MB**.
  - Spin-up latency: **< 3 seconds**.
  - Zero pollution of base image.
- **Pure-Python Cloud-Init NoCloud ISO Builder**:
  Kage generates an in-memory ISO 9660 filesystem with volume ID `CIDATA` containing `user-data` and `meta-data`. This eliminates external packaging dependencies (`genisoimage`, `xorriso`, `cloud-localds`) across Linux and macOS.
- **Shared Folder Mapping**:
  Host directories are mounted into the guest VM using Virtio-9p (`-device virtio-9p-pci`). Inside the guest, `/workspace` is mapped to the host folder.

### 2.2 In-Guest Agent Bridge (`kage-guest-agent`)
A lightweight HTTP/socket daemon runs inside the VM on port 9000, exposing the following capabilities:
- **AT-SPI2 Accessibility Tree Parser**: Queries the active GUI hierarchy, translating desktop widgets, buttons, and windows into structured JSON with bounding boxes and node IDs.
- **Input Synthesizer**: Uses `xdotool` to simulate mouse movements, clicks, double clicks, drags, text typing, and key combinations.
- **Screen Capture**: Uses `maim` for fast full-resolution screen grabs without rasterization lag.
- **Sandboxed Shell**: Executes commands in `/bin/bash` with stdout/stderr streaming and status reporting.

### 2.3 Host Bridge API Server (FastAPI)
Spawns per instance or as a unified daemon:
- `GET /api/v1/instances` — Lists all registered instances and live resource consumption (CPU %, RSS Memory, Uptime).
- `POST /api/v1/instances/{name}/shell/exec` — Executes bash commands inside the guest.
- `GET /api/v1/instances/{name}/gui/tree` — Retrieves structured accessibility tree.
- `POST /api/v1/instances/{name}/gui/click` — Synthesizes mouse clicks by (x, y) coordinates or node ID.
- `GET /api/v1/instances/{name}/gui/screenshot` — Returns PNG screenshot.
- `WS /ws/vnc/{name}` — Native async WebSocket-to-TCP proxy streaming VNC to the browser without external websockify binaries.

### 2.4 LLM Routing & ReAct Agent Engine
- **Multi-Provider Support**: Uses LiteLLM to seamlessly route to Claude 3.7 Sonnet, GPT-4o, DeepSeek, and local models (Ollama/vLLM).
- **Dual-Grounding Loop**: Combines visual feedback (screenshots) with semantic hierarchy (AT-SPI2 node IDs) so agents can reliably click elements without relying purely on pixel coordinate estimation.
