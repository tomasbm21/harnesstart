#!/usr/bin/env python3
"""Mechanical checks on the candidate registry (research/candidates/*.yaml).

Catches the cheap lies before a human or agent reads anything:
  - repos that don't exist, last commit date, detected license vs declared license
  - product URLs that don't resolve
  - missing required fields, duplicate ids, too few self-found candidates (RULES 1)

It never decides fit or sets `status` — that's the verifier's judgment.

Usage:
  python3 swarm/tools/verify_candidates.py research/candidates/            # report only
  python3 swarm/tools/verify_candidates.py research/candidates/ --write    # also store auto_check on each entry
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

import yaml

REQUIRED = ("id", "name", "url", "kind", "domain", "evidence", "found_via")
GIT_HOSTS = ("github.com", "gitlab.com", "codeberg.org", "bitbucket.org", "sr.ht")
LICENSE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "LICENSE-APACHE", "LICENSE-MIT")
LICENSE_PATTERNS = [
    (r"Apache License", "Apache-2.0"),
    (r"MIT License|Permission is hereby granted, free of charge", "MIT"),
    (r"GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL"),
    (r"GNU LESSER GENERAL PUBLIC LICENSE", "LGPL"),
    (r"GNU GENERAL PUBLIC LICENSE", "GPL"),
    (r"Mozilla Public License", "MPL-2.0"),
    (r"BSD 3-Clause|Redistribution and use in source and binary forms", "BSD"),
    (r"Business Source License", "BUSL (source-available)"),
    (r"Elastic License", "Elastic (source-available)"),
    (r"Server Side Public License", "SSPL (source-available)"),
    (r"Fair Source|Functional Source License", "Fair/FSL (source-available)"),
]
ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


def run(cmd: list[str], cwd: str | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=timeout)


def git_repo_url(url: str) -> str | None:
    m = re.match(r"https?://(?:www\.)?([^/]+)/([^/\s]+)/([^/\s#?]+)", url or "")
    if not m or not any(m.group(1).endswith(h) for h in GIT_HOSTS):
        return None
    repo = m.group(3).removesuffix(".git")
    return f"https://{m.group(1)}/{m.group(2)}/{repo}"


def check_repo(url: str) -> dict:
    out: dict = {"exists": False}
    try:
        if run(["git", "ls-remote", "--heads", url], timeout=30).returncode != 0:
            return out
    except subprocess.TimeoutExpired:
        out["error"] = "ls-remote timeout"
        return out
    out["exists"] = True
    with tempfile.TemporaryDirectory() as tmp:
        try:
            clone = run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout", url, tmp], timeout=120)
        except subprocess.TimeoutExpired:
            out["error"] = "clone timeout"
            return out
        if clone.returncode != 0:
            out["error"] = (clone.stderr or "clone failed").strip()[:120]
            return out
        out["last_commit"] = run(["git", "log", "-1", "--format=%cs"], cwd=tmp).stdout.strip() or "unknown"
        out["license_detected"] = "none found"
        for name in LICENSE_FILES:
            text = run(["git", "show", f"HEAD:{name}"], cwd=tmp, timeout=60)
            if text.returncode == 0:
                out["license_detected"] = next(
                    (spdx for pat, spdx in LICENSE_PATTERNS if re.search(pat, text.stdout[:4000], re.I)),
                    f"unrecognised ({name})",
                )
                break
    return out


def check_url(url: str) -> dict:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "claw-verifier/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"reachable": True, "http_status": r.status}
    except urllib.error.HTTPError as e:
        return {"reachable": e.code < 500 and e.code not in (404, 410), "http_status": e.code}
    except Exception as e:  # noqa: BLE001 — report any network failure as unreachable
        return {"reachable": False, "error": type(e).__name__}


def months_since(date_str: str) -> float | None:
    try:
        d = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    return (dt.date.today() - d).days / 30.4


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="YAML files or directories of them")
    ap.add_argument("--write", action="store_true", help="store auto_check results back into the YAML files")
    ap.add_argument("--no-network", action="store_true", help="only check fields, ids and seed ratio")
    args = ap.parse_args()

    files: list[pathlib.Path] = []
    for p in map(pathlib.Path, args.paths):
        files += sorted(p.glob("*.y*ml")) if p.is_dir() else [p]
    if not files:
        print("no YAML files found", file=sys.stderr)
        return 1

    seen: dict[str, str] = {}
    problems = 0
    rows = []
    today = dt.date.today().isoformat()
    for f in files:
        entries = yaml.safe_load(f.read_text()) or []
        if not isinstance(entries, list):
            print(f"✗ {f}: expected a list of entries", file=sys.stderr)
            problems += 1
            continue
        seeds = sum(1 for e in entries if str(e.get("found_via", "")).strip() == "seed")
        if entries and (len(entries) - seeds) / len(entries) < 0.4:
            print(f"! {f.name}: only {len(entries) - seeds}/{len(entries)} entries self-found (RULES 1 wants ≥40%)")
            problems += 1
        for e in entries:
            eid = str(e.get("id", "?"))
            flags = [f"missing:{k}" for k in REQUIRED if not e.get(k)]
            if eid in seen:
                flags.append(f"duplicate id (also in {seen[eid]})")
            seen[eid] = f.name
            check: dict = {}
            if not args.no_network and e.get("url"):
                repo = git_repo_url(e["url"])
                check = check_repo(repo) if repo else check_url(e["url"])
                if repo and not check.get("exists"):
                    flags.append("REPO NOT FOUND")
                if not repo and not check.get("reachable"):
                    flags.append("URL UNREACHABLE")
                declared = str(e.get("license", "")).lower()
                detected = str(check.get("license_detected", ""))
                family = re.split(r"[-\s(]", detected, maxsplit=1)[0].lower()
                if detected == "none found":
                    flags.append("no LICENSE file found")
                elif detected and not detected.startswith("unrecognised") and declared not in ("", "unknown", "n/a") \
                        and family not in declared:
                    flags.append(f"license mismatch (declared {e.get('license')}, found {detected})")
                age = months_since(check.get("last_commit", ""))
                if age is not None and age > 6:
                    flags.append(f"stale ({age:.0f} months since last commit)")
                check["checked_at"] = today
                if args.write:
                    e["auto_check"] = check
                    if check.get("last_commit") and str(e.get("last_activity", "unknown")) == "unknown":
                        e["last_activity"] = check["last_commit"]
            problems += bool(flags)
            rows.append((eid, e.get("url", ""), check, flags))
        if args.write:
            f.write_text(yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=120))

    print("| id | exists/reachable | last commit | license found | flags |")
    print("|---|---|---|---|---|")
    for eid, url, c, flags in rows:
        ok = c.get("exists", c.get("reachable", "—"))
        print(f"| {eid} | {ok} | {c.get('last_commit', '—')} | {c.get('license_detected', '—')} | {'; '.join(flags) or '—'} |")
    print(f"\n{len(rows)} entries, {problems} with problems.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
