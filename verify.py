"""Run everything: per-case cache integrity, unit tests, every case's checks, risk scoring,
incident-graph diagrams, and the structure lint of every write-up (docs/REPORT_STYLE.md).

    python verify.py                # offline, each case from its committed data/cache (checked against its manifest)
    python verify.py --refresh      # re-fetch each case into cases/NN-slug/data/cache.refresh and check it
    python verify.py --promote      # adopt a successful data/cache.refresh as data/cache and rewrite the manifest
    python verify.py 03 --refresh   # any mode, limited to the cases whose folder name starts with "03"

Cases are discovered automatically: every cases/NN-slug/ with a checks.py.
A committed cache is never deleted by --refresh: a failing public node cannot
destroy the snapshot the write-ups were verified against.
For case 03 set TRONGRID_API_KEY when refreshing (TronGrid rate-limits hard without one).
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(args, env):
    print(f"\n$ {' '.join(str(a) for a in args)}")
    return subprocess.call(args, cwd=ROOT, env=env)


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def main(argv):
    flags = {a for a in argv if a.startswith("--")}
    picks = [a for a in argv if not a.startswith("--")]
    cases = [p.parent for p in sorted((ROOT / "cases").glob("*/checks.py"))
             if not picks or any(p.parent.name.startswith(k) for k in picks)]
    if not cases:
        sys.exit("no matching cases")
    base = dict(os.environ)
    rc = 0

    if "--promote" in flags:
        for c in cases:
            fresh, cache = c / "data" / "cache.refresh", c / "data" / "cache"
            if not fresh.exists():
                print(f"{rel(c)}: nothing to promote (run --refresh first)")
                continue
            if cache.exists():
                shutil.rmtree(cache)
            fresh.rename(cache)
            rc |= run([PY, "-m", "tools.manifest", "write", rel(cache)], base)
            print(f"promoted {rel(fresh)} -> {rel(cache)}")
        return rc

    refresh = "--refresh" in flags
    rc |= run([PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."], base)
    for c in cases:
        env = dict(base)
        if refresh:
            cache = c / "data" / "cache.refresh"
            if cache.exists():
                shutil.rmtree(cache)
        else:
            cache = c / "data" / "cache"
            env["CIP_OFFLINE"] = "1"
            bad = run([PY, "-m", "tools.manifest", "verify", rel(cache)], env)
            if bad:
                print(f"\n{rel(cache)} does not match its MANIFEST.sha256; refusing to verify against edited data")
                rc |= bad
                continue
        env["CIP_CACHE"] = str(cache)
        case_rc = run([PY, rel(c / "checks.py")], env)
        if refresh and case_rc == 0:
            run([PY, "-m", "tools.manifest", "write", rel(cache)], env)
        rc |= case_rc
    graphs = [rel(c) for c in cases if (c / "graph.json").exists()]
    if graphs:
        rc |= run([PY, "-m", "risk.score", *graphs], base)
        rc |= run([PY, "-m", "tools.diagrams", *graphs], base)
    # last: the lint compares the write-up with the reports generated above
    rc |= run([PY, "-m", "tools.casedoc", "lint", *(rel(c) for c in cases)], base)
    rc |= run([PY, "-m", "tools.casedoc", "template"], base)

    if refresh:
        print("\nALL CHECKS PASSED against freshly fetched data" if rc == 0 else
              "\nSOME CHECKS FAILED against fresh data; the committed caches are untouched")
        if rc == 0:
            print("Compare cases/*/reports/ with git diff, then `python verify.py --promote` to adopt the new snapshots.")
    else:
        print("\nALL CHECKS PASSED" if rc == 0 else "\nSOME CHECKS FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
