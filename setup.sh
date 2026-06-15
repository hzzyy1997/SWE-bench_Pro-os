#!/usr/bin/env bash
#
# SWE-bench Pro - Local Evaluation Environment Setup
#
# This script sets up the local Docker environment for running
# SWE-bench Pro evaluations on macOS (Apple Silicon & Intel).
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# What it does:
#   1. Installs Docker CLI, Colima, and QEMU (via Homebrew)
#   2. Starts a Colima VM with x86_64 emulation (required by SWE-bench images)
#   3. Logs in to the private image registry
#   4. Installs Python dependencies
#   5. Validates the setup by pulling a test image
#

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────────
REGISTRY="devops-registry.cn-hangzhou.cr.aliyuncs.com"
REGISTRY_USERNAME="yiyun.zyy@1663046207295021"
COLIMA_CPU=4
COLIMA_MEMORY=8    # GB
COLIMA_DISK=60     # GB
# ─────────────────────────────────────────────────────────────────

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$*"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m  %s\n" "$*"; }
error() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$*"; exit 1; }

# ─── Step 0: Check platform ─────────────────────────────────────
info "Checking platform..."
if [[ "$(uname)" != "Darwin" ]]; then
    error "This setup script is designed for macOS. For Linux, install Docker Engine directly: https://docs.docker.com/engine/install/"
fi
ARCH=$(uname -m)
ok "macOS detected (arch: $ARCH)"

# ─── Step 1: Install dependencies via Homebrew ──────────────────
info "Checking Homebrew..."
if ! command -v brew &>/dev/null; then
    error "Homebrew not found. Install it first: https://brew.sh"
fi

install_if_missing() {
    local cmd=$1
    local formula=$2
    if command -v "$cmd" &>/dev/null; then
        ok "$formula already installed"
    else
        info "Installing $formula..."
        brew install "$formula"
        ok "$formula installed"
    fi
}

install_if_missing docker docker
install_if_missing colima colima
install_if_missing qemu-system-x86_64 qemu

# ─── Step 2: Start Colima ───────────────────────────────────────
info "Starting Colima (x86_64 emulation, ${COLIMA_CPU} CPU, ${COLIMA_MEMORY}GB RAM)..."
if colima status &>/dev/null; then
    warn "Colima is already running"
    colima status
else
    colima start \
        --cpu "$COLIMA_CPU" \
        --memory "$COLIMA_MEMORY" \
        --disk "$COLIMA_DISK" \
        --arch x86_64
    ok "Colima started"
fi

# ─── Step 3: Verify Docker ─────────────────────────────────────
info "Verifying Docker connection..."
if docker info &>/dev/null; then
    ok "Docker is running"
else
    error "Docker is not responding. Try: colima stop && colima start --arch x86_64"
fi

# ─── Step 4: Registry login ────────────────────────────────────
info "Logging in to private registry ($REGISTRY)..."
echo "Please enter the registry password when prompted:"
docker login --username="$REGISTRY_USERNAME" "$REGISTRY"
ok "Registry login successful"

# ─── Step 5: Python dependencies ───────────────────────────────
info "Installing Python dependencies..."
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
if [[ -f "$SCRIPT_DIR/requirements.txt" ]]; then
    pip install -r "$SCRIPT_DIR/requirements.txt"
    ok "Python dependencies installed"
else
    warn "requirements.txt not found, skipping"
fi

# ─── Step 6: Validate with a test image pull ───────────────────
info "Pulling a test image to validate setup..."
TEST_IMAGE="devops-registry.cn-hangzhou.cr.aliyuncs.com/long-range/sweap-images:nodebb.nodebb-NodeBB__NodeBB-04998908ba6721d64eba79ae3b65a351dcfbc5b5"
if docker pull "$TEST_IMAGE" --platform linux/amd64; then
    ok "Test image pulled successfully"
    docker rmi "$TEST_IMAGE" &>/dev/null || true
else
    warn "Test image pull failed - check registry credentials and network"
fi

# ─── Done ───────────────────────────────────────────────────────
echo ""
echo "=========================================="
ok "Setup complete!"
echo "=========================================="
echo ""
echo "Run an evaluation with:"
echo ""
echo "  python3 swe_bench_pro_eval.py \\"
echo "    --raw_sample_path=helper_code/sweap_eval_full_v2.jsonl \\"
echo "    --patch_path=<your_patches>.json \\"
echo "    --output_dir=output/ \\"
echo "    --scripts_dir=run_scripts \\"
echo "    --use_local_docker \\"
echo "    --num_workers=4"
echo ""
echo "To stop the Colima VM when done:"
echo "  colima stop"
echo ""
