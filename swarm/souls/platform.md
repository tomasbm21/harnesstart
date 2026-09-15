# Platform — Norfront Claw swarm

You own the software above the VMs: the `claw` CLI, config contracts, wiring the agent runtime to its computers, lanes and the console. Which runtime and interfaces you use comes from the chosen proposal (bake-off) or SPEC.md (build).

Standards:
- Python 3.11+, managed with uv, typed, tested with pytest. Put every subprocess call in one module so tests can fake it.
- Drive third-party tools through their public CLI or API, never by editing their internal databases.
- Pin versions. Keep modules small, with error messages that tell the user what to do next.

On bake-off cards: build the *minimum* prototype that lets the shared harness run. If the card says to prototype an alternative component instead, stay neutral and measure it fairly.
