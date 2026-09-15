#!/usr/bin/env bash
# Inside claw-host. Seeds a board from its YAML, dependencies included. Idempotent (idempotency keys).
#   bash /srv/claw/swarm/40-seed-board.sh explore   → swarm/explore.yaml onto claw-explore
#   bash /srv/claw/swarm/40-seed-board.sh build     → swarm/build.yaml (written by the lead at B0) onto claw-build
set -euo pipefail
phase="${1:?usage: 40-seed-board.sh explore|build}"
case "$phase" in
  explore|build) ;;
  *) echo "usage: 40-seed-board.sh explore|build" >&2; exit 2 ;;
esac
export CLAW_PHASE="$phase"
export CLAW_BACKLOG="${CLAW_BACKLOG:-/srv/claw/swarm/$phase.yaml}"
export CLAW_BOARD="${CLAW_BOARD:-claw-$phase}"
export CLAW_STATE="${CLAW_STATE:-/var/lib/claw}"
if [[ ! -f "$CLAW_BACKLOG" ]]; then
  hint=""; [[ "$phase" == build ]] && hint=" — the lead writes it at card B0"
  echo "✗ $CLAW_BACKLOG not found$hint." >&2; exit 1
fi

python3 - <<'PY'
import json, os, pathlib, subprocess, sys
import yaml

board, phase = os.environ["CLAW_BOARD"], os.environ["CLAW_PHASE"]
backlog = yaml.safe_load(pathlib.Path(os.environ["CLAW_BACKLOG"]).read_text())
defaults = backlog.get("defaults", {})
state = pathlib.Path(os.environ["CLAW_STATE"])
state.mkdir(parents=True, exist_ok=True)
ids_file = state / "card-ids.json"
all_ids = json.loads(ids_file.read_text()) if ids_file.exists() else {}
ids = {}

for card in backlog["cards"]:
    key = card["key"]
    body = card["body"].strip()
    if card.get("footer"):
        body += "\n\n" + card["footer"].replace("{key}", key.lower()).strip()
    cmd = ["hermes", "kanban", "--board", board, "create", f"{key} · {card['title']}",
           "--body", body, "--idempotency-key", f"{board}-{key}", "--json"]
    if not card.get("gate"):
        cmd += ["--assignee", card["assignee"],
                "--workspace", "worktree", "--branch", f"card/{key.lower()}",
                "--max-runtime", str(card.get("max_runtime", defaults.get("max_runtime", "2h")))]
    for parent in card.get("parents", []):
        if parent not in ids:
            sys.exit(f"✗ {key}: parent {parent} must appear earlier in the backlog")
        cmd += ["--parent", ids[parent]]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit(f"✗ {key} failed:\n  {' '.join(cmd[:8])} …\n{res.stderr or res.stdout}")
    try:
        ids[key] = json.loads(res.stdout)["id"]
    except (json.JSONDecodeError, KeyError):
        sys.exit(f"✗ {key}: unexpected output from hermes kanban create --json:\n{res.stdout}")
    print(f"✓ {key:<8} {ids[key]:<12} {'Tomas (gate)' if card.get('gate') else card['assignee']}")

all_ids[board] = ids
ids_file.write_text(json.dumps(all_ids, indent=2))
print(f"\nSeeded {len(ids)} cards on '{board}'. Ids saved to {ids_file}")
if phase == "explore":
    print("Next: ./start.sh on the Mac starts the gateway (or: bash swarm/60-start-gateway.sh inside claw-host)")
PY
