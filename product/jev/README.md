# Claw Jev adapter

Dedicated Chrome + [Jev Ultrafast](https://github.com/browser-use/jev-ultrafast) for Norfront Claw on **Cursor Linux cloud**. This is the Q6 browser plugin, not the agent brain.

Pinned upstream: `jev-ultrafast@1231850` (evaluated on this host). Policy model is TypeSafe; observe and guards do not call it.

## What the core imports

```python
from claw_jev import (
    ClawJev,          # session: start Chrome, observe, choose, run
    observe,          # one-shot snapshot
    check_guards,     # local freshness/execution (21 checks)
    choose,           # TypeSafe policy (env)
    run,              # full Agent loop (env)
    policy_status,    # booleans only; never returns key values
    doctor,           # chrome / dedicated profile / CDP / policy flags
    stop_chrome,      # kill the dedicated browser only
    PolicyUnavailable,
    HumanProfileError,
)
```

`observe` / `check_guards` / `doctor` / `policy_status` work with `TYPESAFE_API_KEY` **unset**.

`choose` and `run` read keys from the **environment** (or `--env-file`). Do not paste keys in chat.

## Linux-cloud observe of example.com

Needs native Chrome (this image: `/opt/google/chrome/google-chrome`), Python 3.12, and network. `DISPLAY=:1` is used when set; otherwise Chrome starts headless. `--no-sandbox` is on by default on Linux (`CLAW_JEV_SANDBOX=1` to opt out).

```bash
cd product/jev
uv sync --extra dev          # or: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
uv run claw-jev doctor --start --json
uv run claw-jev observe https://example.com
# optional JPEG (not dumped on stdout):
uv run claw-jev observe https://example.com --screenshot artifacts/example.com.jpg
uv run claw-jev guards
```

Chrome uses a **dedicated** `--user-data-dir` (default `~/.local/share/norfront-claw/jev-chrome`), never `~/.config/google-chrome`. CDP is loopback `http://127.0.0.1:9333` (`CLAW_JEV_CDP_PORT`). browser-harness daemon name is `claw-jev` via `BU_CDP_URL` + `BU_NAME`.

Pytest (offline unit tests always; live marks need Chrome):

```bash
uv run pytest
uv run pytest -m live
```

## What needs a TypeSafe key

| Call | `TYPESAFE_API_KEY` | `TEXT_MODEL_API_KEY` |
| --- | --- | --- |
| `observe` / `claw-jev observe` | no | no |
| `check_guards` / `claw-jev guards` | no | no |
| `doctor` / `policy_status` | no (reports whether set) | no |
| `choose` / Jev `predict` | **yes** | no |
| `run` / `claw-jev run` (CLICK/SELECT/WAIT/DONE) | **yes** | no |
| `run` when the policy picks `TYPE_TEXT` | **yes** | **yes** |

Put keys in the process environment (or `uv run --env-file …`). Do not put them in chat, commit them, or pass them as CLI flags.

Live loop:

```bash
export TYPESAFE_API_KEY=   # set locally, not here
export TEXT_MODEL_API_KEY= # only if a field must be typed
uv run claw-jev run --url https://example.com --goal 'Stop when the Example Domain heading is visible.'
```

Without the TypeSafe key, `choose`/`run` raise `PolicyUnavailable` and the CLI exits 2.

## Env (non-secret)

| Variable | Default | Role |
| --- | --- | --- |
| `CLAW_JEV_USER_DATA_DIR` | `$XDG_DATA_HOME/norfront-claw/jev-chrome` | Dedicated profile; human paths are rejected |
| `CLAW_JEV_CDP_PORT` | `9333` | Loopback remote-debugging port |
| `CLAW_JEV_CHROME` | `/opt/google/chrome/google-chrome` if present | Browser binary |
| `CLAW_JEV_HEADLESS` | unset → headless only when `DISPLAY` is empty | `1`/`0` |
| `CLAW_JEV_SANDBOX` | unset → `--no-sandbox` on Linux | `1` enables sandbox |
| `BU_CDP_URL` / `BU_NAME` | set by the adapter | Harness must not scan the default profile |
| `TYPESAFE_API_KEY` | unset | Live `choose()`/`run()` |
| `TEXT_MODEL_API_KEY` | unset | Live `TYPE_TEXT` only |
| `TYPESAFE_MODEL` | `jev-latest` | Policy model name |
| `TEXT_MODEL` / `TEXT_MODEL_BASE_URL` | DeepSeek defaults in Jev | Text helper |

Chrome's subprocess environment is stripped of `*_API_KEY` / `*_TOKEN` values. Page content still goes to TypeSafe on `choose()` — that is upstream Jev, not this adapter.
