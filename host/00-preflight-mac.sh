#!/usr/bin/env bash
# Run on the Mac. Checks this MacBook can run Firecracker inside a Linux VM, and installs Lima.
set -euo pipefail

fail() { printf '✗ %s\n' "$1" >&2; exit 1; }
ok()   { printf '✓ %s\n' "$1"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "Run this on the Mac, not inside a VM."
[[ "$(uname -m)" == "arm64" ]]  || fail "Apple Silicon required."

chip="$(sysctl -n machdep.cpu.brand_string)"
gen="$(sed -nE 's/^Apple M([0-9]+).*/\1/p' <<<"$chip")"
[[ -n "$gen" && "$gen" -ge 3 ]] || fail "Nested virtualization needs Apple M3 or newer (found: $chip). Hardware VMs inside the Linux VM will not work on this Mac (BRIEF R1/R2) — use an M3+ Mac or a Linux KVM box."
ok "Chip: $chip"

macos="$(sw_vers -productVersion)"
[[ "${macos%%.*}" -ge 15 ]] || fail "Nested virtualization needs macOS 15+ (found: $macos)."
ok "macOS $macos"

mem_gib=$(( $(sysctl -n hw.memsize) / 1024 / 1024 / 1024 ))
[[ "$mem_gib" -ge 32 ]] || fail "Need ≥32 GiB RAM to give the VM 24 GiB (found: ${mem_gib} GiB)."
ok "RAM ${mem_gib} GiB, $(sysctl -n hw.ncpu) cores"

free_gib="$(df -g "$HOME" | awk 'NR==2 {print $4}')"
[[ "$free_gib" -ge 60 ]] || fail "Need ≥60 GiB free disk (found: ${free_gib} GiB)."
ok "Free disk ${free_gib} GiB"

command -v brew >/dev/null || fail "Install Homebrew first: https://brew.sh"
command -v limactl >/dev/null || brew install lima
lima_major="$(limactl --version | sed -nE 's/^[^0-9]*([0-9]+)\..*/\1/p')"
[[ "${lima_major:-0}" -ge 2 ]] || brew upgrade lima
ok "$(limactl --version)"

printf '  ✓ preflight passed\n'
