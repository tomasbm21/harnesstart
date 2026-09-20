# Norfront Claw — Linux-cloud VM computer (BRIEF R2)

Hardware isolation is a **VM boundary**, not a container. This tree is `product/vm/` plus a thin `./product/claw doctor` hook. It does not edit BRIEF, souls, sealed, `product/jev/`, or `product/brains/`.

**QEMU is the default computer.** Firecracker, Celesto, E2B runtime, AgentENV, microsandbox, and libkrun are selectable backends. Live start is skipped when working KVM or Docker is missing. Nested `KVM_CREATE_VCPU` is never probed unless you pass `--probe-vcpu`.

```python
from claw_vm import ClawVM, start, stop, exec_in, doctor, fetch, default_computer
from claw_vm import list_backends, select, selected_id
```

## Select a computer

```bash
./product/vm/claw-vm list
./product/vm/claw-vm doctor
./product/vm/claw-vm select qemu          # default
./product/vm/claw-vm select firecracker
./product/vm/claw-vm select celesto       # or e2b | agentenv | microsandbox | libkrun
./product/vm/claw-vm selected
CLAW_VM_BACKEND=libkrun ./product/vm/claw-vm doctor
```

`CLAW_VM_BACKEND` env wins over the file written by `select`. `CLAW_VM_VMM=qemu|firecracker` is still accepted as an alias. Default remains **qemu**.

## Start one VM (Cursor Linux cloud)

From the harnesstart repo root:

```bash
./product/vm/claw-vm doctor
./product/vm/claw-vm fetch
./product/vm/claw-vm start agent
./product/vm/claw-vm exec agent -- uname -a
./product/vm/claw-vm isolation agent
./product/vm/claw-vm persist-check agent   # write a file, stop VMM, start, read it
./product/vm/claw-vm stop agent            # keeps the disk
```

Optional backends **do not live-start** on this nested host (`KVM_CREATE_VCPU` kernel-BUGs; Docker is missing):

```bash
./product/vm/claw-vm start agent --backend celesto      # exit 2 skipped-no-kvm
./product/vm/claw-vm start agent --backend e2b          # exit 2 skipped-no-kvm (also needs Docker)
./product/vm/claw-vm start agent --backend agentenv     # exit 2 skipped-no-kvm
./product/vm/claw-vm start agent --backend microsandbox # exit 2 skipped-no-kvm
./product/vm/claw-vm start agent --backend libkrun      # exit 2 skipped-no-kvm
```

State lives in `~/.local/share/norfront-claw/vm/` (override with `CLAW_VM_HOME`). Keys stay on the host; nothing from `claw.env` is copied into the guest. Hosted control planes (Celesto Cloud, E2B Cloud) are **not** used.

Default guest: Alpine 3.21 cloud (NoCloud + SSH). Tiny smoke image: `--image cirros`.

## What is actually isolated

| Layer | This host (Cursor Linux cloud) | Host with working nested KVM |
| --- | --- | --- |
| Default | QEMU VM, guest kernel, virtio disk | QEMU (KVM accel) or selected Firecracker/libkrun computer |
| Hardware EPT/VMX for L2 | **No** | Yes |
| Container/LXC/gVisor | No | No |
| Host filesystem | Not mounted into the guest | Not mounted |
| Guest egress | QEMU user-net (slirp) + SSH hostfwd; `CLAW_VM_RESTRICT=1` blocks guest-initiated sockets | TAP / backend-specific |

`/dev/kvm` exists here and nested=Y, but `KVM_CREATE_VCPU` hits `kernel BUG at arch/x86/kvm/x86.c` (`alloc_loaded_vmcs`). Firecracker, QEMU `-accel kvm`, Celesto-on-Linux, E2B Embed, AgentENV, microsandbox, and libkrun all need that ioctl. **Do not pass `--probe-vcpu` unless you want to re-test; it can oops the host kernel.**

On a machine where nested KVM vCPU works:

```bash
# still do not probe unless you mean to:
CLAW_VM_PROBE_VCPU=1 ./product/vm/claw-vm doctor --probe-vcpu
./product/vm/claw-vm select firecracker
./product/vm/claw-vm fetch --vmm firecracker
./product/vm/claw-vm start agent --backend firecracker
```

Jailer is downloaded with Firecracker but not wired in v0.

## Optional backends

| Id | Upstream | Isolation | Live start needs |
| --- | --- | --- | --- |
| `qemu` (default) | QEMU | VM (TCG or KVM) | `qemu-system-x86_64` (no Docker) |
| `firecracker` | [firecracker](https://github.com/firecracker-microvm/firecracker) | Firecracker microVM | working KVM vCPU |
| `celesto` | [CelestoAI/celesto](https://github.com/CelestoAI/celesto) | Firecracker on Linux | working KVM; never `provider=cloud` |
| `e2b` | [e2b-dev/runtime](https://github.com/e2b-dev/runtime) | Firecracker (Embed) | working KVM **and** Docker Compose; not E2B Cloud |
| `agentenv` | [kvcache-ai/AgentENV](https://github.com/kvcache-ai/AgentENV) | Firecracker, E2B-compatible API | working KVM; local API key file is never printed |
| `microsandbox` | [superradcompany/microsandbox](https://github.com/superradcompany/microsandbox) | libkrun microVM | working KVM |
| `libkrun` | [libkrun/libkrun](https://github.com/libkrun/libkrun) | libkrun VMM library | working KVM; no generic computer CLI |

## Layout

| Path | Role |
| --- | --- |
| `product/vm/claw-vm` | Entrypoint |
| `product/vm/claw_vm/` | Python API |
| `~/.local/share/norfront-claw/vm/selected` | Last `select` (env wins) |
| `~/.local/share/norfront-claw/vm/assets/` | Firecracker binary, kernel, images, SSH key |
| `~/.local/share/norfront-claw/vm/instances/<name>/` | Persistent disk + serial log |

## Persistence

Each qemu/firecracker instance gets a qcow2 overlay (QEMU) or its own ext4 copy (Firecracker). `stop` kills the VMM and leaves the disk. `start` of the same name reuses it. `destroy` deletes it.

`fetch` for Alpine needs sudo once to bake SSH keys into the guest image (OpenSSH treats `!`/`*` shadow entries as locked accounts). After that, `./product/vm/claw-vm start agent` boots the overlay.

## Tests

```bash
python3 -m unittest discover -s product/vm/tests -v
CLAW_VM_LIVE=1 python3 -m unittest discover -s product/vm/tests -p 'test_live.py'
```
