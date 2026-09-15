> **SEALED — Proposal Z (Claude's baseline, 2026-09-11).**
> Do not open this file unless your card tells you to (only R1 red team and J1 judge do).
> It has no special status: it competes against the swarm's proposals on the same rubric.

# Proposal Z — Claude baseline

v0.1 · 2026-09-11 · Written by Claude from a one-session review of a Grok-generated repo list. No market scan behind it.

## 1. What it is

Hermes agents with persistent, hardware-isolated computers, running on hardware Norfront controls.

The split copies Grok Bot. The brain (model calls, memory, task board) lives outside the computer. The computer (disk, shell, browser, screen) is a Firecracker microVM that keeps its state between sessions.

Two customers, in this order:

1. **Norfront internal** (tenant `norfront`): the 5-agent ops roster.
2. **Clients, later**: the same stack, with one claw-host per client.

This is not a Hermes fork. It's vanilla Hermes (pinned), plus a thin `claw` CLI, VM images and config.

## 2. Building blocks (verified 2026-09-11)

| Layer | Choice | Why | Caveat |
|---|---|---|---|
| Linux VM on the Mac | Lima 2.x, `vmType: vz`, `nestedVirtualization: true` | Gives the guest `/dev/kvm`, which Firecracker needs | Apple M3+ and macOS 15+ only |
| MicroVMs | SmolVM (Apache-2.0), Firecracker backend | CLI + Python SDK, persistent disks, browser sandbox (CDP + noVNC), snapshots, network controls, built-in `hermes` preset | v0.0.33, pre-1.0. Spikes S1–S3 either prove it or we switch to the fallback at GATE-1 |
| Fallback | 0xthierry/microvm (MIT: Dockerfile → Firecracker, persistent disks, SSH, blocks VM-to-VM traffic) or raw Firecracker | | Beta, or more work |
| Brain | Hermes Agent (MIT) @ tag v2026.9.11 (0.21.2) | Profiles = agents. Kanban = durable multi-agent board. SSH terminal backend, `browser.cdp_url`, cron routines, Discord gateway, `kanban swarm` | Kanban is single-host with a single trusted user, by design |

Kanban tools run inside the agent's own process on claw-host. So the board keeps working when an agent's terminal points at a remote computer.

Rejected:

- OpenClawMachines: OpenClaw only, needs Linux hosts plus Cloudflare.
- NemoClaw: different isolation model (OpenShell).
- zeroboot / AgentENV: built for dense, short-lived sandboxes, not persistent computers.
- Forking Hermes: it ships changes daily.

## 3. Architecture

```
MacBook (macOS)
└── claw-host  — Lima VM, Ubuntu 24.04, nested virt            ← TENANT BOUNDARY
    ├── Hermes: gateway + Kanban dispatcher + agent profiles   ← brain: LLM keys, memory, board
    ├── claw CLI · egress enforcement · systemd units          ← control
    └── Firecracker microVMs (SmolVM)                          ← hands: disk, shell, browser, screen
        ├── read   → research, marketing
        ├── act    → outbound (+ publishing)
        └── vault  → vendor-readiness, asset-tracker
```

Rules:

- **One claw-host per tenant.** Clients never share a host. Hermes Kanban assumes a single trusted user.
- **Computers are trust zones, not one per agent.** Grok Bot shares a single computer across all of a user's bots. We split by how much damage a compromised agent could do. No zone gets all three of: private data, untrusted web content, and the ability to send things out.

| Zone | Untrusted web | Private data | Sends out | Egress |
|---|---|---|---|---|
| read | yes | no | no | open HTTP/S, no SMTP |
| act | limited | account logins | yes, human-approved | allowlist only |
| vault | no | internal docs, read-only | no | none |

- **Secrets stay in the brain.** LLM and API keys live only in the profile `.env` files on claw-host. Logins inside `act` are done by Tomas through the noVNC viewer.
- **A zone is computer egress plus profile toolsets.** Hermes web tools run in the brain process, so `vault` agents must also have the `web`, `search` and `browser` toolsets disabled.
- **Agents hand off work only through Kanban cards and comments.** Discord is for the human: review requests, blocked cards, the daily digest. Agents don't @mention each other.
- **Irreversible actions need Tomas.** Sending, posting, paying, deleting and signing up all go through `kanban_request_review`.

## 4. Config contract — `tenant.yaml`

```yaml
tenant: norfront
computers:
  read:  { memory_mib: 3072, disk_gib: 20, egress: open-web }
  act:   { memory_mib: 3072, disk_gib: 20, egress: { allow: [] } }   # Tomas fills in mail/LinkedIn/CRM hosts at GATE-2
  vault: { memory_mib: 2048, disk_gib: 10, egress: none, context_ro: /srv/context/norfront-context }
agents:
  research:         { computer: read }
  marketing:        { computer: read }
  outbound:         { computer: act }
  vendor-readiness: { computer: vault, toolsets_off: [web, search, browser] }
  asset-tracker:    { computer: vault, toolsets_off: [web, search, browser] }
routines:
  vendor-readiness: "0 8 * * 1"    # Mondays 08:00
  asset-tracker:    "0 16 * * 5"   # Fridays 16:00
```

The spikes decide how `context_ro` gets delivered: a mount, an upload or a git bundle. SmolVM shared folders don't work together with restricted egress.

## 5. `claw` CLI contract (Python 3.11+, uv)

```
claw doctor                         host checks: kvm, smolvm, hermes, pinned versions
claw up | down                      everything in tenant.yaml, in order: egress → computers → agents → gateway
claw computer up|stop|status|viewer <name>
claw egress apply | test <computer> <url>
claw agent sync                     tenant.yaml → Hermes profiles (SOUL, toolsets, SSH backend, CDP URL)
claw secrets audit                  fails if any key material exists inside a computer
claw lanes install                  runtime board + lanes + routines
claw export | import <bundle>       tenant portability (keys stripped)
```

`ComputerProvider` interface. SmolVM goes first; the fallback must be swappable.
`create · start · stop · status · ssh_target() → (host, port, user, key_path) · cdp_url() · viewer_url() · snapshot(name) · restore(name)`

State goes in `/var/lib/claw/`, never in the repo mount.

## 6. Acceptance criteria — done when all of these pass on clean `main`

1. `claw up` from nothing brings up 3 computers and 5 agents. Running it again changes nothing.
2. A file written inside a computer survives `claw computer stop` / `up` and a claw-host reboot.
3. Computers can't reach each other. `vault` has no egress, and `act` reaches only its allowlist.
4. `claw secrets audit` passes: no LLM or API keys inside any computer.
5. A card assigned to `research` runs its shell commands inside `read` (proven by hostname) and drives `read`'s browser.
6. The outbound dry run works end to end: research → draft → review (waits for Tomas) → approve → send to a local sink mailbox → asset-tracker logs it. Nothing is sent before approval.
7. Everything comes back on its own after the Mac sleeps or claw-host reboots.
8. Tomas can watch any computer's screen from a browser on the Mac, over localhost.

## 7. Known risks

- SmolVM is pre-1.0. It's pinned, and GATE-1 decides whether to keep it.
- Nested virtualization costs speed. S1 measures boot time and RAM.
- The Mac sleeps. That's fine for internal use; client deployments need an always-on Linux box running the same provisioning script without Lima (card P1).
- Kanban comments carry web content from `read` into what `act` agents read. The human review gate on irreversible actions is the backstop.
- Better infrastructure doesn't make agent output better. Output quality is a model, prompt and targeting problem. The review gate only stops bad output from going out.

## Changelog

- v0.1 — initial spec (Tomas + Claude).
