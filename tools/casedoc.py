"""Structure lint for case write-ups (cases/NN-slug/README.md) and the template in docs/.

    python -m tools.casedoc lint                        # every case folder
    python -m tools.casedoc lint cases/03-chainflip-tron-duplicate-payouts
    python -m tools.casedoc template docs/CASE_TEMPLATE.md

The rules are the ones in docs/REPORT_STYLE.md that a machine can check:
section set and order, the fixed tables (case card, addresses, confidence),
the diagrams at the top of "How it unfolded", links to the generated reports,
and that every check ID cited in the text exists in reports/verification.md.
Prose is not checked. A failing lint fails `python verify.py`, like a failing check.
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Section:
    name: str
    required: bool


# Canonical order. A heading matches a section when it starts with the section's name,
# so "Background: why this was possible" is the Background section.
SECTIONS = [
    Section("TL;DR", True),
    Section("Case card", True),
    Section("What this analysis adds", False),
    Section("Addresses", True),
    Section("My role", True),
    Section("Objectives", False),
    Section("Background", False),
    Section("Methodology and tools", False),
    Section("How it unfolded", True),
    Section("False leads, resolved", True),
    Section("Containment and recovery", True),
    Section("Risk scoring", True),
    Section("Confidence assessment", True),
    Section("Limitations", True),
    Section("Open leads", True),
    Section("Lessons learned", True),
    Section("Appendix: key references", True),
]
CASE_CARD_ROWS = ["Dates", "Chains", "Assets", "Loss", "Outcome", "My role", "Checks"]
CONFIDENCE_LEVELS = ["Proven", "Strong", "Moderate", "Suspicion", "Not established"]
MERMAID_TYPES = ("flowchart", "graph", "sequenceDiagram", "timeline", "gantt", "pie", "xychart-beta")
CHECK_ID = re.compile(r"\bC(\d+)-(\d+[A-Za-z]?)\b")


def _section_of(heading: str) -> Section | None:
    for s in SECTIONS:
        if heading == s.name or heading.startswith(s.name + ":") or heading.startswith(s.name + " "):
            return s
    return None


def _split(text: str):
    """Return (preamble lines, [(h2 heading, body lines)]), ignoring headings inside code fences."""
    pre, parts, fence = [], [], False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            parts.append((line[3:].strip(), []))
        elif parts:
            parts[-1][1].append(line)
        else:
            pre.append(line)
    return pre, parts


def _tables(lines):
    """Yield each Markdown table in ``lines`` as a list of rows (list of cells), header row first."""
    rows = []
    for line in lines + [""]:
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [c.strip() for c in s[1:-1].split("|")]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                rows.append(cells)
        elif rows:
            yield rows
            rows = []


def _mermaid_blocks(lines):
    """Yield (index of the opening fence, diagram type) for each ```mermaid block."""
    for i, line in enumerate(lines):
        if line.strip() == "```mermaid":
            body = next((l.strip() for l in lines[i + 1:] if l.strip()), "")
            yield i, body.split()[0] if body else ""


def _plain(cell: str) -> str:
    return re.sub(r"[*`]", "", cell).strip()


