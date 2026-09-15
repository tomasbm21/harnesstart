#!/usr/bin/env bash
# Inside claw-host. Readiness checks before the swarm starts. Changes nothing.
#   bash swarm/50-ready-check.sh           structural checks
#   bash swarm/50-ready-check.sh --ping    also send one tiny prompt per model to prove the keys work
set -uo pipefail
REPO="${CLAW_REPO:-/srv/claw}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
STATE="${CLAW_STATE:-/var/lib/claw}"
export PATH="$HOME/.local/bin:$PATH"
. "$REPO/swarm/lib.sh"
load_env "$REPO/claw.env" || true
PING=0; [ "${1:-}" = "--ping" ] && PING=1
FAILS=0
bad() { printf '  ✗ %s\n' "$1"; FAILS=$((FAILS + 1)); }
check() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1${3:+ — $3}"; fi; }

step "Host"
check "/dev/kvm present (hardware VMs possible)" '[ -e /dev/kvm ]' "nested virtualization is off"
check "git, tmux, python3-yaml, gh installed" 'command -v git && command -v tmux && python3 -c "import yaml" && command -v gh'
check "hermes installed" 'command -v hermes'
hv="$(hermes --version 2>/dev/null | head -1)"; [ -n "$hv" ] && ok "hermes: $hv"
check "state dir writable ($STATE)" '[ -w "$STATE" ]' "sudo mkdir -p $STATE && sudo chown \$USER $STATE"

step "Repo"
check "$REPO is a git repo with a commit" 'git -C "$REPO" rev-parse HEAD'
for f in BRIEF.md START.md .hermes.md swarm/RULES.md swarm/explore.yaml swarm/templates/proposal.md swarm/sealed/claude-baseline-v0.md; do
  check "$f present and committed" 'git -C "$REPO" ls-files --error-unmatch "$f"' "commit it: git -C $REPO add -A && git -C $REPO commit -m scaffold"
done
check "claw.env is gitignored" 'git -C "$REPO" check-ignore -q claw.env'
check "no secrets left in claw.env" '! grep -Eq "^(DEEPSEEK_API_KEY|WEB_API_KEY|GH_TOKEN|CLAW_JUDGE_API_KEY)=[^_[:space:]][^[:space:]]*$" "$REPO/claw.env"' "re-run swarm/25-configure-hermes.sh"
check "explore.yaml parses (22 cards)" 'python3 -c "import yaml,sys; c=yaml.safe_load(open(\"$REPO/swarm/explore.yaml\"))[\"cards\"]; sys.exit(len(c)!=22)"'
check "registry verifier runs" 'python3 "$REPO/swarm/tools/verify_candidates.py" "$REPO/swarm/templates/" --no-network'

step "Hermes"
check "DeepSeek key in default profile" 'grep -Eq "^DEEPSEEK_API_KEY=.+" "$HERMES_HOME/.env"' "put it in claw.env and re-run ./start.sh"
for p in lead lean fortress market verifier redteam infra platform; do
  pd="$HERMES_HOME/profiles/$p"
  check "profile $p: SOUL + rules + model key" '[ -d "$pd" ] && grep -q "Swarm rules" "$pd/SOUL.md" && grep -Eq "^(DEEPSEEK_API_KEY|${CLAW_JUDGE_API_KEY_NAME:-DEEPSEEK_API_KEY})=.+" "$pd/.env"' "re-run swarm/30-create-swarm.sh"
done
if [ -n "${WEB_BACKEND:-}" ]; then
  wk="$(web_key_name "$WEB_BACKEND")"
  if grep -Eq "^$wk=.+" "$HERMES_HOME/.env" 2>/dev/null; then ok "web search: $WEB_BACKEND with key"; else warn "web search: $WEB_BACKEND keyless — expect rate limits"; fi
else
  warn "web search: keyless free tiers — add WEB_BACKEND + WEB_API_KEY to claw.env for a smoother run"
fi
gh auth status >/dev/null 2>&1 && ok "gh authenticated" || warn "gh not authenticated (optional)"

step "Boards"
for b in claw-explore claw-build; do
  check "board $b exists" 'hermes kanban boards list | grep -qw "$b"' "re-run swarm/30-create-swarm.sh"
done
counts="$(hermes kanban --board claw-explore list --json 2>/dev/null | python3 -c '
import json, sys, collections
try:
    tasks = json.load(sys.stdin)
except Exception:
    print("unreadable"); sys.exit()
tasks = tasks.get("tasks", tasks) if isinstance(tasks, dict) else tasks
c = collections.Counter(t.get("status") for t in tasks)
print(len(tasks), " ".join(f"{k}={v}" for k, v in sorted(c.items())))
')"
case "$counts" in
  22*) ok "claw-explore seeded: $counts" ;;
  *)   bad "claw-explore should have 22 cards (got: ${counts:-none}) — run swarm/40-seed-board.sh explore" ;;
esac

if [ "$PING" = 1 ]; then
  step "Model ping (one tiny prompt per distinct model)"
  pinged=" "
  for p in lead lean; do
    model="$(hermes -p "$p" config get model.default 2>/dev/null | tail -1)"
    case "$pinged" in *" $model "*) continue ;; esac
    pinged="$pinged$model "
    reply="$(cd /tmp && timeout 180 hermes -p "$p" --ignore-rules -z "Reply with exactly the word CLAW_OK and nothing else." 2>&1 | tail -3)"
    if printf '%s' "$reply" | grep -q CLAW_OK; then ok "$p → $model answers"
    else bad "$p → $model did not answer: $(printf '%s' "$reply" | tr '\n' ' ' | cut -c1-160)"; fi
  done
fi

echo
if [ "$FAILS" -eq 0 ]; then echo "READY ✓"; exit 0; else echo "NOT READY: $FAILS problem(s) above ✗"; exit 1; fi
