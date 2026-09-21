# Norfront Claw — Linux cloud product

Prime Agent is the **brain**. Jev Ultrafast is the **browser** in `product/jev/` (stacked from [PR #1](https://github.com/tomasbm21/harnesstart/pull/1)). The **R2 VM computer** is `product/vm/` (stacked from [PR #3](https://github.com/tomasbm21/harnesstart/pull/3)). This tree is the Linux-cloud runtime: not Hermes, not Tomas’s Mac, not Remote Control.

This PR contains `product/claw`, `product/jev/`, and `product/vm/`.

Config is environment-only (`claw.env` plus process env). Keys are never printed.

## Run on Cursor Linux cloud

```bash
# from the harnesstart repo root
./product/claw doctor          # also runs ./product/vm/claw-vm doctor (never --probe-vcpu)
./product/claw test            # offline unit tests; no vendor keys
./product/claw guards          # local R6 broker + Jev check_guards(); no TypeSafe key
./product/claw observe URL     # claw_jev.observe(); no TypeSafe key
./product/claw policy          # claw_jev.policy_status() booleans; no key values
```

Install the brain (official Prime Agent Linux binary + Python kernel):

```bash
./product/claw install
export PATH="$HOME/.local/bin:$PATH"
```

Put `DEEPSEEK_API_KEY` in repo-root `claw.env` (copy `claw.env.example`). Do not paste keys in chat.

On a real terminal, `./product/claw doctor` and `./product/claw run` prompt once (hidden) for a missing DeepSeek key and write it to `claw.env`. `doctor` also offers TypeSafe (Enter skips). `choose` / `browse` prompt for TypeSafe. Non-TTY/CI never prompts.

Skip prompts: `./product/claw --no-prompt doctor` or `CLAW_NO_KEY_PROMPT=1`.

```bash
./product/claw run "Reply with pong"    # needs DeepSeek in env
./product/claw status
./product/claw stop
```

Live Jev policy reads `TYPESAFE_API_KEY` from **env** (never chat):

```bash
./product/claw choose URL GOAL    # observe + claw_jev.choose(); exit 2 if the key is missing
./product/claw browse URL GOAL    # claw_jev.run(); exit 2 if the key is missing
```

`observe` / `guards` / `policy` / `doctor` keep working when that key is unset.

Live Chrome observe needs the Jev extra once:

```bash
cd product/jev && uv sync --extra dev
```

## Layout

| Path | Role |
| --- | --- |
| `product/claw` | Entrypoint |
| `product/norfront_claw/` | Config, doctor, Prime wrapper, R6 guards, claw_jev + claw-vm hooks |
| `product/jev/` | `claw_jev` package (dedicated Chrome + Jev Ultrafast) |
| `product/vm/` | `claw_vm` package (Firecracker preferred; QEMU TCG on this nested host) |
| `product/prime-prompt.md` | Appended to Prime Agent; `--no-context-files` so repo `AGENTS.md` is not loaded |
| `~/.local/share/norfront-claw/workspace` | Prime Agent cwd (not the harness git tree) |

## Jev adapter hook

The core loads `product/jev` onto `sys.path` and imports the public surface:

```python
from claw_jev import (
    ClawJev,
    observe,
    check_guards,
    choose,
    run,
    policy_status,
    doctor,
)
```

| Call | `TYPESAFE_API_KEY` |
| --- | --- |
| `observe` / `check_guards` / `doctor` / `policy_status` | no |
| `choose` / `run` | **yes** (env). Raises `PolicyUnavailable`; CLI exits 2 |

Override discovery with `CLAW_BROWSER_ADAPTER=module:factory` (tests). If `product/jev/claw_jev` is absent, commands that only need observe/guards still run; live policy fails with “adapter missing”.

## R2 VM hook

`./product/claw doctor` shells out to `./product/vm/claw-vm doctor --json` when that script exists. It never passes `--probe-vcpu` (nested `KVM_CREATE_VCPU` kernel-BUGs on this host). Direct check:

```bash
./product/vm/claw-vm doctor
```

## Still stubbed

- **R2 hardware KVM** — this nested cloud host kernel-BUGs on `KVM_CREATE_VCPU`. Do not pass `--probe-vcpu`. Default computer is QEMU TCG (still a VM boundary). Firecracker on hosts where nested KVM works.
- **Live model turn** — needs `DEEPSEEK_API_KEY` in env; doctor does not.
- **Live Jev policy** — needs `TYPESAFE_API_KEY` in env; fails R4 unless Tomas waives it.
- **Prime bash permission extension** — R6 is a prompt-level classifier on `claw run` / `claw browse` / `claw choose`, not an in-kernel Prime extension.
- **Hermes kanban / GATE-A/B** — out of this product; `claw agents` wraps Prime sessions.
- **Desktop watch/takeover** — Jev inspector is adapter-side (`claw-jev`), not this CLI.

## Commands

| Command | Keys |
| --- | --- |
| `doctor` / `status` / `guards` / `observe` / `policy` | none required |
| `install` | network for the Prime installer |
| `run` | `DEEPSEEK_API_KEY` |
| `choose` / `browse` | `TYPESAFE_API_KEY` (and `product/jev`) |
| `stop` / `agents` | Prime Agent installed |

Irreversible intents (send / post / pay / delete / sign up) are blocked unless `CLAW_ALLOW_IRREVERSIBLE=1` is set in env.