def lint_text(text: str, case_no: str | None = None, verified_ids: set[str] | None = None,
              passed: int | None = None) -> list[str]:
    """Lint one write-up. ``case_no`` ("03"), ``verified_ids`` and ``passed`` come from the case
    folder; leave them None for the template, which has placeholders instead of real values."""
    errors: list[str] = []
    pre, parts = _split(text)
    body = {}

    # Title and header note
    h1 = next((l for l in pre if l.startswith("# ")), None)
    number = r"\d{2}" if case_no else r"(\d{2}|NN)"  # the template keeps the NN placeholder
    if not h1 or not re.match(rf"# Case {number}: \S", h1):
        errors.append("title must be '# Case NN: <what happened>'")
    elif case_no and not h1.startswith(f"# Case {case_no}:"):
        errors.append(f"title number does not match the folder: expected 'Case {case_no}'")
    note = "\n".join(l for l in pre if l.startswith(">"))
    if "**Reproducibility" not in note:
        errors.append("header note must contain a '**Reproducibility.**' paragraph")
    for link in ("reports/verification.md", "reports/risk.md"):
        if f"]({link})" not in note:
            errors.append(f"header note must link [..]({link})")

    # Section set and order
    seen: list[Section] = []
    for heading, lines in parts:
        s = _section_of(heading)
        if s is None:
            errors.append(f"unknown section '## {heading}' (allowed: see SECTIONS in tools/casedoc.py)")
            continue
        if s in seen:
            errors.append(f"section '{s.name}' appears twice")
            continue
        if seen and SECTIONS.index(s) < SECTIONS.index(seen[-1]):
            errors.append(f"section '{s.name}' must come before '{seen[-1].name}'")
        seen.append(s)
        body[s.name] = lines
    for s in SECTIONS:
        if s.required and s not in seen:
            errors.append(f"missing required section '## {s.name}'")

    # Case card
    if "Case card" in body:
        tables = list(_tables(body["Case card"]))
        keys = [_plain(r[0]) for r in tables[0][1:]] if tables else []
        if keys != CASE_CARD_ROWS:
            errors.append(f"case card rows must be exactly {CASE_CARD_ROWS}, found {keys}")
        elif passed is not None:
            checks = _plain(tables[0][1 + CASE_CARD_ROWS.index("Checks")][1])
            if not checks.startswith(f"{passed} "):
                errors.append(f"case card 'Checks' must start with {passed} (passed in reports/verification.md)")

    # Addresses
    if "Addresses" in body:
        tables = list(_tables(body["Addresses"]))
        if not tables or [_plain(c) for c in tables[0][0]] != ["Role", "Address"]:
            errors.append("Addresses must start with a '| Role | Address |' table")

    # How it unfolded: overview diagrams first, then numbered steps
    if "How it unfolded" in body:
        lines = body["How it unfolded"]
        first_step = next((i for i, l in enumerate(lines) if l.startswith("### ")), len(lines))
        kinds = [k for i, k in _mermaid_blocks(lines) if i < first_step]
        if not any(k in ("flowchart", "graph") for k in kinds):
            errors.append("How it unfolded must open with a Mermaid flowchart of the money flow")
        if "timeline" not in kinds and "gantt" not in kinds:
            errors.append("How it unfolded must open with a Mermaid timeline (or gantt) of the incident")
        steps = [l for l in lines if l.startswith("### ")]
        if not steps:
            errors.append("How it unfolded needs numbered steps '### 1. ...'")
        for n, step in enumerate(steps, 1):
            if not step.startswith(f"### {n}. "):
                errors.append(f"step headings must be numbered 1, 2, 3...: expected '### {n}. ', found '{step}'")
                break

    # Risk scoring links both generated reports
    if "Risk scoring" in body:
        joined = "\n".join(body["Risk scoring"])
        for link in ("reports/risk.md", "reports/graph.md"):
            if f"]({link})" not in joined:
                errors.append(f"Risk scoring must link [..]({link})")

    # Confidence assessment
    if "Confidence assessment" in body:
        tables = list(_tables(body["Confidence assessment"]))
        if not tables or [_plain(c) for c in tables[0][0]] != ["Level", "Statement"]:
            errors.append("Confidence assessment must be a '| Level | Statement |' table")
        else:
            levels = []
            for row in tables[0][1:]:
                lvl = next((L for L in CONFIDENCE_LEVELS if _plain(row[0]).startswith(L)), None)
                if lvl is None:
                    errors.append(f"unknown confidence level '{_plain(row[0])}' (use {CONFIDENCE_LEVELS})")
                levels.append(lvl)
            known = [l for l in levels if l]
            if known != sorted(known, key=CONFIDENCE_LEVELS.index):
                errors.append(f"confidence levels must be in the order {CONFIDENCE_LEVELS}")
            if "Proven" not in known:
                errors.append("Confidence assessment needs a 'Proven' row")

    if "Appendix: key references" in body:
        tables = list(_tables(body["Appendix: key references"]))
        if not tables or [_plain(c) for c in tables[0][0]] != ["Event", "Chain", "Reference"]:
            errors.append("Appendix must contain an '| Event | Chain | Reference |' table")

    # Every Mermaid block has a known diagram type
    all_lines = text.splitlines()
    for i, kind in _mermaid_blocks(all_lines):
        if kind not in MERMAID_TYPES:
            errors.append(f"line {i + 1}: Mermaid block of unknown type '{kind}' (use {MERMAID_TYPES})")
        if kind == "timeline":
            # Mermaid's timeline grammar rejects ':' inside a period or an event, so 08:22 breaks it
            for j in range(i + 1, len(all_lines)):
                line = all_lines[j]
                if line.startswith("```"):
                    break
                if " : " in line and any(":" in part for part in line.split(" : ")):
                    errors.append(f"line {j + 1}: a timeline entry cannot contain ':'; write times as 08.22")

    # Cited check IDs exist
    if case_no is not None and verified_ids is not None:
        for m in CHECK_ID.finditer(text):
            if m.group(1).zfill(2) != case_no:
                errors.append(f"{m.group(0)} cites another case's check; cite it as text, not as an ID")
            elif m.group(0) not in verified_ids:
                errors.append(f"{m.group(0)} is cited but is not in reports/verification.md")
    return errors


def lint_case(case_dir: Path) -> list[str]:
    case_dir = Path(case_dir)
    readme = case_dir / "README.md"
    if not readme.exists():
        return ["README.md missing"]
    case_no = case_dir.name[:2]
    ver = case_dir / "reports" / "verification.md"
    ids, passed = None, None
    if ver.exists():
        vtext = ver.read_text()
        ids = set(re.findall(r"^\| (C\d+-\d+[A-Za-z]?) \|", vtext, flags=re.M))
        m = re.search(r"Result: \*\*(\d+) passed", vtext)
        passed = int(m.group(1)) if m else None
    errors = lint_text(readme.read_text(), case_no, ids, passed)
    if (case_dir / "graph.json").exists() and not (case_dir / "reports" / "graph.md").exists():
        errors.append("reports/graph.md missing: run `python -m tools.diagrams` (verify.py does)")
    return errors


def _main(argv) -> int:
    if not argv or argv[0] not in ("lint", "template"):
        print(__doc__)
        return 2
    rc = 0
    if argv[0] == "template":
        for p in argv[1:] or [str(ROOT / "docs" / "CASE_TEMPLATE.md")]:
            errs = lint_text(Path(p).read_text())
            print(f"{p}: {'OK' if not errs else 'FAIL'}")
            for e in errs:
                print(f"  - {e}")
            rc |= bool(errs)
        return rc
    dirs = [Path(a) for a in argv[1:]] or sorted(p.parent for p in (ROOT / "cases").glob("*/README.md"))
    for d in dirs:
        errs = lint_case(d)
        print(f"{d.name}/README.md: {'structure OK' if not errs else 'FAIL'}")
        for e in errs:
            print(f"  - {e}")
        rc |= bool(errs)
    return rc


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
