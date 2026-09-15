#!/usr/bin/env bash
# Shared helpers. Sourced by start.sh (macOS bash 3.2) and swarm/*.sh (claw-host) — keep it bash-3.2 compatible.

STORED="__stored_in_hermes__"
CLAW_SECRET_KEYS="DEEPSEEK_API_KEY WEB_API_KEY GH_TOKEN CLAW_JUDGE_API_KEY"

ok()   { printf '  ✓ %s\n' "$1"; }
warn() { printf '  ! %s\n' "$1"; }
fail() { printf '  ✗ %s\n' "$1" >&2; exit 1; }
step() { printf '\n== %s\n' "$1"; }

# Read KEY=VALUE lines without executing anything. Strips trailing "  # comments" and surrounding quotes.
load_env() {
  local file="$1" line key val
  [ -f "$file" ] || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ''|'#'*) continue ;; esac
    key="${line%%=*}"
    val="${line#*=}"
    if ! printf '%s' "$key" | grep -Eq '^[A-Z_][A-Z0-9_]*$'; then continue; fi
    val="$(printf '%s' "$val" | sed -E 's/[[:space:]]+#.*$//; s/^[[:space:]]+//; s/[[:space:]]+$//; s/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/')"
    export "$key=$val"
  done < "$file"
}

# True when a secret value is present and not already moved into Hermes.
is_fresh_secret() { [ -n "${1:-}" ] && [ "$1" != "$STORED" ]; }

# Env var name Hermes uses for a web backend's API key.
web_key_name() {
  case "$1" in
    tavily) echo TAVILY_API_KEY ;; exa) echo EXA_API_KEY ;; firecrawl) echo FIRECRAWL_API_KEY ;;
    parallel) echo PARALLEL_API_KEY ;; keenable) echo KEENABLE_API_KEY ;; perplexity) echo PERPLEXITY_API_KEY ;;
    brave) echo BRAVE_SEARCH_API_KEY ;; *) echo "" ;;
  esac
}
