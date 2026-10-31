"""CLI: score case graphs and write cases/NN-slug/reports/risk.md

    python -m risk.score                                   # every case that has a graph.json
    python -m risk.score cases/02-neutron-governance-attack
"""
import sys
from pathlib import Path

from risk.model import load, score_graph, render_markdown

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    dirs = [Path(a) for a in sys.argv[1:]] or sorted(p.parent for p in (ROOT / "cases").glob("*/graph.json"))
    for d in dirs:
        g = load(d)
        res = score_graph(g)
        out = d.resolve() / "reports" / "risk.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(render_markdown(g, res))
        print(f"== {g['title']}")
        for r in res:
            print(f"{r.score:>3} {r.band:<16} {r.entity:<14} {r.address}")
        print(f"-> {out.relative_to(ROOT)}\n")
