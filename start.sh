#!/usr/bin/env bash
# Norfront Claw — the one command. Run on the Mac, from this folder. Safe to re-run at any point.
#
#   ./start.sh                     set everything up (first run ~20 min) and start the swarm
#   ./start.sh status              what's running, blocked, and waiting for Tomas
#   ./start.sh doctor              readiness checks, plus one tiny model call to prove the keys work
#   ./start.sh approve GATE-A "…"  approve a gate (Tomas's decision only)
#   ./start.sh show <card-id|KEY>  full card: body, comments, why it's blocked
#   ./start.sh answer <card-id> "…"  answer a blocked card and release it
#   ./start.sh build               after GATE-B: seed the build board from swarm/build.yaml
#   ./start.sh watch               live event stream
#   ./start.sh logs                follow the gateway log
#   ./start.sh shell               open a shell inside claw-host
#   ./start.sh stop                stop the swarm and the VM
set -euo pipefail
cd "$(dirname "$0")"
. swarm/lib.sh
NAME="${CLAW_HOST_NAME:-claw-host}"
cmd="${1:-up}"; [ $# -gt 0 ] && shift

in_vm() { limactl shell --workdir /srv/claw "$NAME" "$@"; }
vm_status() { limactl list --format '{{.Status}}' "$NAME" 2>/dev/null || true; }
need_vm() { [ "$(vm_status)" = "Running" ] || fail "claw-host isn't running — run ./start.sh first."; }

[ "$(uname -s)" = "Darwin" ] || fail "Run start.sh on the Mac. Inside claw-host use the swarm/*.sh scripts (see START.md)."

case "$cmd" in
  up|start)
    if [ ! -f claw.env ]; then
      cp claw.env.example claw.env
      fail "Created claw.env. Open it, paste your DeepSeek key (and ideally a web search key), then run ./start.sh again."
    fi
    grep -Eq '^DEEPSEEK_API_KEY=[^[:space:]#]+' claw.env || fail "DEEPSEEK_API_KEY is empty in claw.env — paste your key, then re-run."
    load_env claw.env
    export CLAW_CPUS="${CLAW_CPUS:-6}" CLAW_MEMORY_GIB="${CLAW_MEMORY_GIB:-24}" CLAW_DISK_GIB="${CLAW_DISK_GIB:-200}"

    step "1/6 Mac preflight";                    bash host/00-preflight-mac.sh
    step "2/6 Linux VM (claw-host)";             bash host/10-create-host.sh
    step "3/6 Hermes: model, web search, keys";  in_vm bash swarm/25-configure-hermes.sh
    step "4/6 Swarm: 8 profiles, 2 boards";      in_vm bash swarm/30-create-swarm.sh
    step "5/6 Explore board: 22 cards";          in_vm bash swarm/40-seed-board.sh explore
    step "6/6 Readiness check + start";          in_vm bash swarm/50-ready-check.sh --ping
    in_vm bash swarm/60-start-gateway.sh
    cat <<'EOF'

✓ The swarm is running. First card: F0 (lead checks the tools), then 7 scouts in parallel.

  ./start.sh status     progress, blocked cards, gates waiting for you
  ./start.sh watch      live events
  Findings land in research/ in this folder.

You decide at GATE-A (research/decision-A.md) and GATE-B (research/decision-B.md).
EOF
    ;;
  status)  need_vm; in_vm bash swarm/70-status.sh ;;
  doctor)  bash host/00-preflight-mac.sh; need_vm; in_vm bash swarm/50-ready-check.sh --ping ;;
  approve)
    need_vm
    [ $# -ge 1 ] || fail 'usage: ./start.sh approve GATE-A "your note"'
    in_vm bash swarm/approve.sh "$1" "${2:-approved}" --yes
    ;;
  show)
    need_vm
    [ $# -ge 1 ] || fail 'usage: ./start.sh show <card-id|KEY>'
    read -r board id <<EOF2
$(in_vm python3 -c 'import json,sys; ids=json.load(open("/var/lib/claw/card-ids.json")); a=sys.argv[1]
for b,m in ids.items():
    if a in m: print(b, m[a]); break
    if a in m.values(): print(b, a); break
else: print("claw-explore", a)' "$1")
EOF2
    in_vm hermes kanban --board "$board" show "$id"
    ;;
  answer)
    need_vm
    [ $# -ge 2 ] || fail 'usage: ./start.sh answer <card-id> "your answer"'
    board="$(in_vm python3 -c 'import json,sys; ids=json.load(open("/var/lib/claw/card-ids.json")); print(next((b for b,m in ids.items() if sys.argv[1] in m.values()), "claw-explore"))' "$1")"
    in_vm hermes kanban --board "$board" comment "$1" "Tomas: $2"
    in_vm hermes kanban --board "$board" unblock "$1"
    ok "answered and unblocked $1 on $board"
    ;;
  build)   need_vm; in_vm bash swarm/40-seed-board.sh build ;;
  watch)   need_vm; in_vm hermes kanban --board "${1:-claw-explore}" watch ;;
  logs)    need_vm; in_vm tail -f /var/lib/claw/gateway.log ;;
  shell)   need_vm; limactl shell --workdir /srv/claw "$NAME" ;;
  stop)
    if [ "$(vm_status)" = "Running" ]; then
      in_vm tmux kill-session -t claw 2>/dev/null || true
      limactl stop "$NAME"
    fi
    ok "stopped (cards and research are kept; ./start.sh resumes)"
    ;;
  *) sed -n '2,16p' "$0"; exit 2 ;;
esac
