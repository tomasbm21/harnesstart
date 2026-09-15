# START — operator runbook

You're the operator (see AGENTS.md). Everything runs through `./start.sh` on the Mac. It's safe to re-run at any point: finished steps are skipped.

## What Tomas says → what you run

| Tomas says | You run | Then |
|---|---|---|
| start / go / run it | `./start.sh` | Relay each `== n/6` step in one line. When it finishes, run `./start.sh status` and summarise. |
| status / how's it going | `./start.sh status` | Summarise: running, blocked, and gates waiting for him. |
| check / doctor | `./start.sh doctor` | Report READY, or the exact problems. |
| approve GATE-A (or GATE-B) + his note | `./start.sh approve GATE-A "<his exact words>"` | Only when he explicitly says approve. |
| what's blocked / show me card X | `./start.sh show <card-id or key>` | Explain it in plain words. |
| answer / reply to a blocked card | `./start.sh answer <card-id> "<his exact words>"` | |
| build (after GATE-B) | `./start.sh build` | |
| stop / pause | `./start.sh stop` | |

## Before the first start

0. **Check the script can run.** If `./start.sh` says "permission denied", run `chmod +x start.sh` once.
1. **Check where you are.** If `uname -s` isn't `Darwin`, you're inside claw-host, not on the Mac. Tell Tomas to open you in the folder on his Mac instead.
2. **Check `claw.env`.** If it doesn't exist, run `./start.sh` once: it creates `claw.env` and stops. Ask Tomas to open the file and paste:
   - `DEEPSEEK_API_KEY` (required)
   - ideally `WEB_BACKEND` + `WEB_API_KEY` (e.g. tavily)
   - optionally `GH_TOKEN`

   Don't read the values back or ask for keys in chat. To check whether a key is filled, only test that the line isn't empty.
3. **Warn about timing.** The first run takes ~20 minutes (VM download, apt, Hermes install). Later runs take about a minute.

## When a step fails

Read the `✗` line, match it below, fix, and re-run `./start.sh`. Don't improvise around hard failures.

| Failure | What to do |
|---|---|
| `Nested virtualization needs Apple M3 or newer` or `macOS 15+` | **Stop.** This Mac can't run hardware VMs inside a VM (BRIEF R1/R2). Tell Tomas; don't work around it. |
| `Install Homebrew first` | Tell Tomas to install Homebrew from https://brew.sh, then re-run. |
| `limactl create` / `start` errors | Run `limactl list`. If claw-host is `Broken`, show Tomas the error and ask before `limactl delete claw-host` (that wipes the VM, not the folder). |
| `/dev/kvm missing` | Check `host/claw-host.yaml` has `nestedVirtualization: true`. If it does, the VM was created before the flag: ask Tomas, then `limactl delete claw-host` and re-run. |
| apt / curl / install errors during provisioning | Usually network. Wait a minute and re-run. |
| `No DeepSeek key` / `DEEPSEEK_API_KEY is empty` | Tomas pastes the key into `claw.env`, then re-run. |
| `did not answer` in the model ping, or 401/403 | The key or model is wrong. Tomas replaces `__stored_in_hermes__` in `claw.env` with a fresh key, then re-run. |
| `model … not found` | Set `CLAW_MODEL` in `claw.env` to a name from Hermes's DeepSeek catalog (`deepseek-v4-pro` or `deepseek-flash`), then re-run. |
| `claw-explore should have 22 cards` | Run `limactl shell --workdir /srv/claw claw-host bash swarm/40-seed-board.sh explore`, then re-run. |
| `NOT READY` with other lines | Fix the line named. Each one says which script to re-run. |
| `gateway exited straight away` | Run `./start.sh logs`, show Tomas the last lines, and fix only if the cause is obvious (e.g. a bad key). |

## While the swarm runs

- **Blocked cards.** `./start.sh status` shows each one with its id. Run `./start.sh show <id>` and relay the question to Tomas in plain words. When he answers, run `./start.sh answer <id> "<his words>"`.
- **Gates.** When status shows `★ WAITING FOR TOMAS`:
  - GATE-A: read `research/decision-A.md`.
  - GATE-B: read `research/decision-B.md`.

  Give Tomas a neutral 5-line summary (options, scores, what's being decided, what the red team flagged). Don't recommend unless he asks. Approve only on his explicit instruction.
- **Research.** Everything lands in `research/`. You may read it to answer Tomas's questions. Don't edit it.
- **Problems.** If a card keeps failing or the gateway stops, use `./start.sh logs` and `./start.sh status`. Restarting with `./start.sh` is safe.

## Never

- Do the swarm's work, or edit `BRIEF.md`, `swarm/RULES.md`, `swarm/explore.yaml`, `swarm/souls/` or `swarm/templates/` to steer results. Only edit these when Tomas asks, and then add a line to the file's changelog.
- Open `swarm/sealed/`.
- Print or commit secrets.
- Delete the VM, boards, `research/` or `.git` without Tomas's OK.
