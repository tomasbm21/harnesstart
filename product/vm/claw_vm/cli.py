"""CLI: doctor, list, select, start. Never prints secrets. Never --probe-vcpu by default."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .assets import fetch_assets
from .backends import StartSkipped
from .computer import default_computer
from .host import docker_present
from .instance import destroy, exec_in, persist_probe, start, status, stop
from .isolation import isolation_report
from .kvm import kvm_report
from .names import DEFAULT_BACKEND, KNOWN_BACKENDS, UnknownBackend
from .paths import vm_home
from .registry import (
    list_backends,
    resolve_backend,
    select,
    selected_id,
    selected_source,
)
from .secrets import assert_no_secrets, redact


def dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def doctor_payload(*, probe_vcpu: bool = False, backend: str | None = None) -> dict[str, object]:
    kvm = kvm_report(probe_vcpu=probe_vcpu)
    current, source = selected_source()
    if backend:
        current = resolve_backend(backend)
        source = "flag"
    computer = default_computer()
    if backend:
        from .backends import doctor_backend

        default = doctor_backend(current)
    else:
        default = computer.doctor()
    iso = default.get("isolation") if isinstance(default.get("isolation"), dict) else isolation_report(
        vmm=current,
        accel=default.get("accel") if isinstance(default, dict) else getattr(computer, "accel", None),
    )
    backends = list_backends()
    if backend:
        backends = [b for b in backends if b.get("name") == current]
    return {
        "product": "claw-vm",
        "version": __version__,
        "ok": True,
        "home": str(vm_home()),
        "kvm": kvm,
        "docker": docker_present(),
        "default": DEFAULT_BACKEND,
        "selected": current,
        "selected_source": source,
        "default_computer": default,
        "isolation": iso,
        "backends": backends,
        "hint": (
            "Select: ./product/vm/claw-vm select "
            "qemu|firecracker|celesto|e2b|agentenv|microsandbox|libkrun "
            "(or CLAW_VM_BACKEND=…). Default remains qemu. "
            "Live start skips without working KVM / Docker. Never --probe-vcpu on this host."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="claw-vm",
        description=(
            "Norfront Claw VM computer (BRIEF R2). QEMU is the default. "
            "Optional: Celesto, E2B runtime, AgentENV, microsandbox, libkrun."
        ),
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON on stdout")
    sub = parser.add_subparsers(dest="cmd")

    doc = sub.add_parser("doctor", help="KVM/Docker node, selected backend, isolation statement")
    doc.add_argument("--probe-vcpu", action="store_true", help="KVM_CREATE_VCPU (can oops nested hosts)")
    doc.add_argument("--backend", default=None, help="doctor one backend")
    doc.add_argument("--json", action="store_true")

    lst = sub.add_parser("list", help="List wired computers (qemu is default)")
    lst.add_argument("--json", action="store_true")

    sel = sub.add_parser("select", help="Persist the selected computer (CLAW_VM_BACKEND still wins)")
    sel.add_argument("backend", help=" | ".join(KNOWN_BACKENDS))
    sel.add_argument("--json", action="store_true")

    shown = sub.add_parser("selected", help="Show the selected computer and why")
    shown.add_argument("--json", action="store_true")

    fet = sub.add_parser("fetch", help="Download Firecracker and/or QEMU guest images (no Docker)")
    fet.add_argument("--image", default=None)
    fet.add_argument("--vmm", default=None, choices=["auto", "qemu", "firecracker", "all"])
    fet.add_argument("--json", action="store_true")

    st = sub.add_parser("start", help="Start one named VM (skips optional backends without KVM/Docker)")
    st.add_argument("name", nargs="?", default="agent")
    st.add_argument("--image", default=None, help="alpine | cirros | fc-ubuntu")
    st.add_argument("--vmm", default=None, help="auto | qemu | firecracker (aliases for --backend)")
    st.add_argument("--backend", default=None, help=" | ".join(KNOWN_BACKENDS))
    st.add_argument("--timeout", type=int, default=180)
    st.add_argument("--no-wait", action="store_true")
    st.add_argument("--json", action="store_true")

    ex = sub.add_parser("exec", help="Run a command in the guest via SSH")
    ex.add_argument("name")
    ex.add_argument("command", nargs=argparse.REMAINDER)
    ex.add_argument("--timeout", type=int, default=60)

    sub.add_parser("stop", help="Stop the VMM; keep the disk").add_argument("name", nargs="?", default="agent")
    sub.add_parser("destroy", help="Stop and delete the instance disk").add_argument(
        "name", nargs="?", default="agent"
    )

    stat = sub.add_parser("status", help="List instances or one instance")
    stat.add_argument("name", nargs="?")
    stat.add_argument("--json", action="store_true")

    iso = sub.add_parser("isolation", help="What this layer actually isolates")
    iso.add_argument("name", nargs="?")
    iso.add_argument("--backend", default=None)
    iso.add_argument("--json", action="store_true")

    pb = sub.add_parser("persist-check", help="Write a guest file, reboot VMM, read it back")
    pb.add_argument("name", nargs="?", default="agent")
    pb.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        _emit(__version__)
        return 0
    if not args.cmd:
        parser.print_help()
        return 2

    want_json = bool(getattr(args, "json", False))

    try:
        if args.cmd == "doctor":
            payload = doctor_payload(probe_vcpu=bool(args.probe_vcpu), backend=args.backend)
            _emit(dumps(payload) if want_json else _render_doctor(payload))
            return 0 if payload.get("ok") else 1
        if args.cmd == "list":
            current = selected_id()
            items = list_backends()
            if want_json:
                _emit(dumps({"product": "claw-vm", "default": DEFAULT_BACKEND, "selected": current, "backends": items}))
            else:
                lines = []
                for item in items:
                    star = "*" if item.get("selected") else " "
                    live = item.get("live_start")
                    present = "present" if item.get("present") else "not installed"
                    lines.append(
                        f"{star} {item['name']:13}  {present:16}  live={live}"
                    )
                _emit("\n".join(lines) + "\n")
            return 0
        if args.cmd == "select":
            resolved = select(args.backend)
            payload = {"ok": True, "selected": resolved, "source": "file", "default": DEFAULT_BACKEND}
            _emit(
                dumps(payload)
                if want_json
                else f"selected {resolved} (CLAW_VM_BACKEND env still wins; default remains qemu)\n"
            )
            return 0
        if args.cmd == "selected":
            backend_id, source = selected_source()
            payload = {"id": backend_id, "source": source, "default": DEFAULT_BACKEND}
            _emit(dumps(payload) if want_json else f"{backend_id}  source={source}  default={DEFAULT_BACKEND}\n")
            return 0
        if args.cmd == "fetch":
            payload = fetch_assets(image=args.image, vmm=args.vmm)
            _emit(dumps(payload) if want_json else _render_kv(payload))
            return 0
        if args.cmd == "start":
            vm = start(
                args.name,
                image=args.image,
                vmm=args.vmm,
                backend=args.backend,
                wait=not args.no_wait,
                timeout=args.timeout,
            )
            payload = {
                "name": vm.name,
                "vmm": vm.vmm,
                "accel": vm.accel,
                "ssh": f"{vm.ssh_user}@{vm.ssh_host}:{vm.ssh_port}",
                "disk": str(vm.disk),
                "r2_isolated": vm.r2_isolated,
                "isolation": vm.isolation(),
                "skipped": False,
            }
            _emit(dumps(payload) if want_json else _render_start(payload))
            return 0
        if args.cmd == "exec":
            command = args.command
            if command and command[0] == "--":
                command = command[1:]
            if not command:
                print("usage: claw-vm exec NAME -- cmd...", file=sys.stderr)
                return 2
            result = exec_in(args.name, command, timeout=args.timeout)
            sys.stdout.write(redact(result.stdout))
            sys.stderr.write(redact(result.stderr))
            return result.returncode
        if args.cmd == "stop":
            stop(args.name)
            _emit(f"stopped {args.name}")
            return 0
        if args.cmd == "destroy":
            destroy(args.name)
            _emit(f"destroyed {args.name}")
            return 0
        if args.cmd == "status":
            payload = status(args.name)
            _emit(dumps(payload))
            return 0
        if args.cmd == "isolation":
            if args.backend:
                bid = resolve_backend(args.backend)
                from .backends import doctor_backend

                payload = doctor_backend(bid)["isolation"]
            elif args.name:
                st = status(args.name)
                payload = st.get("isolation") if isinstance(st, dict) else isolation_report(vmm="qemu")
            else:
                computer = default_computer()
                payload = isolation_report(
                    vmm=computer.name,
                    accel=getattr(computer, "accel", None),
                )
            _emit(dumps(payload) if want_json else _render_iso(payload))  # type: ignore[arg-type]
            return 0
        if args.cmd == "persist-check":
            payload = persist_probe(args.name)
            _emit(dumps(payload) if want_json else dumps(payload))
            return 0 if payload.get("ok") else 1
    except StartSkipped as exc:
        payload = exc.payload()
        _emit(dumps(payload) if want_json else f"skipped {exc.backend}: {exc.reason}\n{exc.detail}\n")
        return 2
    except UnknownBackend as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError, RuntimeError, TimeoutError) as exc:
        print(redact(f"claw-vm: {exc}"), file=sys.stderr)
        return 1
    parser.print_help()
    return 2


def _emit(text: str) -> None:
    text = redact(text)
    assert_no_secrets(text)
    sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _render_doctor(payload: dict[str, object]) -> str:
    kvm = payload["kvm"]  # type: ignore[index]
    iso = payload["isolation"]  # type: ignore[index]
    docker = payload.get("docker")
    lines = [
        f"claw-vm {payload['version']}  home={payload['home']}",
        f"kvm: present={kvm['present']} openable={kvm['openable']} nested={kvm['nested']}",
        f"docker: {'present' if docker else 'missing'}",
        f"default computer: {payload.get('default')}",
        f"selected: {payload.get('selected')}  source={payload.get('selected_source')}",
        f"R2 VM boundary: {iso['r2_vm_boundary']}  hardware KVM: {iso['r2_hardware_kvm']}",
        iso["boundary"],  # type: ignore[index]
        "",
        "Backends:",
    ]
    for item in payload.get("backends") or []:
        if not isinstance(item, dict):
            continue
        star = "*" if item.get("selected") else " "
        present = "present" if item.get("present") else "not installed"
        lines.append(
            f" {star} {item.get('name'):13}  {present:16}  live={item.get('live_start')}"
        )
        if item.get("live_start") != "ready" and item.get("live_detail"):
            lines.append(f"     {item.get('live_detail')}")
    lines.extend(
        [
            "",
            "Start one VM (qemu default; optionals skip without KVM/Docker):",
            "  ./product/vm/claw-vm select qemu",
            "  ./product/vm/claw-vm fetch",
            "  ./product/vm/claw-vm start agent",
            "  ./product/vm/claw-vm exec agent -- uname -a",
            "",
            str(payload.get("hint") or ""),
        ]
    )
    return "\n".join(str(x) for x in lines)


def _render_kv(payload: dict[str, object]) -> str:
    lines = []
    for key, value in payload.items():
        if key == "firecracker" and isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"{k}: {v}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _render_start(payload: dict[str, object]) -> str:
    iso = payload["isolation"]  # type: ignore[index]
    return "\n".join(
        [
            f"started {payload['name']}  vmm={payload['vmm']} accel={payload['accel']}",
            f"ssh {payload['ssh']}",
            f"disk {payload['disk']}",
            f"R2 VM boundary={iso['r2_vm_boundary']} hardware_kvm={iso['r2_hardware_kvm']}",
            str(iso["boundary"]),
        ]
    )


def _render_iso(payload: dict[str, object]) -> str:
    lines = [
        str(payload.get("boundary")),
        f"R2 VM boundary: {payload.get('r2_vm_boundary')}  hardware KVM: {payload.get('r2_hardware_kvm')}",
        "Isolated:",
    ]
    for item in payload.get("isolated") or []:
        lines.append(f"  - {item}")
    lines.append("Not isolated:")
    for item in payload.get("not_isolated") or []:
        lines.append(f"  - {item}")
    return "\n".join(lines)
