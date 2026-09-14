# 影 Kage — The Multi-Instance Agentic VM Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/shahaayush265/kage)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![QEMU/KVM](https://img.shields.io/badge/Hypervisor-QEMU%20%2F%20KVM%20%2F%20HVF-orange.svg)](https://www.qemu.org)

**Kage** is an open-source, production-grade CLI tool and virtualization engine for spinning up, managing, observing, and connecting autonomous AI agents to dedicated, local Linux GUI/shell virtual machines with single-line commands.

---

## ⚡ Quickstart

### 1-Line Curl Installer
```bash
curl -fsSL https://raw.githubusercontent.com/shahaayush265/kage/main/install.sh | bash
```

### Or Install via Pip / Pipx
```bash
pip install kage
# or
pipx install kage
```

---

## 🚀 30-Second Walkthrough

```bash
# 1. Initialize environment & validate hypervisor capabilities (KVM / HVF)
kage init

# 2. Launch an isolated VM instance in under 3 seconds with shared workspace
kage up alpha --cpus 2 --memory 4G --shared-dir ./workspace

# 3. View status and allocated ports across all instances
kage list

# 4. Open the live noVNC desktop stream + split-screen Agent Web Console
kage connect alpha

# 5. Run an autonomous AI agent task against the VM
kage agent run alpha --prompt "Open terminal, create fibonacci.py, and run unit tests"

# 6. Stop or destroy when finished
kage stop alpha
kage destroy alpha --force
```

---

## 🏛 Architecture

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

## ✨ Key Capabilities

- ⚡ **Instant CoW Spawns (<3s)**: Utilizes QEMU qcow2 copy-on-write overlay disks on top of a single cached base image. Launch dozens of VMs without duplicating gigabytes of storage.
- 💿 **Zero-Dependency Cloud-Init**: Includes a built-in, pure-Python ISO 9660 generator for cloud-init NoCloud seed images. Works out-of-the-box on Linux and macOS without requiring `genisoimage` or `xorriso`.
- 🔌 **Dynamic Conflict-Free Ports**: Automatically detects and reserves available host ports for SSH (`2222+`), VNC (`5900+`), noVNC (`6080+`), Host Bridge API (`8000+`), and Guest Agent (`9000+`).
- 🌳 **AT-SPI2 Accessibility Grounding**: Extracts desktop GUI widget hierarchies into structured JSON with bounding boxes and node IDs, eliminating pixel hallucination.
- 🌐 **Native noVNC Streaming**: Features a built-in async WebSocket-to-TCP VNC proxy. Open the desktop GUI in any modern browser without extra client software.
- 🤖 **Multi-Model LLM Routing**: Built-in LiteLLM agent runner compatible with Claude 3.7 Sonnet, OpenAI GPT-4o, DeepSeek V3, Ollama, and vLLM.
- 📁 **Virtio-9p Host Mounts**: Map host directories directly into the guest VM filesystem (`/workspace`) with near-native I/O throughput.

---

## 🛠 Command Reference

| Command | Description |
| :--- | :--- |
| `kage init` | Validates host virtualization (KVM/HVF) and provisions base Ubuntu images. |
| `kage up [name]` | Spins up a new VM instance with overlay disk, port mappings, and API bridge. |
| `kage list` | Prints an ASCII table of instances, status, ports, CPU %, RAM RSS, and uptime. |
| `kage connect [name]` | Launches or displays the browser URL for the live noVNC stream & Web Console. |
| `kage shell [name]` | Opens interactive SSH or runs a single command inside the guest VM. |
| `kage stop [name]` | Halts execution gracefully via QMP ACPI shutdown. |
| `kage destroy [name]` | Cleanly removes VM overlays, cloud-init seed, and persistent records. |
| `kage agent run [name]` | Executes an autonomous AI agent task with live step-by-step console logs. |
| `kage model onboard` | Connects an AI provider (OmniRoute, Anthropic, OpenAI, Ollama, DeepSeek) & discovers models. |
| `kage model list` | Lists configured providers, endpoints, active default model, and available models. |
| `kage model set-default` | Sets the active default model for AI agent tasks. |
| `kage logs [name]` | Displays QEMU, serial console, or Host Bridge API logs for debugging. |
| `kage config` | Inspects or updates global engine preferences. |

---

## 🖥 Web Console & Observability

Every running VM comes with a built-in split-screen Web Console served at `http://127.0.0.1:<api_port>/view/<name>`:

- **Left Panel**: Live interactive desktop stream with click forwarding and coordinate inspector.
- **Right Panel**:
  - **AI Agent Chat**: Real-time prompt input and step-by-step reasoning logs.
  - **AT-SPI2 Tree Explorer**: Interactive GUI element hierarchy viewer.
  - **Terminal Console**: Execute commands directly against the VM.
  - **Instance Metrics**: Live CPU %, RSS RAM usage, and allocated port list.

---

## 📚 Documentation

- [Architecture & Subsystems Deep-Dive](docs/ARCHITECTURE.md)
- [Quickstart Guide](docs/QUICKSTART.md)
- [Host Bridge API Reference](docs/API_REFERENCE.md)
- [Agent Framework Integration (LangChain, AutoGen, CrewAI)](docs/AGENT_INTEGRATION.md)

---

## 📄 License

MIT © [Kage Project Contributors](LICENSE)
