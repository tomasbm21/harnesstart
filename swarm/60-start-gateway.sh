#!/usr/bin/env bash
# Inside claw-host. Starts the Hermes gateway (it runs the Kanban dispatcher) in tmux session "claw". Idempotent.
set -euo pipefail
REPO="${CLAW_REPO:-/srv/claw}"
STATE="${CLAW_STATE:-/var/lib/claw}"
export PATH="$HOME/.local/bin:$PATH"
. "$REPO/swarm/lib.sh"

if tmux has-session -t claw 2>/dev/null; then ok "gateway already running (tmux session 'claw')"; exit 0; fi
HERMES_BIN="$(command -v hermes)" || fail "hermes not on PATH"
mkdir -p "$STATE"
tmux new-session -d -s claw -c "$REPO" \
  "PATH='$PATH' '$HERMES_BIN' gateway run --replace 2>&1 | tee -a '$STATE/gateway.log'"
sleep 8
tmux has-session -t claw 2>/dev/null || fail "gateway exited straight away — last lines: $(tail -5 "$STATE/gateway.log" 2>/dev/null | tr '\n' ' ')"
ok "gateway running — dispatcher picks up ready cards within ~60 s (log: $STATE/gateway.log)"
