# Rules for `swarm/build.yaml` (the lead writes it at B0)

Use the same schema as `swarm/explore.yaml`: `key`, `title`, `assignee`, `parents`, `body`, optional `gate: true`, optional `max_runtime`.

## Structure

- **Keys** start with `B-` (e.g. `B-C1`). Parents appear before children.
- **Assignees:** `infra`, `platform`, `verifier`, `lead`. Scouts are only for the market-watch card.
- **Size:** at most 30 cards. If the plan is bigger, split it into releases and only seed release 1.
- **Card bodies** follow Goal / Do / Deliver / Done when. Each card is at most a day of agent work, with `max_runtime` ≤ 4h.
- **Phases** each end with a `verifier` acceptance card that runs tests on clean `main`.

## Required cards (whatever the architecture)

1. A **dry run with fake accounts and sinks** before anything real.
2. A **go-live gate** (`gate: true`) where Tomas connects real accounts and sets a spend cap.
3. **Restart resilience:** everything comes back after the Mac sleeps or the host reboots.
4. **Secrets audit:** no keys inside agent computers or git.
5. **Tomas can watch and steer:** see each agent's current work and screen, approve irreversible actions.
6. **Client portability:** the same stack stands up on a plain Linux KVM box.
7. **Monthly market watch:** a routine that re-checks `research/candidates/` and scouts for new entrants, and reports only when something beats a chosen component by 10 or more rubric points. It's report-only: any change goes through a gate.

## Traceability

Every card's body names the `SPEC.md` section it implements. Every SPEC section is covered by at least one card.
