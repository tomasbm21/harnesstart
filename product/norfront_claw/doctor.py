"""Linux-cloud readiness. Observe/guards checks never require TypeSafe.

R2: if product/vm/claw-vm exists, doctor shells out to `./product/vm/claw-vm doctor`.
Never pass --probe-vcpu (nested KVM_CREATE_VCPU kernel-BUGs on this host).
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .brain import PrimeBrain
from .browser import load_browser_adapter
from .computer import HostComputer
from .config import Config, presence_label
from .guards import check_text
from .paths import product_dir

STUBBED = (
    "r2-hardware-kvm",
    "prime-bash-permission-extension",
    "hermes-kanban",
    "desktop-watch-takeover",
)


@dataclass
class Check:
    id: str
    ok: bool
    detail: str
    warning: bool = False


def claw_vm_bin(root: Path) -> Path | None:
    path = product_dir(root) / "vm" / "claw-vm"
    if path.is_file():
        return path
    return None


def claw_vm_doctor_argv(root: Path) -> list[str] | None:
    """How to run the VM check. Windows has no bash, so use this Python."""
    binary = claw_vm_bin(root)
    if binary is None:
        return None
    if sys.platform == "win32":
        return [sys.executable, "-m", "claw_vm", "doctor", "--json"]
    return [str(binary), "doctor", "--json"]


def claw_vm_doctor_env(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    if sys.platform == "win32":
        vm_dir = str(product_dir(root) / "vm")
        prefix = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = vm_dir + (os.pathsep + prefix if prefix else "")
    return env


def run_claw_vm_doctor(root: Path) -> dict | None:
    """Thin hook: call product/vm/claw-vm doctor --json. Never --probe-vcpu."""
    argv = claw_vm_doctor_argv(root)
    if argv is None:
        return None
    if any(part == "--probe-vcpu" for part in argv):
        raise RuntimeError("refusing to pass --probe-vcpu to claw-vm")
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(root),
            env=claw_vm_doctor_env(root),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": type(exc).__name__, "present": True}
    if proc.returncode != 0:
        return {
            "ok": False,
            "present": True,
            "error": f"claw-vm doctor exit {proc.returncode}",
            "stderr": (proc.stderr or "").strip()[:400],
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "present": True, "error": "claw-vm doctor produced non-JSON"}
    if not isinstance(payload, dict):
        return {"ok": False, "present": True, "error": "claw-vm doctor JSON was not an object"}
    payload["ok"] = True
    payload["present"] = True
    return payload


@dataclass
class Check:
    id: str
    ok: bool
    detail: str
    warning: bool = False


def chrome_search_paths() -> list[str]:
    """Chrome stays installed on the machine. Look in the usual places."""
    home = Path.home()
    paths = [
        os.environ.get("CHROME_BIN") or "",
        os.environ.get("CLAW_CHROME") or "",
        "/opt/google/chrome/chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        str(home / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
    ]
    for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(key)
        if base:
            paths.append(str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    return paths


def _chrome_bin() -> str | None:
    for candidate in chrome_search_paths():
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")


def collect(cfg: Config, vm: dict | None = None) -> list[Check]:
    checks: list[Check] = []
    system = platform.system()
    # Linux cloud and the portable Windows package are both hosts.
    checks.append(
        Check(
            "linux",
            system in {"Linux", "Windows"},
            f"{system} {platform.release()} {platform.machine()}",
        )
    )
    py = sys.version_info
    checks.append(
        Check(
            "python",
            py >= (3, 11),
            f"Python {py.major}.{py.minor}.{py.micro}",
        )
    )
    computer = HostComputer()
    kvm = computer.kvm_present()
    if vm is None:
        vm = run_claw_vm_doctor(cfg.repo_root)
    if vm and vm.get("ok"):
        kvm_info = vm.get("kvm") if isinstance(vm.get("kvm"), dict) else {}
        default = vm.get("default_computer") if isinstance(vm.get("default_computer"), dict) else {}
        iso = vm.get("isolation") if isinstance(vm.get("isolation"), dict) else {}
        kvm_detail = (
            f"/dev/kvm present={kvm_info.get('present', kvm)} "
            f"openable={kvm_info.get('openable')} nested={kvm_info.get('nested')} "
            f"(claw-vm; never --probe-vcpu on this host)"
        )
        selected = vm.get("selected") or default.get("name") or iso.get("vmm") or "present"
        n_backends = len(vm.get("backends") or []) if isinstance(vm.get("backends"), list) else 0
        r2_detail = (
            f"claw-vm selected={selected} "
            f"source={vm.get('selected_source') or 'default'} "
            f"backends={n_backends} "
            f"accel={default.get('accel') or iso.get('accel')} "
            f"r2_vm_boundary={iso.get('r2_vm_boundary')} "
            f"r2_hardware_kvm={iso.get('r2_hardware_kvm')}"
        )
        r2_warning = not bool(iso.get("r2_hardware_kvm"))
    elif vm and vm.get("present"):
        kvm_detail = f"/dev/kvm present={kvm}; claw-vm doctor failed: {vm.get('error')}"
        r2_detail = f"product/vm/claw-vm present but doctor failed: {vm.get('error')}"
        r2_warning = True
    else:
        kvm_detail = (
            "/dev/kvm present (product/vm/claw-vm not on this checkout)"
            if kvm
            else "/dev/kvm missing (product/vm/claw-vm not on this checkout)"
        )
        r2_detail = "product/vm/claw-vm not present"
        r2_warning = True
    checks.append(Check("kvm", True, kvm_detail, warning=not kvm))
    checks.append(Check("r2-vm", True, r2_detail, warning=r2_warning))
    brain = PrimeBrain(cfg)
    version = brain.version()
    checks.append(
        Check(
            "prime-agent",
            version is not None,
            version or "not on PATH — run ./product/claw install",
            warning=version is None,
        )
    )
    checks.append(
        Check(
            "deepseek",
            True,
            f"{presence_label(cfg.deepseek_key)} (needed for claw run, not for observe/guards)",
            warning=not cfg.deepseek_key,
        )
    )
    checks.append(
        Check(
            "typesafe",
            True,
            f"{presence_label(cfg.typesafe_key)} (live Jev policy only; observe/guards do not need it)",
            warning=False,
        )
    )
    adapter = load_browser_adapter(cfg)
    info = adapter.doctor()
    present = bool(info.get("present", adapter.name != "missing-jev"))
    checks.append(
        Check(
            "jev-adapter",
            True,
            f"{adapter.name}; present={present}; observe/guards typesafe=no",
            warning=not present,
        )
    )
    chrome = _chrome_bin()
    checks.append(
        Check(
            "chrome",
            True,
            chrome or "not found (Jev observe needs Chrome/CDP via product/jev)",
            warning=chrome is None,
        )
    )
    display = cfg.display or os.environ.get("DISPLAY") or ""
    checks.append(
        Check(
            "display",
            True,
            display or "DISPLAY unset (set BU_CDP_URL for a headless CDP browser)",
            warning=not display and not cfg.cdp_url,
        )
    )
    local = check_text("summarize this repo", allow_irreversible=False)
    checks.append(
        Check("r6-local-guards", local.allowed, local.reason),
    )
    workspace = cfg.workspace
    checks.append(
        Check(
            "workspace",
            True,
            f"{workspace} (Prime cwd; not the harness git tree)",
        )
    )
    try:
        adapter.close()
    except Exception:
        pass
    return checks


def report(cfg: Config) -> dict:
    vm = run_claw_vm_doctor(cfg.repo_root)
    checks = collect(cfg, vm=vm)
    hard_fail = [c for c in checks if not c.ok and not c.warning]
    ready = all(c.ok for c in checks if c.id in {"linux", "python"})
    adapter = load_browser_adapter(cfg)
    iso = vm.get("isolation") if isinstance(vm, dict) and isinstance(vm.get("isolation"), dict) else {}
    default = (
        vm.get("default_computer") if isinstance(vm, dict) and isinstance(vm.get("default_computer"), dict) else {}
    )
    r2_isolated = bool(iso.get("r2_vm_boundary") or default.get("r2_isolated"))
    stubbed = [
        "prime-bash-permission-extension",
        "hermes-kanban",
        "desktop-watch-takeover",
    ]
    if adapter.name == "missing-jev":
        stubbed.insert(0, "jev-adapter")
    if not (isinstance(vm, dict) and vm.get("ok")):
        stubbed.insert(0, "r2-vm-computer")
    elif not iso.get("r2_hardware_kvm"):
        stubbed.insert(0, "r2-hardware-kvm")
    payload = {
        "ok": ready and not hard_fail,
        "ready": ready,
        "host": "linux" if platform.system() == "Linux" else platform.system().lower(),
        "provider": cfg.provider,
        "model": cfg.model,
        "workspace": str(cfg.workspace),
        "browser_profile": str(cfg.browser_profile),
        "adapter": adapter.name,
        "r2_isolated": r2_isolated,
        "vm": _public_vm(vm),
        "checks": [asdict(c) for c in checks],
        "stubbed": stubbed,
        "env_files": [str(p) for p in cfg.env_files],
        "keys": {
            "DEEPSEEK_API_KEY": presence_label(cfg.deepseek_key),
            "TYPESAFE_API_KEY": presence_label(cfg.typesafe_key),
            "TEXT_MODEL_API_KEY": presence_label(cfg.text_model_key),
            "WEB_API_KEY": presence_label(cfg.web_api_key),
            "GH_TOKEN": presence_label(cfg.gh_token),
        },
    }
    try:
        adapter.close()
    except Exception:
        pass
    return payload


def render_text(payload: dict) -> str:
    vm = payload.get("vm") if isinstance(payload.get("vm"), dict) else {}
    computer_name = vm.get("computer") or "host process"
    lines = [
        f"Norfront Claw Linux  {'READY' if payload.get('ok') else 'NOT READY'}",
        f"  brain     Prime Agent ({payload.get('provider')}/{payload.get('model')})",
        f"  computer  {computer_name} — R2 isolated={payload.get('r2_isolated')}",
        f"  browser   {payload.get('adapter')} (Jev hook)",
        "",
    ]
    for check in payload.get("checks", []):
        mark = "✓" if check["ok"] and not check.get("warning") else ("!" if check.get("warning") else "✗")
        lines.append(f"  {mark} {check['id']}: {check['detail']}")
    lines.append("")
    lines.append("  keys (values never printed):")
    for name, state in payload.get("keys", {}).items():
        lines.append(f"    {name}: {state}")
    lines.append("")
    lines.append("  still stubbed: " + ", ".join(payload.get("stubbed", [])))
    return "\n".join(lines) + "\n"


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _public_vm(vm: dict | None) -> dict:
    if not vm:
        return {"present": False}
    iso = vm.get("isolation") if isinstance(vm.get("isolation"), dict) else {}
    default = vm.get("default_computer") if isinstance(vm.get("default_computer"), dict) else {}
    backends = vm.get("backends") if isinstance(vm.get("backends"), list) else []
    selected = vm.get("selected") or default.get("name") or iso.get("vmm")
    return {
        "present": bool(vm.get("present")),
        "ok": bool(vm.get("ok")),
        "computer": selected,
        "selected": selected,
        "selected_source": vm.get("selected_source"),
        "accel": default.get("accel") or iso.get("accel"),
        "r2_vm_boundary": iso.get("r2_vm_boundary"),
        "r2_hardware_kvm": iso.get("r2_hardware_kvm"),
        "home": vm.get("home"),
        "error": vm.get("error"),
        "backends": [
            {
                "id": item.get("name"),
                "live_start": item.get("live_start"),
                "present": item.get("present"),
                "selected": item.get("selected"),
            }
            for item in backends
            if isinstance(item, dict)
        ],
    }
