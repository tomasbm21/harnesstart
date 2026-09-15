#!/usr/bin/env bash
# Inside claw-host. Approve a human gate. Only Tomas decides gates.
#   bash swarm/approve.sh GATE-A "lean + fortress"          (asks y/N)
#   bash swarm/approve.sh GATE-B "go" --yes                 (no prompt; used by ./start.sh approve)
#   bash swarm/approve.sh t_1234abcd "note" --yes
set -euo pipefail
STATE="${CLAW_STATE:-/var/lib/claw}"
IDS="$STATE/card-ids.json"
export PATH="$HOME/.local/bin:$PATH"

ref="${1:?usage: approve.sh <GATE-key|card-id> [note] [--yes]}"
note="${2:-approved}"
yes=0; for a in "$@"; do [ "$a" = "--yes" ] && yes=1; done

board="claw-explore"; id="$ref"
if [[ ! "$ref" =~ ^t_ ]]; then
  [ -f "$IDS" ] || { echo "✗ $IDS missing — seed the board first." >&2; exit 1; }
  read -r board id < <(python3 - "$ref" "$IDS" <<'PY'
import json, sys
key, path = sys.argv[1], sys.argv[2]
for board, ids in json.load(open(path)).items():
    if key in ids:
        print(board, ids[key]); break
else:
    sys.exit(f"{key} not found in {path}")
PY
)
fi

status="$(hermes kanban --board "$board" list --json 2>/dev/null | python3 -c '
import json, sys
tasks = json.load(sys.stdin)
tasks = tasks.get("tasks", tasks) if isinstance(tasks, dict) else tasks
print(next((t.get("status", "?") for t in tasks if t.get("id") == sys.argv[1]), "missing"))
' "$id")"
case "$status" in
  ready|blocked) ;;
  done) echo "✓ $ref was already approved."; exit 0 ;;
  todo) echo "✗ $ref isn't waiting for you yet — the cards before it haven't finished (./start.sh status)." >&2; exit 1 ;;
  *) echo "✗ $ref has status '$status' — nothing to approve." >&2; exit 1 ;;
esac

hermes kanban --board "$board" show "$id"
if [ "$yes" != 1 ]; then
  echo
  read -r -p "Approve $ref ($id on $board)? Read the decision memo first. [y/N] " yn
  [[ "$yn" == [yY] ]] || { echo "Not approved."; exit 1; }
fi
hermes kanban --board "$board" complete "$id" --summary "Approved by Tomas: $note"
echo "✓ $ref approved — dependent cards start on the next dispatcher tick."
if [ "$ref" = "GATE-B" ]; then echo "Next: ./start.sh build   (seeds the build board from swarm/build.yaml)"; fi
exit 0
