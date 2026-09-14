# Execution Plan: Kage — The Multi-Instance Agentic VM Engine

## 1. Project Overview & Architecture

**Kage** (`kage`) is an open-source, production-grade CLI tool and orchestration engine for spinning up, managing, observing, and connecting autonomous AI agents to dedicated, local Linux GUI/shell virtual machines with single-line commands.

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

## 2. Target File Structure

```
kage/
├── pyproject.toml                     # Modern package config (Hatchling / setuptools entrypoint)
├── install.sh                         # Standalone one-line curl installer
├── README.md                          # Comprehensive docs, architecture diagrams, demo & quickstart
├── LICENSE                            # MIT License
├── docs/                              # In-depth technical documentation
│   ├── ARCHITECTURE.md                # Detailed subsystem breakdown
│   ├── QUICKSTART.md                  # Step-by-step onboarding guide
│   ├── API_REFERENCE.md               # Host Bridge REST & WebSocket API reference
│   └── AGENT_INTEGRATION.md           # How to connect LangChain, AutoGen, LlamaIndex, or raw LiteLLM
├── kage/
│   ├── __init__.py                    # Version & package metadata
│   ├── cli/                           # CLI commands (Typer + Rich)
│   │   ├── __init__.py
│   │   ├── main.py                    # Root CLI application & global flags
│   │   ├── init_cmd.py                # `kage init` (validation, directory setup, base image pull)
│   │   ├── up_cmd.py                  # `kage up` (qcow2 overlay, port allocation, QEMU spawn)
│   │   ├── list_cmd.py                # `kage list` (ASCII status table, resources, ports)
│   │   ├── connect_cmd.py             # `kage connect` (browser noVNC + Web Agent Console)
│   │   ├── shell_cmd.py               # `kage shell` (interactive SSH / direct guest exec)
│   │   ├── stop_cmd.py                # `kage stop` (clean QMP / ACPI shutdown)
│   │   ├── destroy_cmd.py             # `kage destroy` (teardown disks, metadata, sockets)
│   │   ├── agent_cmd.py               # `kage agent run` (autonomous agent loop via CLI)
│   │   ├── logs_cmd.py                # `kage logs` (instance QEMU/API logs)
│   │   └── config_cmd.py              # `kage config` (default settings, paths, API keys)
│   ├── core/                          # State & lifecycle management
│   │   ├── __init__.py
│   │   ├── config.py                  # Global config (~/.kage/config.json, directory paths)
│   │   ├── instance.py                # Instance state model (Pydantic), persistence, schema
│   │   ├── port_manager.py            # Conflict-free port allocator (SSH, VNC, noVNC, API, QMP)
│   │   └── process.py                 # Daemon lifecycle, PID tracking, process monitoring
│   ├── hypervisor/                    # QEMU / KVM virtualization engine
│   │   ├── __init__.py
│   │   ├── detector.py                # KVM / HVF / TCG capability detection
│   │   ├── qemu.py                    # QEMU command builder & subprocess manager
│   │   ├── qmp.py                     # QEMU Machine Protocol (QMP) JSON socket client
│   │   ├── disks.py                   # Qcow2 overlay creation & backing chain manager
│   │   ├── cloud_init.py              # Pure-Python NoCloud ISO 9660 generator (zero external tool deps)
│   │   ├── image_manager.py           # Base Ubuntu 24.04 image downloader, verifier & cache
│   │   └── shared_folder.py           # 9p / Virtio-fs host-guest directory mapping
│   ├── guest/                         # In-Guest Agent (Embedded payload injected into VM)
│   │   ├── __init__.py
│   │   ├── agent_service.py           # In-guest HTTP / Unix-socket daemon
│   │   ├── atspi_tree.py              # AT-SPI2 accessibility tree extractor & parser
│   │   ├── input_synth.py             # xdotool / input synthesis engine
│   │   ├── screen.py                  # maim / X11 screen capture engine
│   │   ├── shell_exec.py              # Subprocess execution & streaming
│   │   └── installer.sh               # In-guest bootstrap & systemd service setup
│   ├── server/                        # Host Bridge API & Web UI Server (FastAPI)
│   │   ├── __init__.py
│   │   ├── app.py                     # FastAPI application factory
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── instances.py           # Instance lifecycle endpoints
│   │   │   ├── shell.py               # Shell execution endpoints
│   │   │   ├── gui.py                 # AT-SPI tree, click, type, screenshot endpoints
│   │   │   ├── agent.py               # Agent execution & streaming endpoints
│   │   │   └── vnc.py                 # VNC connection helper endpoints
│   │   ├── websockify_proxy.py        # Native async WebSocket-to-TCP bridge for noVNC
│   │   └── static/                    # Built-in Web Console UI
│   │       ├── index.html             # Split-screen noVNC viewer + Live Agent Console
│   │       ├── app.js                 # Interactive console, AT-SPI inspector & chat
│   │       ├── styles.css             # Polished dark-mode UI
│   │       └── novnc/                 # Bundled lightweight noVNC distribution
│   └── agent/                         # LLM Routing & Autonomous Agent Loop
│       ├── __init__.py
│       ├── router.py                  # LiteLLM client & multi-provider routing
│       ├── runner.py                  # ReAct autonomous agent execution loop
│       ├── tools.py                   # Tool calling schemas (shell, click, tree, screenshot)
│       └── prompts.py                 # System prompts for OS-world interaction
└── tests/                             # Comprehensive test suite
    ├── __init__.py
    ├── conftest.py                    # Fixtures, mock QEMU, mock guest bridges
    ├── test_cli.py                    # CLI commands test suite
    ├── test_detector.py               # Hypervisor detection tests
    ├── test_qemu.py                   # QEMU command builder & QMP tests
    ├── test_port_manager.py           # Port allocation & conflict tests
    ├── test_disks.py                  # Qcow2 overlay logic tests
    ├── test_cloud_init.py             # ISO 9660 generator verification
    ├── test_guest_agent.py            # In-guest AT-SPI & input parsing tests
    ├── test_api_server.py             # FastAPI Host Bridge endpoints tests
    └── test_agent_runner.py           # LiteLLM routing & tool dispatch tests
```

