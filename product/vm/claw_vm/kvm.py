"""KVM node and vCPU probe.

Opening /dev/kvm is safe. KVM_CREATE_VCPU on this Cursor Linux cloud nested
guest hits `kernel BUG at arch/x86/kvm/x86.c` in alloc_loaded_vmcs. Do not
probe vCPU creation unless the caller asks (CLAW_VM_PROBE_VCPU=1 / --probe-vcpu).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import priv
from .paths import vm_home

KVM_PATH = Path("/dev/kvm")

_PROBE = r"""
import fcntl, os, sys
KVM_GET_API_VERSION = 0xAE00
KVM_CREATE_VM = 0xAE01
KVM_CREATE_VCPU = 0xAE41
fd = os.open("/dev/kvm", os.O_RDWR)
print("api", fcntl.ioctl(fd, KVM_GET_API_VERSION), flush=True)
vm = fcntl.ioctl(fd, KVM_CREATE_VM, 0)
print("vm", vm, flush=True)
vcpu = fcntl.ioctl(vm, KVM_CREATE_VCPU, 0)
print("vcpu", vcpu, flush=True)
"""


def kvm_present() -> bool:
    return KVM_PATH.exists()


def kvm_openable() -> bool:
    try:
        fd = os.open(KVM_PATH, os.O_RDWR)
        os.close(fd)
        return True
    except OSError:
        return False


def ensure_kvm_acl() -> bool:
    if kvm_openable():
        return True
    if not kvm_present() or not priv.can_sudo() or not priv.have("setfacl"):
        return kvm_openable()
    priv.run(
        ["setfacl", "-m", f"u:{priv.username()}:rw", str(KVM_PATH)],
        privileged=True,
        check=False,
    )
    return kvm_openable()


def probe_cache_path() -> Path:
    return vm_home() / "kvm-vcpu-probe.json"


def read_probe_cache() -> dict[str, object] | None:
    path = probe_cache_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def write_probe_cache(payload: dict[str, object]) -> None:
    path = probe_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def probe_kvm_vcpu(*, force: bool = False, timeout: float = 4.0) -> dict[str, object]:
    """Run CREATE_VCPU in a subprocess. Can oops a nested host kernel."""
    cached = read_probe_cache()
    if cached and not force:
        return {**cached, "cached": True}

    if not kvm_present():
        result = {
            "ok": False,
            "error": "/dev/kvm missing",
            "probed_at": time.time(),
        }
        write_probe_cache(result)
        return result

    ensure_kvm_acl()
    argv = [sys.executable, "-c", _PROBE]
    if not kvm_openable() and priv.can_sudo():
        argv = ["sudo", "-n", *argv]

    try:
        proc = subprocess.run(
            argv,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        result = {
            "ok": False,
            "error": f"CREATE_VCPU timed out: {exc}",
            "probed_at": time.time(),
        }
        write_probe_cache(result)
        return result

    ok = proc.returncode == 0 and "vcpu" in (proc.stdout or "")
    result = {
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-500:],
        "stderr": (proc.stderr or "")[-500:],
        "error": None if ok else "KVM_CREATE_VCPU failed (nested VMX often kernel-BUGs here)",
        "probed_at": time.time(),
    }
    write_probe_cache(result)
    return result


def kvm_report(*, probe_vcpu: bool = False) -> dict[str, object]:
    present = kvm_present()
    opened = ensure_kvm_acl() if present else False
    nested = None
    nested_path = Path("/sys/module/kvm_intel/parameters/nested")
    if nested_path.is_file():
        nested = nested_path.read_text().strip()
    cached = read_probe_cache()
    vcpu: dict[str, object]
    if probe_vcpu or os.environ.get("CLAW_VM_PROBE_VCPU") == "1":
        vcpu = probe_kvm_vcpu(force=probe_vcpu)
    elif cached:
        vcpu = {**cached, "cached": True}
    else:
        vcpu = {
            "ok": None,
            "skipped": True,
            "error": (
                "Not probed. On this Cursor nested KVM host, KVM_CREATE_VCPU has "
                "hit kernel BUG alloc_loaded_vmcs. Pass --probe-vcpu only if you "
                "want to re-test (it can oops the host kernel)."
            ),
        }
    return {
        "path": str(KVM_PATH),
        "present": present,
        "openable": opened,
        "nested": nested,
        "vcpu": vcpu,
        "sudo": priv.can_sudo(),
        "virt": _detect_virt(),
    }


def _detect_virt() -> str | None:
    for cmd in (["systemd-detect-virt"], ["virt-what"]):
        if not priv.have(cmd[0]):
            continue
        try:
            proc = subprocess.run(
                cmd, check=False, text=True, capture_output=True, timeout=3
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = (proc.stdout or "").strip()
        if out:
            return out.splitlines()[0]
    return None


def vcpu_known_good() -> bool:
    cached = read_probe_cache()
    return bool(cached and cached.get("ok") is True)
