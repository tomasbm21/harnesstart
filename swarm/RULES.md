# Swarm rules (every agent)

Repo: `/srv/claw` (git, `main`). Source of truth: `BRIEF.md` until B0, then `SPEC.md`.
Boards: `claw-explore` (scout → decide), then `claw-build`.

## Exploring: room to roam, with evidence

1. **Seeds are leads, not a whitelist.** At least 40% of the candidates you report must come from your own searching. Log the queries you ran in your scouting file.
2. **Go wide before you go deep.** Look at GitHub, product sites, docs, papers, Hacker News, Reddit, X and changelogs. Include at least one wildcard from an adjacent field that nobody asked about.
3. **No evidence, no entry.** Every candidate in `research/candidates/*.yaml` needs a source URL plus what you checked (see `swarm/templates/candidate.example.yaml`). If you can't verify something, mark it `unverified`. Never fill gaps from memory.
4. **Run it, don't just read it.** When a repo is cheap to try (clone, build, `--help`, a hello-world), try it and paste the output. For you, "it runs" beats "the README says".
5. **Disagree on purpose.** Your SOUL gives you a lens. Argue from it. Consensus is the judge's job, not yours.
6. **Stay blind until your card says otherwise.** Don't open `swarm/sealed/`. Don't read another agent's proposal before R1.
7. **Research cards finish themselves.** Commit on your branch, rebase on `main`, run `git -C /srv/claw merge --ff-only card/<key>`, then `kanban_complete` with a 5-line summary. The verifier checks your facts later.
8. **Stay in your box.** Scouts: ≤25 candidates and ≤2 pages of narrative per domain. Heartbeat (`kanban_heartbeat`) about every 10 minutes. When the timebox runs out, hand off what you have plus your open questions.

## Building: small, tested, reviewed

9. **One card, one branch.** The dispatcher gives you a worktree on `card/<key>`. Keep diffs small and don't edit files owned by another open card.
10. **Tests ship with the change.** Use `./tests/run.sh <area>`. Prototype and spike claims ship with a script that reproduces them.
11. **Done means evidence.** Call `kanban_request_review(summary=…, reviewer="verifier")` with what changed, the commands you ran, pasted output and open questions. Implementers never complete their own implementation cards.

## Always

12. **Blocked?** If the brief or spec is wrong, use `kanban_block(kind="needs_input")` with the exact problem and a proposed diff. If you're waiting on another card, use `kind="dependency"`.
13. **Stay in bounds.** Work only in `/srv/claw`, `/var/lib/claw` and `/tmp`. Never touch the Lima config, the Mac or other tenants. Record any new system package in `host/20-provision-host.sh`.
14. **No secrets in git.** Fixtures use obvious fakes like `sk-test-000`.
15. **Nothing real goes out.** No real emails, posts, sign-ups, purchases or paid API trials. Use sinks and mocks.
16. **Actions that kill the swarm need Tomas.** A claw-host reboot or gateway restart kills every worker. Leave verification steps in a comment, then block with `needs_input`.
17. **Say what's unknown.** Don't guess versions, flags, prices or behaviour. Check them, or mark them unknown.
18. **Write decisions down.** Put them in `docs/adr/NNN-title.md`: 5–15 lines covering context, decision and consequence.
