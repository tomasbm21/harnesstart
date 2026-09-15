# Norfront Claw — BRIEF

v1 · 2026-09-11 · Owner: Tomas · Read by every agent in the swarm.

This brief says **what** Norfront Claw must do and **how** options get judged. It deliberately doesn't say how to build it. The swarm scouts the market, proposes competing architectures, tests the finalists against each other, and only then writes `SPEC.md`.

## 1. The goal

Hermes-style self-improving agents that work as a swarm, where each agent has a real, persistent computer (disk, shell, browser, screen) isolated at the hardware level. It's like Grok Bot, but open source and on hardware Norfront controls.

It serves Norfront's own ops agents first (outbound, marketing, research, vendor readiness, asset tracking), and paying clients later.

## 2. Hard requirements (Tomas's decisions)

A proposal that breaks one of these is out, unless it includes a **waiver request**: which requirement, why breaking it wins, and what it costs. Only Tomas grants waivers, at GATE-A.

- **R1 · Host.** Runs on Tomas's MacBook (Apple Silicon, ~48 GB RAM) inside a Linux VM. There must also be a credible path to always-on Linux boxes for clients.
- **R2 · Hardware isolation.** Agent computers are separated by a VM boundary, not just containers or processes.
- **R3 · Persistence.** Files, browser sessions and logins survive restarts.
- **R4 · Open and self-hosted.** Open-source components. No required hosted control plane or vendor account to run it.
- **R5 · Two customers.** Norfront internal first. The design must not block one-deployment-per-client later.
- **R6 · Human control.** Irreversible actions (send, post, pay, delete, sign up) need Tomas's approval. Secrets are never exposed to paths that carry untrusted content.
- **R7 · Swarm.** Multiple specialised agents coordinate on durable work. Tomas can see what each is doing and steer.
- **R8 · Model reality.** Must work with DeepSeek-class models, which is what the swarm itself runs on. Don't assume frontier-model reliability for tool calling.

## 3. Open questions — the swarm answers these

| # | Question |
|---|---|
| Q1 | Isolation unit: one VM per agent, per trust zone, per task, or one shared computer (Grok Bot style)? |
| Q2 | VM technology and manager that runs inside a Linux VM on Apple Silicon *and* on bare Linux. |
| Q3 | Where the agent brain runs: on the host, inside each VM, or split. |
| Q4 | Agent runtime: Hermes is the incumbent, not a given. Also decide adopt vs plugin vs fork. |
| Q5 | Coordination: board/blackboard, chat, A2A, supervisor, market-based. How the human steers. |
| Q6 | Computer use: headless browser, full desktop, or both. How Tomas watches and takes over. |
| Q7 | Secrets and egress: brokers, proxies, per-agent or per-zone policy, prompt-injection containment. |
| Q8 | Client deployment model: host per client, VM per client, shared control plane. |
| Q9 | Observability and cost control across the swarm. |
| Q10 | Build vs adopt, and the smallest v1 that proves the whole thing. |

## 4. Rubric (fixed before scouting; only Tomas changes it)

First, a pass/fail check against R1–R8. Then a score out of 100:

| Weight | Criterion | What "good" looks like |
|---|---|---|
| 20 | Isolation and security | Strong boundary, contained blast radius, secrets and egress handled by design |
| 15 | Real-computer fidelity | Persistent disk, browser sessions, desktop; Tomas can watch and take over |
| 15 | Operable on one MacBook | Fits the RAM budget, sets up in an afternoon, survives sleep and reboot |
| 15 | Maturity and maintainer health | Active commits, permissive license, more than one maintainer, real users, docs |
| 10 | Client portability | The same design stands up on a client's Linux box without rework |
| 10 | Swarm quality | Durable handoffs, human gates, visibility, no chat-storm interruptions |
| 10 | Build effort | A small team (or this swarm) ships v1 in weeks, not months |
| 5 | Differentiation | A reason a client picks this over Grok Bot, Orgo or a hosted agent product |

Scores need a one-line justification that points to evidence: a registry id, a test result or a source URL.

## 5. How the swarm works

```
F0 check tools ─► D1…D7 scout the market (3 lenses, in parallel)
               ─► V1 fact-check ─► M1 map the options
               ─► three blind proposals (lean · fortress · market)
               ─► R1 red team (+ unseals Proposal Z) ─► J1 judge
               ─► GATE-A Tomas picks finalists
               ─► T0 test harness ─► K1/K2 prototype finalists ─► V2 verify
               ─► B0 decision memo + SPEC.md + build plan
               ─► GATE-B Tomas approves ─► build board seeded from swarm/build.yaml
```

Where things live:

- `research/candidates/*.yaml`: every component, product and pattern found. This is the registry.
- `research/scouting/*.md`: scout narratives.
- `research/landscape.md`: the options map.
- `research/proposals/*.md`: the competing architectures.
- `research/redteam.md`: red-team findings.
- `research/decision-A.md`, `research/decision-B.md`: the two decision memos.
- `research/bakeoff/`: prototype results.
- `SPEC.md` and `swarm/build.yaml`: written at B0.

## 6. Known context (facts, not recommendations)

- Tomas already ran a 3-agent Hermes system on Discord. Agents @mentioning each other interrupted each other's work.
- Tomas's current Grok ops roster is 5 agents: Outbound, Marketing/Content, Research, Vendor Readiness, Asset Tracker. There's no orchestrator bot.
- A Grok-generated repo list exists. Some of its claims were wrong: Grok Bot doesn't give each bot its own VM, all of a user's bots share one. Use that list as leads only and verify everything.
- `swarm/sealed/` holds a baseline written before any market scan. It's sealed so it doesn't anchor the scouts.
