#!/usr/bin/env bash
# Run on the Mac (start.sh calls it). Creates and starts the claw-host VM, and provisions it once.
set -euo pipefail
cd "$(dirname "$0")/.."

NAME="${CLAW_HOST_NAME:-claw-host}"
CPUS="${CLAW_CPUS:-6}"
MEM_GIB="${CLAW_MEMORY_GIB:-24}"
DISK_GIB="${CLAW_DISK_GIB:-200}"
REPO_DIR="$(pwd)"

if limactl list -q 2>/dev/null | grep -qx "$NAME"; then
  echo "  ✓ $NAME exists"
else
  limactl create --tty=false --name="$NAME" \
    --cpus="$CPUS" --memory="$MEM_GIB" --disk="$DISK_GIB" \
    --set ".mounts = [{\"location\": \"$REPO_DIR\", \"mountPoint\": \"/srv/claw\", \"writable\": true}]" \
    host/claw-host.yaml
fi

limactl start --tty=false "$NAME"   # no-op when already running

marker="/var/lib/claw/.provisioned-$(shasum -a 256 host/20-provision-host.sh | cut -c1-12)"
if limactl shell "$NAME" test -f "$marker" 2>/dev/null; then
  echo "  ✓ provisioned"
else
  limactl shell --workdir /srv/claw "$NAME" bash /srv/claw/host/20-provision-host.sh
fi
