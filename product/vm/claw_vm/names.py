"""Backend ids. QEMU is the default computer; optionals are selected explicitly."""

from __future__ import annotations

DEFAULT_BACKEND = "qemu"

KNOWN_BACKENDS = (
    "qemu",
    "firecracker",
    "celesto",
    "e2b",
    "agentenv",
    "microsandbox",
    "libkrun",
)

# qemu + firecracker launch guests in this tree. The others are optional computers.
BUILTIN_VMMS = frozenset({"qemu", "firecracker"})

ALIASES = {
    "fc": "firecracker",
    "qemu-tcg": "qemu",
    "qemu-kvm": "qemu",
    "smolvm": "celesto",
    "celestoai": "celesto",
    "e2b-runtime": "e2b",
    "runtime": "e2b",
    "aenv": "agentenv",
    "agent-env": "agentenv",
    "msb": "microsandbox",
    "micro-sandbox": "microsandbox",
    "krun": "libkrun",
    "lib-krun": "libkrun",
}


class UnknownBackend(ValueError):
    """Not a wired computer backend."""


def canonical_backend(raw: str | None) -> str | None:
    """Return a known id, or None for empty/auto. Does not raise."""
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value or value == "auto":
        return None
    value = ALIASES.get(value, value)
    if value in KNOWN_BACKENDS:
        return value
    return None


def normalize_backend(raw: str) -> str:
    value = canonical_backend(raw)
    if value is None:
        raise UnknownBackend(
            f"unknown backend {raw!r}. Choose one of: {', '.join(KNOWN_BACKENDS)}"
        )
    return value
