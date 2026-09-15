#!/usr/bin/env bash
# Inside claw-host, after 25-configure-hermes.sh. Creates the 8 swarm profiles and both boards, and keeps each
# profile's model, web search and keys in sync with the default profile. Idempotent.
set -euo pipefail
REPO="${CLAW_REPO:-/srv/claw}"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export PATH="$HOME/.local/bin:$PATH"
. "$REPO/swarm/lib.sh"
load_env "$REPO/claw.env" || true
cd "$REPO/swarm"

command -v hermes >/dev/null || fail "hermes not on PATH — re-run ./start.sh."
[ -f "$HERMES_HOME/config.yaml" ] || fail "Hermes not configured — run swarm/25-configure-hermes.sh first."

declare -A DESC=(
  [lead]="Coordinator and judge for Norfront Claw: checks tools, maps options, scores proposals, writes SPEC and build plan. Doesn't scout or advocate."
  [lean]="Scout + proposer with a LEAN lens: fewest moving parts, adopt before build, runs on one MacBook."
  [fortress]="Scout + proposer with a FORTRESS lens: isolation, secrets, egress, reliability a client CISO would sign off."
  [market]="Scout + proposer with a MARKET lens: competitors, pricing, user demand, what makes Claw sellable to clients."
  [verifier]="Fact-checker for research (registry, bake-off numbers) and code reviewer during build. Evidence only."
  [redteam]="Breaks proposals: failure modes, hidden costs, rubric scoring, steal list for hybrids."
  [infra]="Builds below the brain: virtualization, images, networking, egress, services — per the chosen proposal/SPEC."
  [platform]="Builds above the VMs: claw CLI, config contracts, runtime wiring, lanes, console — per the chosen proposal/SPEC."
)
JUDGES=" lead verifier redteam "
MODEL="${CLAW_MODEL:-deepseek-v4-pro}"

# Keys to copy from the default profile's .env into every profile (values never printed).
sync_keys="DEEPSEEK_API_KEY"
[ -n "${WEB_BACKEND:-}" ] && sync_keys="$sync_keys $(web_key_name "$WEB_BACKEND")"
[ -n "${CLAW_JUDGE_API_KEY_NAME:-}" ] && sync_keys="$sync_keys $CLAW_JUDGE_API_KEY_NAME"

env_value() { if [ -f "$HERMES_HOME/.env" ]; then sed -n "s/^$1=//p" "$HERMES_HOME/.env" | tail -1; fi; }

step "Profiles"
for p in lead lean fortress market verifier redteam infra platform; do
  if [ ! -d "$HERMES_HOME/profiles/$p" ]; then
    hermes profile create "$p" --clone --description "${DESC[$p]}" >/dev/null
  fi
  { cat "souls/$p.md"; echo; cat RULES.md; } > "$HERMES_HOME/profiles/$p/SOUL.md"
  hermes -p "$p" config set terminal.backend local >/dev/null   # the swarm works inside claw-host
  hermes -p "$p" config set terminal.cwd "$REPO" >/dev/null

  # model
  if [[ "$JUDGES" == *" $p "* && -n "${CLAW_JUDGE_MODEL:-}" ]]; then
    hermes -p "$p" config set model.provider "${CLAW_JUDGE_PROVIDER:-deepseek}" >/dev/null
    hermes -p "$p" config set model.default "$CLAW_JUDGE_MODEL" >/dev/null
    m="${CLAW_JUDGE_PROVIDER:-deepseek}/$CLAW_JUDGE_MODEL"
  elif [[ "$JUDGES" != *" $p "* && -n "${CLAW_SCOUT_MODEL:-}" ]]; then
    hermes -p "$p" config set model.provider deepseek >/dev/null
    hermes -p "$p" config set model.default "$CLAW_SCOUT_MODEL" >/dev/null
    m="deepseek/$CLAW_SCOUT_MODEL"
  else
    hermes -p "$p" config set model.provider deepseek >/dev/null
    hermes -p "$p" config set model.default "$MODEL" >/dev/null
    m="deepseek/$MODEL"
  fi

  # web search + keys
  [ -n "${WEB_BACKEND:-}" ] && hermes -p "$p" config set web.backend "$WEB_BACKEND" >/dev/null
  for k in $sync_keys; do
    v="$(env_value "$k")"
    [ -n "$v" ] && hermes -p "$p" config set "$k" "$v" >/dev/null
  done
  ok "$p  ($m)"
done

step "Dispatcher"
hermes config set kanban.max_in_progress 3 >/dev/null
hermes config set kanban.max_in_progress_per_profile 1 >/dev/null   # two runs on one profile corrupt its memory
hermes config set kanban.orchestrator_profile lead >/dev/null
ok "max 3 in progress, 1 per profile, orchestrator = lead"

step "Boards"
hermes kanban init >/dev/null
for board in claw-explore claw-build; do
  if ! hermes kanban boards list 2>/dev/null | grep -qw "$board"; then
    hermes kanban boards create "$board" --default-workdir "$REPO" >/dev/null
  fi
  hermes kanban boards set-default-workdir "$board" "$REPO" >/dev/null
  ok "$board"
done

step "Repo"
# Workers branch from main, so scaffold edits (brief, rules, templates) must be committed before cards run.
for path in BRIEF.md SPEC.md START.md AGENTS.md CLAUDE.md .hermes.md README.md .gitignore claw.env.example start.sh host swarm; do
  [ -e "$REPO/$path" ] && git -C "$REPO" add -- "$path"
done
if ! git -C "$REPO" diff --cached --quiet; then
  git -C "$REPO" commit -q -m "Scaffold update ($(date +%F))"
  ok "committed scaffold changes: $(git -C "$REPO" log -1 --format=%h)"
else
  ok "scaffold up to date on main ($(git -C "$REPO" log -1 --format=%h))"
fi
