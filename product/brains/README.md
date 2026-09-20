# Norfront Claw — optional Linux-cloud brains

Prime Agent stays the **default** brain in `product/claw`. This tree is `product/brains/` only: OpenHands, OpenClaw, and Goose as selectable Linux-cloud backends. It does not edit BRIEF, souls, sealed, or take over `product/claw`.

The claw CLI can call it later (same idea as `claw-vm doctor --json`):

```python
from claw_brains import doctor, selected, select, list_brains
```

```bash
./product/brains/claw-brains doctor --json
```

## Select a brain

From the harnesstart repo root:

```bash
./product/brains/claw-brains list
./product/brains/claw-brains doctor
./product/brains/claw-brains select goose     # or openhands | openclaw | prime
./product/brains/claw-brains selected
```

`CLAW_BRAIN` in the process environment (or `claw.env`) wins over the file written by `select`. Default when neither is set: **prime**.

```bash
CLAW_BRAIN=openclaw ./product/brains/claw-brains doctor
```

Install an optional backend (official Linux installer; noninteractive; no onboard/configure TUI):

```bash
./product/brains/claw-brains install goose
./product/brains/claw-brains install openhands
./product/brains/claw-brains install openclaw
```

Prime install stays `./product/claw install` when that tree is present.

## Live turns

```bash
./product/brains/claw-brains run "Reply with pong"
./product/brains/claw-brains run --brain goose "Reply with pong"
```

Without `DEEPSEEK_API_KEY` (or the backend’s own key) the turn is **stubbed** (exit 2). Put keys in `claw.env` locally. Do not paste keys in chat. Keys are never printed and never placed on argv (`--api-key` is refused).

| Brain | Binary | Headless turn | Key |
| --- | --- | --- | --- |
| prime (default) | `prime-agent` | `prime-agent -p --mode json …` | `DEEPSEEK_API_KEY` |
| openhands | `openhands` | `openhands --headless --json --override-with-envs -t …` | `LLM_API_KEY` or `DEEPSEEK_API_KEY` |
| openclaw | `openclaw` | `openclaw agent exec --auth-env-only --json …` | `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` |
| goose | `goose` | `goose run --no-session --output-format json -t …` | `DEEPSEEK_API_KEY` or `OPENAI_API_KEY` |

These are **host processes**. Pair with `product/vm` for BRIEF R2. OpenHands’ default Docker sandbox is not started here (this cloud host has no Docker). OpenClaw’s default host tools are not a VM; isolate it.

## Layout

| Path | Role |
| --- | --- |
| `product/brains/claw-brains` | Entrypoint |
| `product/brains/claw_brains/` | Python API |
| `~/.local/share/norfront-claw/brains/selected` | Last `select` (override `CLAW_BRAINS_HOME`) |
| `~/.local/share/norfront-claw/workspace` | Agent cwd (not the harness git tree) |

## Tests

```bash
python3 -m unittest discover -s product/brains/tests -v
# or:
./product/brains/claw-brains test
```
