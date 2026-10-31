"""CLI: score a case graph and write reports/risk-<case>.md

    python -m risk.score case01
    python -m risk.score case02
"""
import sys
from pathlib import Path

from risk.model import load, score_graph, render_markdown

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    for case in sys.argv[1:] or ["case01", "case02"]:
        g = load(case)
        res = score_graph(g)
        out = ROOT / "reports" / f"risk-{case}.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(render_markdown(g, res))
        print(f"== {g['title']}")
        for r in res:
            print(f"{r.score:>3} {r.band:<16} {r.entity:<14} {r.address}")
        print(f"-> {out.relative_to(ROOT)}\n")
