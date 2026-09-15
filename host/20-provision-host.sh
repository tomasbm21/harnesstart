#!/usr/bin/env bash
# Runs inside claw-host (10-create-host.sh calls it once per version of this file). Idempotent.
# Installs only the swarm's own tooling. Product components (VM managers etc.) are chosen by the swarm —
# builders record any system package they add here.
set -euo pipefail

HERMES_COMMIT="${HERMES_COMMIT:-939e45c91d751fadd94dcd1b873ac3cb44846213}"   # tag v2026.9.11 (Hermes 0.21.2)
REPO=/srv/claw
STATE=/var/lib/claw
export PATH="$HOME/.local/bin:$PATH"

say() { printf '\n== %s\n' "$1"; }

say "KVM"
if [[ ! -e /dev/kvm ]]; then
  echo "✗ /dev/kvm missing — nested virtualization is off. Needs Apple M3+, macOS 15+, nestedVirtualization: true." >&2
  exit 1
fi
getent group kvm >/dev/null && sudo usermod -aG kvm "$USER"
echo "✓ /dev/kvm present"

say "System packages"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl jq tmux build-essential python3 python3-venv python3-yaml \
  nftables ripgrep unzip ca-certificates gh

say "uv"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

say "Hermes Agent @ ${HERMES_COMMIT:0:8}"
if ! command -v hermes >/dev/null; then
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh \
    | bash -s -- --non-interactive --skip-setup --skip-computer-use --commit "$HERMES_COMMIT"
fi
hash -r
command -v hermes >/dev/null || { echo "✗ hermes not found in ~/.local/bin after install" >&2; exit 1; }
hermes --version | head -1

say "Git repo at ${REPO}"
git config --global --get-all safe.directory 2>/dev/null | grep -qx '\*' || git config --global --add safe.directory '*'   # virtiofs uid mapping + worktrees
git config --global user.name  >/dev/null || git config --global user.name  "claw-swarm"
git config --global user.email >/dev/null || git config --global user.email "claw-swarm@localhost"
if [[ ! -d "$REPO/.git" ]]; then
  git -C "$REPO" init -b main
  git -C "$REPO" add -A
  git -C "$REPO" commit -q -m "Scaffold: brief, swarm, host bootstrap"
fi
echo "✓ $(git -C "$REPO" log -1 --format='%h %s')"

say "State"
sudo mkdir -p "$STATE" && sudo chown "$USER" "$STATE"
touch "$STATE/.provisioned-$(sha256sum "$0" | cut -c1-12)"
printf '\n✓ claw-host provisioned.\n'
