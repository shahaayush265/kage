#!/usr/bin/env bash
# ==============================================================================
# Kage Engine Installer — curl -fsSL https://raw.githubusercontent.com/shahaayush265/kage/main/install.sh | bash
# ==============================================================================

set -euo pipefail

# ANSI Colors
BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}"
cat << "EOF"
  _  __              
 | |/ /              
 | ' / __ _  __ _  ___ 
 |  < / _` |/ _` |/ _ \
 | . \ (_| | (_| |  __/
 |_|\_\__,_|\__, |\___|
             __/ |     
            |___/      
The Multi-Instance Agentic VM Engine
EOF
echo -e "${RESET}"

# 1. Detect Operating System & Architecture
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m | tr '[:upper:]' '[:lower:]')"

echo -e "${BOLD}▶ Detecting system environment...${RESET}"
echo -e "  • OS:   ${CYAN}${OS}${RESET}"
echo -e "  • Arch: ${CYAN}${ARCH}${RESET}"

# 2. Check Virtualization & QEMU
echo -e "\n${BOLD}▶ Checking virtualization dependencies...${RESET}"

HAS_QEMU=false
if command -v qemu-system-x86_64 >/dev/null 2>&1 || command -v qemu-system-aarch64 >/dev/null 2>&1; then
    HAS_QEMU=true
    echo -e "  ${GREEN}✓${RESET} QEMU hypervisor binary detected"
else
    echo -e "  ${YELLOW}⚠${RESET} QEMU not found in PATH."
fi

if [ "$OS" = "linux" ]; then
    if [ -e /dev/kvm ]; then
        if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
            echo -e "  ${GREEN}✓${RESET} Hardware acceleration (/dev/kvm) is accessible"
        else
            echo -e "  ${YELLOW}⚠${RESET} /dev/kvm exists, but user lacks permissions. Run:"
            echo -e "    ${BOLD}sudo usermod -aG kvm $USER${RESET}"
        fi
    else
        echo -e "  ${YELLOW}⚠${RESET} /dev/kvm not found. Virtual machines will run via TCG emulation."
    fi
elif [ "$OS" = "darwin" ]; then
    echo -e "  ${GREEN}✓${RESET} macOS Hypervisor.framework support active"
fi

# 3. Check Python & Installer Environment
echo -e "\n${BOLD}▶ Configuring Python environment for Kage...${RESET}"

KAGE_DIR="$HOME/.kage"
KAGE_VENV="$KAGE_DIR/venv"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$KAGE_DIR" "$BIN_DIR"

if command -v uv >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} Using uv for high-speed installation"
    if [ ! -d "$KAGE_VENV" ]; then
        uv venv "$KAGE_VENV" --quiet
    fi
    uv pip install --python "$KAGE_VENV/bin/python" "git+https://github.com/shahaayush265/kage.git" 2>/dev/null || \
    uv pip install --python "$KAGE_VENV/bin/python" -e .
elif command -v python3 >/dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} Using python3 venv"
    if [ ! -d "$KAGE_VENV" ]; then
        python3 -m venv "$KAGE_VENV"
    fi
    "$KAGE_VENV/bin/pip" install --quiet --upgrade pip
    "$KAGE_VENV/bin/pip" install --quiet "git+https://github.com/shahaayush265/kage.git" 2>/dev/null || \
    "$KAGE_VENV/bin/pip" install --quiet -e .
else
    echo -e "${RED}Error: Python 3.10+ is required to install Kage.${RESET}"
    exit 1
fi

# 4. Link CLI binary into PATH
ln -sf "$KAGE_VENV/bin/kage" "$BIN_DIR/kage"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}Notice:${RESET} Add ${BOLD}$BIN_DIR${RESET} to your PATH by adding this to your ~/.bashrc or ~/.zshrc:"
    echo -e "  ${BOLD}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
    export PATH="$BIN_DIR:$PATH"
fi

# 5. Verify Installation
echo -e "\n${BOLD}▶ Verifying Kage installation...${RESET}"
if command -v kage >/dev/null 2>&1 || [ -x "$BIN_DIR/kage" ]; then
    VERSION=$("$BIN_DIR/kage" --version 2>&1 || echo "0.1.0")
    echo -e "  ${GREEN}✓${RESET} Successfully installed ${BOLD}kage${RESET} (${VERSION})"
else
    echo -e "  ${RED}Failed to verify kage executable.${RESET}"
    exit 1
fi

# 6. Final Instructions
echo -e "\n${BOLD}${GREEN}✨ Kage installation complete!${RESET}"
echo -e "\n${BOLD}Quick Start:${RESET}"
echo -e "  1. Initialize host:    ${CYAN}kage init${RESET}"
echo -e "  2. Launch agent VM:    ${CYAN}kage up my-agent --memory 4G${RESET}"
echo -e "  3. Open Web Console:   ${CYAN}kage connect my-agent${RESET}"
echo -e "  4. Run AI agent:       ${CYAN}kage agent run my-agent --prompt \"Open terminal and run pytest\"${RESET}"
echo ""
