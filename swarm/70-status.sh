#!/usr/bin/env bash
# Inside claw-host. One-screen status: gateway, cards per board, what's blocked, which gates wait for Tomas.
set -uo pipefail
REPO="${CLAW_REPO:-/srv/claw}"
STATE="${CLAW_STATE:-/var/lib/claw}"
export PATH="$HOME/.local/bin:$PATH"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

if tmux has-session -t claw 2>/dev/null; then echo "gateway: running"; else echo "gateway: STOPPED — run ./start.sh to restart"; fi

for board in claw-explore claw-build; do
  hermes kanban --board "$board" list --json > "$TMP/$board.json" 2>/dev/null || continue
  python3 - "$board" "$TMP/$board.json" <<'PY'
import collections, json, sys
board, path = sys.argv[1], sys.argv[2]
try:
    tasks = json.load(open(path))
except Exception:
    sys.exit()
if isinstance(tasks, dict):
    tasks = tasks.get("tasks", [])
if not tasks:
    sys.exit()
counts = collections.Counter(t.get("status") for t in tasks)
print(f"\n{board}: {len(tasks)} cards — " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
for t in tasks:
    status, title, tid = t.get("status"), t.get("title", ""), t.get("id")
    who = t.get("assignee") or "-"
    if status == "running":
        print(f"  ▶ running   {title}  [{who}]")
    elif status == "blocked":
        print(f"  ■ BLOCKED   {title}  [{who}]  → hermes kanban --board {board} show {tid}")
    elif status == "review":
        print(f"  ◆ review    {title}  [{who}]")
    elif status == "ready" and title.startswith("GATE") or (status == "ready" and not t.get("assignee")):
        key = title.split(" ")[0]
        print(f"  ★ WAITING FOR TOMAS  {title}  → ./start.sh approve {key} \"<your note>\"")
PY
done

if [ -d "$REPO/research" ]; then
  echo; echo "research/: $(find "$REPO/research" -type f | wc -l | tr -d ' ') files"
  for d in candidates scouting proposals bakeoff; do
    [ -d "$REPO/research/$d" ] && echo "  $d/: $(ls "$REPO/research/$d" | tr '\n' ' ')"
  done
fi
if [ -f "$STATE/gateway.log" ]; then echo; echo "gateway log (last 3 lines):"; tail -3 "$STATE/gateway.log" | cut -c1-200; fi
exit 0
