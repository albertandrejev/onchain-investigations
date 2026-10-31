"""Run everything: cache integrity, unit tests, both case verifications, risk scoring.

    python verify.py            # offline, from the committed data/cache (checked against its manifest)
    python verify.py --refresh  # re-fetch everything from public nodes into data/cache.refresh and check it
    python verify.py --promote  # replace data/cache with a successful data/cache.refresh and rewrite the manifest

The committed cache is never deleted by --refresh: a failing public node cannot
destroy the snapshot the write-ups were verified against.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "data" / "cache"
REFRESH = ROOT / "data" / "cache.refresh"
PY = sys.executable


def run(args, env):
    print(f"\n$ {' '.join(args)}")
    return subprocess.call(args, cwd=ROOT, env=env)


def checks(env):
    rc = 0
    rc |= run([PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."], env)
    rc |= run([PY, "-m", "checks.case01"], env)
    rc |= run([PY, "-m", "checks.case02"], env)
    rc |= run([PY, "-m", "risk.score", "case01", "case02"], env)
    return rc


def main(argv):
    env = dict(os.environ)
    if "--promote" in argv:
        if not REFRESH.exists():
            sys.exit("nothing to promote: run --refresh first")
        if CACHE.exists():
            shutil.rmtree(CACHE)
        REFRESH.rename(CACHE)
        rc = run([PY, "-m", "tools.manifest", "write"], env)
        print("promoted data/cache.refresh -> data/cache")
        return rc
    if "--refresh" in argv:
        if REFRESH.exists():
            shutil.rmtree(REFRESH)
        env["CIP_CACHE"] = str(REFRESH)
        rc = checks(env)
        if rc == 0:
            run([PY, "-m", "tools.manifest", "write"], env)
            print("\nALL CHECKS PASSED against freshly fetched data in data/cache.refresh")
            print("Compare reports/ with git diff, then `python verify.py --promote` to adopt the new snapshot.")
        else:
            print("\nSOME CHECKS FAILED against fresh data; the committed cache is untouched")
        return rc
    if not CACHE.exists():
        sys.exit("data/cache is missing; run `python verify.py --refresh` then `--promote`")
    env["CIP_OFFLINE"] = "1"
    rc = run([PY, "-m", "tools.manifest", "verify"], env)
    if rc:
        print("\ncache does not match data/cache/MANIFEST.sha256; refusing to verify against edited data")
        return rc
    rc = checks(env)
    print("\nALL CHECKS PASSED" if rc == 0 else "\nSOME CHECKS FAILED")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
