"""CLI: doctor, fetch, start, exec, stop, isolation. Never prints secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .assets import fetch_assets
from .computer import default_computer
from .instance import destroy, exec_in, persist_probe, start, status, stop
from .isolation import isolation_report
from .kvm import kvm_report
from .paths import vm_home


def dumps(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def doctor_payload(*, probe_vcpu: bool = False) -> dict[str, object]:
    kvm = kvm_report(probe_vcpu=probe_vcpu)
    computer = default_computer()
    iso = isolation_report(
        vmm="firecracker" if computer.name == "firecracker" else "qemu",
        accel=getattr(computer, "accel", "tcg"),
    )
    return {
        "product": "claw-vm",
        "version": __version__,
        "home": str(vm_home()),
        "kvm": kvm,
        "default_computer": computer.doctor(),
        "isolation": iso,
        "hint": (
            "Start one VM: ./product/vm/claw-vm fetch && ./product/vm/claw-vm start agent"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="claw-vm",
        description="Norfront Claw VM computer (BRIEF R2). Firecracker/KVM preferred; QEMU fallback.",
    )
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON on stdout")
    sub = parser.add_subparsers(dest="cmd")

    doc = sub.add_parser("doctor", help="KVM node, default VMM, isolation statement")
    doc.add_argument("--probe-vcpu", action="store_true", help="KVM_CREATE_VCPU (can oops nested hosts)")
    doc.add_argument("--json", action="store_true")

    fet = sub.add_parser("fetch", help="Download Firecracker and/or QEMU guest images (no Docker)")
    fet.add_argument("--image", default=None)
    fet.add_argument("--vmm", default=None, choices=["auto", "qemu", "firecracker", "all"])
    fet.add_argument("--json", action="store_true")

    st = sub.add_parser("start", help="Start one named VM (persistent disk)")
    st.add_argument("name", nargs="?", default="agent")
    st.add_argument("--image", default=None, help="alpine | cirros | fc-ubuntu")
    st.add_argument("--vmm", default=None, help="auto | qemu | firecracker")
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
    iso.add_argument("--json", action="store_true")

    pb = sub.add_parser("persist-check", help="Write a guest file, reboot VMM, read it back")
    pb.add_argument("name", nargs="?", default="agent")
    pb.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)
    if args.version or args.cmd == "version":
        print(__version__)
        return 0
    if not args.cmd:
        parser.print_help()
        return 2

    want_json = bool(getattr(args, "json", False))

    try:
        if args.cmd == "doctor":
            payload = doctor_payload(probe_vcpu=bool(args.probe_vcpu))
            print(dumps(payload) if want_json else _render_doctor(payload))
            return 0
        if args.cmd == "fetch":
            payload = fetch_assets(image=args.image, vmm=args.vmm)
            print(dumps(payload) if want_json else _render_kv(payload))
            return 0
        if args.cmd == "start":
            vm = start(
                args.name,
                image=args.image,
                vmm=args.vmm,
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
            }
            print(dumps(payload) if want_json else _render_start(payload))
            return 0
        if args.cmd == "exec":
            command = args.command
            if command and command[0] == "--":
                command = command[1:]
            if not command:
                print("usage: claw-vm exec NAME -- cmd...", file=sys.stderr)
                return 2
            result = exec_in(args.name, command, timeout=args.timeout)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode
        if args.cmd == "stop":
            stop(args.name)
            print(f"stopped {args.name}")
            return 0
        if args.cmd == "destroy":
            destroy(args.name)
            print(f"destroyed {args.name}")
            return 0
        if args.cmd == "status":
            payload = status(args.name)
            print(dumps(payload) if want_json else dumps(payload))
            return 0
        if args.cmd == "isolation":
            if args.name:
                st = status(args.name)
                payload = st.get("isolation") if isinstance(st, dict) else isolation_report(vmm="qemu")
            else:
                computer = default_computer()
                payload = isolation_report(
                    vmm="firecracker" if computer.name == "firecracker" else "qemu",
                    accel=getattr(computer, "accel", "tcg"),
                )
            print(dumps(payload) if want_json else _render_iso(payload))  # type: ignore[arg-type]
            return 0
        if args.cmd == "persist-check":
            payload = persist_probe(args.name)
            print(dumps(payload) if want_json else dumps(payload))
            return 0 if payload.get("ok") else 1
    except (FileNotFoundError, ValueError, RuntimeError, TimeoutError) as exc:
        print(f"claw-vm: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


def _render_doctor(payload: dict[str, object]) -> str:
    kvm = payload["kvm"]  # type: ignore[index]
    iso = payload["isolation"]  # type: ignore[index]
    lines = [
        f"claw-vm {payload['version']}  home={payload['home']}",
        f"kvm: present={kvm['present']} openable={kvm['openable']} nested={kvm['nested']}",
        f"default computer: {payload['default_computer']['name']}",  # type: ignore[index]
        f"R2 VM boundary: {iso['r2_vm_boundary']}  hardware KVM: {iso['r2_hardware_kvm']}",
        iso["boundary"],  # type: ignore[index]
        "",
        "Start one VM:",
        "  ./product/vm/claw-vm fetch",
        "  ./product/vm/claw-vm start agent",
        "  ./product/vm/claw-vm exec agent -- uname -a",
    ]
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
