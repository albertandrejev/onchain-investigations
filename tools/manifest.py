"""Integrity manifest for the raw-data cache.

Each case runs offline from its own ``cases/NN-slug/data/cache``. The manifest
pins that cache: a reader can confirm that the JSON files the checks read are
byte-for-byte the ones that were fetched, and ``verify.py`` refuses to run
against a cache that has been edited after the manifest was written.

    python -m tools.manifest write    cases/03-chainflip-tron-duplicate-payouts/data/cache
    python -m tools.manifest verify   cases/03-chainflip-tron-duplicate-payouts/data/cache   # exit 1 on mismatch
    python -m tools.manifest snapshot cases/03-chainflip-tron-duplicate-payouts/data/cache   # newest fetched_at

Without a path the commands use ``$CIP_CACHE``.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from .net import CACHE

MANIFEST = "MANIFEST.sha256"


def _files(cache: Path):
    return sorted(p for p in cache.rglob("*.json") if p.name != MANIFEST)


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(cache: Path = CACHE) -> Path:
    lines = [f"{_digest(p)}  {p.relative_to(cache).as_posix()}" for p in _files(cache)]
    out = cache / MANIFEST
    out.write_text("\n".join(lines) + "\n")
    return out


def verify(cache: Path = CACHE) -> list[str]:
    """Return a list of problems (empty = cache matches the manifest)."""
    m = cache / MANIFEST
    if not m.exists():
        return [f"no {MANIFEST} in {cache}"]
    expected = {}
    for line in m.read_text().splitlines():
        if line.strip():
            digest, rel = line.split("  ", 1)
            expected[rel] = digest
    actual = {p.relative_to(cache).as_posix(): _digest(p) for p in _files(cache)}
    problems = []
    for rel in sorted(set(expected) | set(actual)):
        if rel not in actual:
            problems.append(f"missing: {rel}")
        elif rel not in expected:
            problems.append(f"not in manifest: {rel}")
        elif expected[rel] != actual[rel]:
            problems.append(f"modified: {rel}")
    return problems


def snapshot_time(cache: Path = CACHE) -> dt.datetime | None:
    """Newest ``fetched_at`` across the cache: the moment the data reflects."""
    newest = 0
    for p in _files(cache):
        try:
            newest = max(newest, int(json.loads(p.read_text()).get("fetched_at", 0)))
        except (ValueError, json.JSONDecodeError):
            continue
    return dt.datetime.fromtimestamp(newest, dt.timezone.utc) if newest else None


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    cache = Path(sys.argv[2]) if len(sys.argv) > 2 else CACHE
    if cmd == "write":
        out = write(cache)
        print(f"wrote {out} ({len(_files(cache))} files)")
    elif cmd == "verify":
        problems = verify(cache)
        for x in problems:
            print(x)
        print("cache matches manifest" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)
    elif cmd == "snapshot":
        t = snapshot_time(cache)
        print(t.strftime("%Y-%m-%d %H:%M UTC") if t else "no cache")
    else:
        print(__doc__)
        sys.exit(1)
