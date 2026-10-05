"""Interactive console for the launch window.

The launch window (Launch Claw.bat / start.exe / ./launch) used to sit idle
after boot: it started the Vite server and then only waited on that child
process, so anything you typed into it went nowhere. This module turns that
window into a real prompt. Type a task and the crew runs it; a few built-in
words drive the usual claw subcommands.

Nothing here prints secret values. Dispatch goes through the claw CLI, which
already redacts.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, TextIO

BANNER = (
    "\n"
    "Norfront Claw is running. This window now takes typing.\n"
    "\n"
    "  Type a task and press Enter — the crew picks it up.\n"
    "  help                    this list\n"
    "  status | doctor         what is running / readiness\n"
    "  crew <task>             run the coding crew on a task\n"
    "  run <task>              one Prime Agent turn (needs DEEPSEEK_API_KEY)\n"
    "  ui                      reopen the console in your browser\n"
    "  clear                   clear this window\n"
    "  quit  (or Ctrl+C)       stop the console\n"
)

HELP = (
    "  <task>                  shorthand for: crew <task>\n"
    "  crew <task>             coding crew: orchestrator, writer, reviewer, ui\n"
    "  run <task>              one Prime Agent turn (needs DEEPSEEK_API_KEY)\n"
    "  observe <url>           look at a page (no key needed)\n"
    "  guards [text]           local R6 + Jev guard checks\n"
    "  choose <url> <goal>     Jev choose (needs TYPESAFE_API_KEY)\n"
    "  browse <url> <goal>     Jev run (needs TYPESAFE_API_KEY)\n"
    "  status                  brain, computer, browser, workspace\n"
    "  doctor                  full readiness report\n"
    "  agents                  list Prime Agent sessions\n"
    "  policy                  Jev policy booleans\n"
    "  test                    run the offline unit tests\n"
    "  ui                      reopen the console in your browser\n"
    "  clear                   clear this window\n"
    "  quit | exit | q          stop the console\n"
)

# Built-in words that map straight onto a claw subcommand.
_SUBCOMMANDS = {
    "status",
    "doctor",
    "agents",
    "policy",
    "test",
    "observe",
    "guards",
    "choose",
    "browse",
    "install",
    "stop",
}


def _default_run_command() -> Callable[[list[str]], int]:
    """Dispatch to the claw CLI without ever prompting for keys."""

    def run(argv: list[str]) -> int:
        from .cli import main as cli_main

        try:
            code = cli_main(["--no-prompt", *argv])
        except SystemExit as exc:  # --version and friends raise SystemExit
            code = exc.code
        except Exception as exc:  # never let one bad command kill the prompt
            print(f"claw: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        if code is None:
            return 0
        return int(code)

    return run


def _default_reopen():
    from .boot import open_browser

    def reopen() -> None:
        open_browser()

    return reopen


def _write(out: TextIO, line: str = "") -> None:
    out.write(line + "\n")
    out.flush()


def run_repl(
    root: Path,
    *,
    stop: Callable[[], None] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    run_command: Callable[[list[str]], int] | None = None,
    reopen: Callable[[], None] | None = None,
) -> int:
    """Read tasks from the launch window until quit/EOF. Returns an exit code.

    `stop` is called once on the way out so the console process can shut down.
    The stdin/stdout/run_command/reopen seams exist so this is testable without
    a terminal or a live vendor.
    """
    inp = stdin if stdin is not None else sys.stdin
    out = stdout if stdout is not None else sys.stdout
    run = run_command if run_command is not None else _default_run_command()
    open_console = reopen if reopen is not None else _default_reopen()

    _write(out, BANNER)

    def quit_now() -> int:
        _write(out, "\nStopping Norfront Claw. Close this window if it stays open.")
        if stop is not None:
            try:
                stop()
            except Exception:
                pass
        return 0

    while True:
        try:
            out.write("claw> ")
            out.flush()
            line = inp.readline()
        except KeyboardInterrupt:
            return quit_now()
        except EOFError:
            return quit_now()
        if line == "":  # EOF: piped input ran out, or Ctrl+Z then Enter
            return quit_now()
        text = line.strip()
        if not text:
            continue
        lowered = text.lower()

        if lowered in {"quit", "exit", "q"}:
            return quit_now()
        if lowered in {"help", "?", "h"}:
            _write(out, HELP.rstrip("\n"))
            continue
        if lowered in {"clear", "cls"}:
            out.write("\x1b[2J\x1b[H")
            out.flush()
            continue
        if lowered in {"ui", "open", "console"}:
            try:
                open_console()
                _write(out, "Opened the console.")
            except Exception as exc:
                _write(out, f"Could not open the console ({type(exc).__name__}).")
            continue

        words = text.split()
        head = words[0].lower()

        if head in _SUBCOMMANDS:
            argv = words
        elif head == "crew":
            if len(words) == 1:
                _write(out, "Give the crew a task: crew <task>")
                continue
            argv = words
        elif head == "run":
            if len(words) == 1:
                _write(out, "Give it a prompt: run <task>")
                continue
            argv = words
        else:
            # Bare text is a task for the crew, mirroring the console task box.
            argv = ["crew", text]

        _write(out)
        code = run(argv)
        if code:
            _write(out, f"(exit {code})")

    return 0  # unreachable; kept for readers
