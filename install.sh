#!/usr/bin/env bash
# ==============================================================================
# Kage Engine Installer — curl -fsSL https://raw.githubusercontent.com/shahaayush265/kage/main/install.sh | bash
# ==============================================================================

set -euo pipefail

# ANSI Colors & Formatting
BOLD="\033[1m"
DIM="\033[2m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
BLUE="\033[34m"
MAGENTA="\033[35m"
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

# 1. System & Architecture Detection
echo -e "${BOLD}${CYAN}[1/4]${RESET} ${BOLD}Detecting system environment & virtualization...${RESET}"
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m | tr '[:upper:]' '[:lower:]')"

echo -e "  • Operating System: ${CYAN}${OS}${RESET}"
echo -e "  • Architecture:     ${CYAN}${ARCH}${RESET}"

HAS_QEMU=false
if command -v qemu-system-x86_64 >/dev/null 2>&1 || command -v qemu-system-aarch64 >/dev/null 2>&1; then
    HAS_QEMU=true
    echo -e "  ${GREEN}✓${RESET} QEMU hypervisor binary detected"
else
    echo -e "  ${YELLOW}⚠${RESET} QEMU not found in PATH (Install via: apt install qemu-system-x86 qemu-utils / brew install qemu)"
fi

if [ "$OS" = "linux" ]; then
    if [ -e /dev/kvm ]; then
        if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
            echo -e "  ${GREEN}✓${RESET} KVM hardware acceleration (/dev/kvm) is active"
        else
            echo -e "  ${YELLOW}⚠${RESET} /dev/kvm exists, but user lacks permissions. Add your user with:"
            echo -e "    ${BOLD}sudo usermod -aG kvm $USER${RESET}"
        fi
    else
        echo -e "  ${YELLOW}⚠${RESET} /dev/kvm not detected. VMs will run in TCG software emulation mode."
    fi
elif [ "$OS" = "darwin" ]; then
    echo -e "  ${GREEN}✓${RESET} macOS Hypervisor.framework support active"
fi

# 2. Directory & Python Virtual Environment Setup
echo -e "\n${BOLD}${CYAN}[2/4]${RESET} ${BOLD}Configuring storage & Python environment...${RESET}"

KAGE_DIR="$HOME/.kage"
KAGE_VENV="$KAGE_DIR/venv"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$KAGE_DIR/instances" "$KAGE_DIR/images" "$KAGE_DIR/logs" "$BIN_DIR"
echo -e "  ${GREEN}✓${RESET} Storage initialized at ${BOLD}${KAGE_DIR}${RESET}"

USE_UV=false
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    echo -e "  ${GREEN}✓${RESET} Found ${BOLD}uv${RESET} package manager"
    if [ ! -d "$KAGE_VENV" ]; then
        echo -e "  • Creating virtual environment at ${DIM}$KAGE_VENV${RESET}..."
        uv venv "$KAGE_VENV" --quiet
    else
        echo -e "  ${GREEN}✓${RESET} Using existing virtual environment at ${DIM}$KAGE_VENV${RESET}"
    fi
elif command -v python3 >/dev/null 2>&1; then
    echo -e "  • Using ${BOLD}python3 venv${RESET}"
    if [ ! -d "$KAGE_VENV" ]; then
        echo -e "  • Creating virtual environment at ${DIM}$KAGE_VENV${RESET}..."
        python3 -m venv "$KAGE_VENV"
    else
        echo -e "  ${GREEN}✓${RESET} Using existing virtual environment at ${DIM}$KAGE_VENV${RESET}"
    fi
else
    echo -e "${RED}Error: Python 3.10+ is required to install Kage.${RESET}"
    exit 1
fi

# 3. Installing Kage Engine & Dependencies with Live Progress
echo -e "\n${BOLD}${CYAN}[3/4]${RESET} ${BOLD}Downloading and installing Kage & dependencies...${RESET}"

REPO_URL="git+https://github.com/shahaayush265/kage.git"

if [ "$USE_UV" = true ]; then
    echo -e "  • Resolving and installing packages (showing download progress)..."
    uv pip install --python "$KAGE_VENV/bin/python" "$REPO_URL" || \
    uv pip install --python "$KAGE_VENV/bin/python" -e .
else
    echo -e "  • Updating pip and downloading dependencies..."
    "$KAGE_VENV/bin/pip" install --progress-bar on --upgrade pip
    "$KAGE_VENV/bin/pip" install --progress-bar on "$REPO_URL" || \
    "$KAGE_VENV/bin/pip" install --progress-bar on -e .
fi

# 4. Linking Executable & Verifying Installation
echo -e "\n${BOLD}${CYAN}[4/4]${RESET} ${BOLD}Finalizing installation...${RESET}"

ln -sf "$KAGE_VENV/bin/kage" "$BIN_DIR/kage"
echo -e "  ${GREEN}✓${RESET} Linked CLI executable to ${BOLD}$BIN_DIR/kage${RESET}"

# Check PATH
PATH_NOTICE=""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    PATH_NOTICE="export PATH=\"\$HOME/.local/bin:\$PATH\""
    export PATH="$BIN_DIR:$PATH"
fi

# Verify CLI
if [ -x "$BIN_DIR/kage" ]; then
    VERSION_STR=$("$BIN_DIR/kage" --version 2>&1 || echo "0.1.0")
    echo -e "  ${GREEN}✓${RESET} Verified ${BOLD}${VERSION_STR}${RESET}"
else
    echo -e "  ${RED}Error: Failed to verify executable at $BIN_DIR/kage${RESET}"
    exit 1
fi

echo -e "\n${BOLD}${GREEN}======================================================${RESET}"
echo -e "${BOLD}${GREEN}  ✨ Kage Engine installed successfully!              ${RESET}"
echo -e "${BOLD}${GREEN}======================================================${RESET}"

if [ -n "$PATH_NOTICE" ]; then
    echo -e "\n${YELLOW}Notice:${RESET} Please add ${BOLD}~/.local/bin${RESET} to your PATH by adding this to your ~/.bashrc or ~/.zshrc:"
    echo -e "  ${BOLD}${CYAN}${PATH_NOTICE}${RESET}\n"
fi

echo -e "${BOLD}Next Steps:${RESET}"
echo -e "  1. Initialize hypervisor & base images: ${CYAN}kage init${RESET}"
echo -e "  2. Launch your first agent VM:          ${CYAN}kage up my-agent --memory 4G${RESET}"
echo -e "  3. Open live web desktop & console:     ${CYAN}kage connect my-agent${RESET}"
echo -e "  4. Run an autonomous AI task:           ${CYAN}kage agent run my-agent --prompt \"...\"${RESET}"
echo ""
