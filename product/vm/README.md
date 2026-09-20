# Norfront Claw — Linux-cloud VM computer (BRIEF R2)

Hardware isolation is a **VM boundary**, not a container. This tree is `product/vm/` only. It does not edit BRIEF, souls, sealed, `product/jev/`, or the claw CLI.

The claw CLI can call it later:

```python
from claw_vm import ClawVM, start, stop, exec_in, doctor, fetch, default_computer
```

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

State lives in `~/.local/share/norfront-claw/vm/` (override with `CLAW_VM_HOME`). Keys stay on the host; nothing from `claw.env` is copied into the guest.

Default guest: Alpine 3.21 cloud (NoCloud + SSH). Tiny smoke image: `--image cirros`.

## What is actually isolated

| Layer | This host (Cursor Linux cloud) | Host with working nested KVM |
| --- | --- | --- |
| Boundary | QEMU VM, guest kernel, virtio disk | Firecracker microVM on KVM |
| Hardware EPT/VMX for L2 | **No** | Yes |
| Container/LXC/gVisor | No | No |
| Host filesystem | Not mounted into the guest | Not mounted |
| Guest egress | QEMU user-net (slirp) + SSH hostfwd; `CLAW_VM_RESTRICT=1` blocks guest-initiated sockets | TAP to host; no NAT unless you add it |

`/dev/kvm` exists here and nested=Y, but `KVM_CREATE_VCPU` hits `kernel BUG at arch/x86/kvm/x86.c` (`alloc_loaded_vmcs`). Firecracker, QEMU `-accel kvm`, and libkrun all need that ioctl, so they cannot create a vCPU on this nested guest. **Do not pass `--probe-vcpu` unless you want to re-test; it can oops the host kernel.**

Preferred VMM is still Firecracker:

```bash
# on a machine where nested KVM vCPU works (Lima claw-host, bare metal):
CLAW_VM_PROBE_VCPU=1 ./product/vm/claw-vm doctor --probe-vcpu
./product/vm/claw-vm fetch --vmm firecracker
./product/vm/claw-vm start agent --vmm firecracker
```

On this cloud host the default is QEMU TCG so a guest actually boots. That is still a VM (separate kernel + disk), not a container.

Jailer is downloaded with Firecracker but not wired in v0.

## Layout

| Path | Role |
| --- | --- |
| `product/vm/claw-vm` | Entrypoint |
| `product/vm/claw_vm/` | Python API |
| `~/.local/share/norfront-claw/vm/assets/` | Firecracker binary, kernel, images, SSH key |
| `~/.local/share/norfront-claw/vm/instances/<name>/` | Persistent disk + serial log |

## Persistence

Each instance gets a qcow2 overlay (QEMU) or its own ext4 copy (Firecracker). `stop` kills the VMM and leaves the disk. `start` of the same name reuses it. `destroy` deletes it.

`fetch` for Alpine needs sudo once to bake SSH keys into the guest image (OpenSSH treats `!`/`*` shadow entries as locked accounts). After that, `./product/vm/claw-vm start agent` boots the overlay.

## Tests

```bash
python3 -m unittest discover -s product/vm/tests -v
CLAW_VM_LIVE=1 python3 -m unittest discover -s product/vm/tests -p 'test_live.py'
```
