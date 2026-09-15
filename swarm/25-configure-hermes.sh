#!/usr/bin/env bash
# Inside claw-host. Configures the default Hermes profile from /srv/claw/claw.env, then moves secrets out of
# claw.env (they live in ~/.hermes/.env afterwards). Idempotent. Replaces the interactive `hermes setup`.
set -euo pipefail
REPO="${CLAW_REPO:-/srv/claw}"
ENV_FILE="$REPO/claw.env"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
export PATH="$HOME/.local/bin:$PATH"
. "$REPO/swarm/lib.sh"

command -v hermes >/dev/null || fail "hermes not installed — re-run ./start.sh (provisioning installs it)."
load_env "$ENV_FILE" || fail "$ENV_FILE missing — run ./start.sh on the Mac; it creates it from claw.env.example."

has_env_key() { [ -f "$HERMES_HOME/.env" ] && grep -Eq "^$1=.+" "$HERMES_HOME/.env"; }

step "Model"
hermes config set model.provider deepseek >/dev/null
hermes config set model.default "${CLAW_MODEL:-deepseek-v4-pro}" >/dev/null
if is_fresh_secret "${DEEPSEEK_API_KEY:-}"; then
  hermes config set DEEPSEEK_API_KEY "$DEEPSEEK_API_KEY" >/dev/null
fi
has_env_key DEEPSEEK_API_KEY || fail "No DeepSeek key. Put DEEPSEEK_API_KEY=<key> in claw.env and re-run ./start.sh."
ok "deepseek / ${CLAW_MODEL:-deepseek-v4-pro}"

step "Web search"
if [ -n "${WEB_BACKEND:-}" ]; then
  key_name="$(web_key_name "$WEB_BACKEND")"
  [ -n "$key_name" ] || fail "WEB_BACKEND=$WEB_BACKEND not recognised (tavily, exa, firecrawl, parallel, keenable, perplexity)."
  hermes config set web.backend "$WEB_BACKEND" >/dev/null
  if is_fresh_secret "${WEB_API_KEY:-}"; then hermes config set "$key_name" "$WEB_API_KEY" >/dev/null; fi
  if has_env_key "$key_name"; then ok "$WEB_BACKEND with API key"; else warn "$WEB_BACKEND without a key (keyless tier — expect rate limits)"; fi
else
  warn "no WEB_BACKEND — using Hermes's keyless free tiers; scouts will hit rate limits"
fi

step "Judge model (optional)"
if [ -n "${CLAW_JUDGE_API_KEY_NAME:-}" ] && is_fresh_secret "${CLAW_JUDGE_API_KEY:-}"; then
  hermes config set "$CLAW_JUDGE_API_KEY_NAME" "$CLAW_JUDGE_API_KEY" >/dev/null
fi
if [ -n "${CLAW_JUDGE_MODEL:-}" ]; then ok "${CLAW_JUDGE_PROVIDER:-deepseek} / $CLAW_JUDGE_MODEL for lead, verifier, redteam"; else ok "judges use CLAW_MODEL"; fi

step "GitHub"
if is_fresh_secret "${GH_TOKEN:-}"; then
  if printf '%s' "$GH_TOKEN" | gh auth login --with-token >/dev/null 2>&1; then ok "gh authenticated"; else warn "GH_TOKEN rejected by gh — scouts fall back to unauthenticated git"; fi
elif gh auth status >/dev/null 2>&1; then ok "gh already authenticated"
else warn "no GH_TOKEN — scouts use unauthenticated git/web (fine, slower)"; fi

step "Moving secrets out of claw.env"
python3 - "$ENV_FILE" "$STORED" $CLAW_SECRET_KEYS <<'PY'
import pathlib, re, sys
path, stored, keys = pathlib.Path(sys.argv[1]), sys.argv[2], set(sys.argv[3:])
out, moved = [], []
for line in path.read_text().splitlines():
    m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
    if m and m.group(1) in keys:
        value = re.sub(r"\s+#.*$", "", m.group(2)).strip()
        if value and value != stored:
            line = f"{m.group(1)}={stored}"
            moved.append(m.group(1))
    out.append(line)
path.write_text("\n".join(out) + "\n")
print("  ✓ " + (", ".join(moved) + " → Hermes" if moved else "nothing new to move"))
PY
chmod 600 "$HERMES_HOME/.env" 2>/dev/null || true
