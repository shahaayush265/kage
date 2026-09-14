# Kage Quickstart Guide

Get up and running with multi-instance AI agent VMs in less than 2 minutes.

---

## 1. Installation

### One-Line Install
```bash
curl -sSL https://raw.githubusercontent.com/kage-engine/kage/main/install.sh | bash
```

### Or Install via Pip / Pipx
```bash
pip install kage
# or with pipx:
pipx install kage
```

---

## 2. Initialize Kage
Validates host virtualization capabilities (KVM on Linux, Hypervisor.framework on macOS) and prepares base images:
```bash
kage init
```

---

## 3. Spin Up Your First VM Instance
```bash
# Launch a dedicated VM with 2 vCPUs, 4GB RAM, and host workspace mapping
kage up alpha --cpus 2 --memory 4G --shared-dir ./workspace
```

Output:
```
Provisioning new Kage instance 'alpha'...
✓ Instance 'alpha' is up and running!

╭───────────────────────────────────────────────╮
│ Web Console:    http://127.0.0.1:8000/view/alpha│
│ Host Bridge API: http://127.0.0.1:8000/docs   │
│ SSH Access:     ssh kage@127.0.0.1 -p 2222    │
│ VNC Port:       127.0.0.1:5900                │
│ Shared Folder:  ./workspace -> /workspace     │
╰───────────────────────────────────────────────╯
```

---

## 4. Observe the Live Desktop & Web Console
Open the live noVNC stream and interactive AI Agent console in your default browser:
```bash
kage connect alpha
```

---

## 5. Command Autonomous AI Agents
Instruct the autonomous agent to complete tasks inside the VM:
```bash
# Using Claude 3.7 Sonnet (or specify --model openai/gpt-4o)
export ANTHROPIC_API_KEY="your-api-key"
kage agent run alpha --prompt "Open terminal, create a python script that calculates fibonacci, and execute it"
```

---

## 6. List and Manage Instances
```bash
# View all instances and resource consumption
kage list

# Shell into the VM
kage shell alpha

# Stop an instance
kage stop alpha

# Cleanly destroy instance and delete disk overlay
kage destroy alpha --force
```