---

## 3. Subsystem Specifications

### A. Host Virtualization & Image Management (`kage init`)
- **Capability Detector**:
  - Checks Linux `/dev/kvm` read/write access.
  - Checks macOS `Hypervisor.framework` support (`sysctl kern.hv_support`).
  - Detects `qemu-system-x86_64` (and `qemu-system-aarch64`), `qemu-img`.
  - Graceful fallback: If hardware acceleration is unavailable, configures QEMU TCG emulation mode with clear notification.
- **Pure-Python Cloud-Init ISO Builder**:
  - Implements an in-memory ISO 9660 filesystem generator (`CIDATA` volume label) for `user-data` and `meta-data`.
  - Eliminates external tool dependencies like `genisoimage`, `xorriso`, or `cloud-localds`.
- **Base Image Management**:
  - Downloads Ubuntu 24.04 LTS minimal cloud image with SHA-256 integrity verification.
  - Pre-configures base image cache in `~/.kage/images/` and sets up fast golden images.

### B. Instant VM Lifecycle & CoW Overlays (`kage up`, `stop`, `destroy`, `list`)
- **Copy-on-Write Storage**:
  - Uses `qemu-img create -f qcow2 -b <base_image> -F qcow2 <overlay.qcow2>`.
  - Spins up new instances in under 3 seconds with ~5MB initial disk overhead.
- **Dynamic Port Allocation**:
  - Automatically claims free ephemeral ports for SSH (`2222+`), VNC (`5900+`), noVNC WebSocket (`6080+`), Host Bridge API (`8000+`), and Guest Agent (`9000+`).
- **Virtio-fs / 9p Mount**:
  - Automatically maps host shared directory (e.g. `./workspace`) to `/workspace` inside the guest VM.
- **Instance State Management**:
  - Persistent JSON state records in `~/.kage/instances/<name>/state.json`.
  - Background daemon monitoring with PID tracking and QMP socket health checks.
- **Clean Teardown**:
  - Graceful ACPI shutdown via QMP socket, followed by SIGTERM/SIGKILL escalation if unresponsive.
  - Complete disk overlay and runtime socket cleanup on `kage destroy`.

### C. In-Guest Agent & Accessibility Stack
- **AT-SPI2 Accessibility Tree Parser**:
  - Traverses the X11 AT-SPI2 bus to extract GUI hierarchy:
    - Node ID (`node_0`, `node_1`, ...), Widget Name ("Firefox", "Save", "Terminal"), Role (`push_button`, `entry`, `window`), States (`focused`, `visible`, `enabled`), and Bounding Box `[x, y, width, height]`.
- **Input Synthesizer**:
  - Synthesizes mouse clicks, double clicks, drags, text typing, and key combinations via `xdotool` and X11 protocols.
- **Screenshot Capture**:
  - Grabs full-screen or region screenshots via `maim`/Xlib, returned as base64 or raw PNG.
- **Shell Executor**:
  - Sandboxed command execution with working directory tracking, streaming output, and exit status.

### D. Host Bridge API & Live Observability Server
- **FastAPI Endpoints**:
  - `POST /api/v1/instances/{name}/shell/exec`: Execute bash commands.
  - `GET /api/v1/instances/{name}/gui/tree`: Get structured accessibility tree JSON.
  - `POST /api/v1/instances/{name}/gui/click`: Click by coordinate `(x, y)` or node ID.
  - `POST /api/v1/instances/{name}/gui/type`: Type text or send key combo.
  - `GET /api/v1/instances/{name}/gui/screenshot`: Capture high-resolution screenshot.
  - `POST /api/v1/instances/{name}/agent/run`: Run autonomous agent prompt.
  - `WS /api/v1/instances/{name}/ws`: Real-time streaming log & terminal feed.
- **Integrated noVNC + Web Console**:
  - Built-in async WebSocket proxy (`websockify`) forwarding browser connections directly to QEMU VNC.
  - Split-screen UI: Live noVNC desktop viewer on the left, interactive AI agent chat, AT-SPI tree inspector, and tool logs on the right.

### E. LLM Routing Layer & Autonomous Agent Engine
- **Multi-Model Provider via LiteLLM**:
  - Supports Anthropic (`claude-3-7-sonnet`, `claude-3-5-sonnet`), OpenAI (`gpt-4o`, `o3-mini`), DeepSeek (`deepseek/deepseek-chat`), Ollama (`ollama/qwen2.5-coder`, `ollama/llama3.2-vision`), and vLLM.
- **Dual-Grounding ReAct Loop**:
  - Combines visual understanding (screenshots) with semantic hierarchy (accessibility tree) for robust UI automation.
  - Tool definitions: `execute_shell`, `get_accessibility_tree`, `mouse_click`, `type_text`, `take_screenshot`, `finish_task`.

### F. Distribution & Developer Experience
- **One-Line Installer (`install.sh`)**:
  - Inspects OS packages, sets up Python environment/uv, installs `kage`, and validates virtualization support.
- **Full CLI UX**:
  - Rich tables, spinners, colored status badges, auto-completion, and verbose logging options.
