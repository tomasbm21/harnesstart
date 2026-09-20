# Norfront Claw

Hermes-style agents with Grok Bot–style computers, running on hardware Norfront controls.

**The architecture isn't decided yet, on purpose.** A swarm of DeepSeek agents scouts the market, writes competing architectures, red-teams them, prototypes the finalists against identical tests, and only then writes `SPEC.md` and a build plan. You make the calls at two gates.

## Start

### Linux cloud

Use `./product/claw` (Prime Agent + Jev hook). See `product/README.md`. `./start.sh` is Darwin/Lima only.

### Mac swarm

1. Put your keys in `claw.env`. The first `./start.sh` creates the file for you.
   - `DEEPSEEK_API_KEY` is required.
   - `WEB_BACKEND` + `WEB_API_KEY` are strongly recommended.
2. Open your agent (Claude Code on DeepSeek, Hermes, anything) in this folder and say **"start"**.
   - It follows `START.md` and runs `./start.sh`.
   - Or run `./start.sh` yourself.

The first Mac run takes about 20 minutes: it checks the Mac, creates a Linux VM with nested virtualization, installs Hermes, configures 8 agent profiles, seeds 22 cards, checks readiness (including a model ping) and starts the swarm.

```bash
./start.sh status                  # progress, blocked cards, gates waiting for you
./start.sh watch                   # live events
./start.sh approve GATE-A "note"   # your decisions
./start.sh answer <card-id> "…"    # reply to a blocked card
./start.sh stop                    # pause; ./start.sh resumes
```

**Needs:** Apple M3 or newer, macOS 15+, Homebrew, ~24 GiB RAM and 60 GiB+ disk for the VM. Set a spend cap at DeepSeek before you start.

## The swarm

| Profile | Job |
|---|---|
| `lead` | Coordinates and judges: maps options, scores proposals, writes the SPEC and build plan |
| `lean` · `fortress` · `market` | Scouts with three different lenses (simplest, most secure, most sellable); each writes one blind proposal |
| `verifier` | Fact-checks claims and bake-off numbers; reviews code during the build |
| `redteam` | Breaks every proposal, including sealed Proposal Z, and pulls the best idea from each |
| `infra` · `platform` | Prototype the finalists, then build the winner |

Flow:

1. Tools check.
2. Seven scouts cover the market.
3. The verifier fact-checks, and the lead maps the options.
4. Three blind proposals, then the red team, then the judge.
5. **GATE-A:** you pick the finalists.
6. Bake-off prototypes, then the verifier checks the results.
7. The lead writes SPEC and the build plan.
8. **GATE-B:** you approve.
9. `./start.sh build`.

## What's in here

```
start.sh          the one command (run on the Mac)
START.md          operator runbook, what your agent follows when you say "start"
AGENTS.md CLAUDE.md .hermes.md   entry prompts (operator vs swarm worker)
BRIEF.md          goal, hard requirements R1–R8, open questions Q1–Q10, rubric
SPEC.md           empty until card B0
claw.env.example  settings template (claw.env itself is gitignored)
host/             Linux VM on the Mac: Lima template, preflight, provisioning
swarm/            rules, souls, cards, templates, scripts 25–70, approve, verifier tool
swarm/sealed/     Proposal Z: only the red team and judge open it
research/         created by the swarm: everything it finds
product/          Linux-cloud runtime (Prime Agent brain, Jev browser hook)
```
# harnesstart
