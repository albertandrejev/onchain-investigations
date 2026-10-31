"""Transparent, rule-based address risk scoring for incident graphs.

Philosophy
----------
Commercial KYT tools return a number. An investigator has to *defend* a number,
so every point here comes from a named rule with a human-readable reason, and
the inputs are an explicit graph (``graphs/caseNN.json``) whose edges cite the
transactions they come from.

Scale: 0-100.  Bands: SEVERE >= 80, HIGH 60-79, MEDIUM 30-59, LOW < 30.

Entity classes change *what the score means*:

* ``wallet``          - scored for likelihood of being attacker-controlled.
* ``service``         - exchange deposit / hot wallet / bridge user account:
                        scored for *exposure* (how much tainted value it took),
                        and flagged as an action point (freeze / KYC request).
* ``infrastructure``  - routers, IBC adapters, module accounts, AMM pools,
                        bridge vaults: never scored (always 0). Treating these
                        as owners is the most common false positive.

Rules (points are additive, then capped at 100)
-----------------------------------------------
R1  confirmed seed (incident evidence)                         = 100
R2  same 20-byte key as a seed on another chain                = 95
R3  received value directly from a seed / same-key address     +45  (+ up to 15 by amount)
R3b received value from a wallet already scored HIGH/SEVERE      +35  (+ up to 15 by amount)
    (propagation: up to 3 passes, so taint follows the funds)
R4  sent value directly to a seed (funder)                      +35  (+10 if before incident)
R5  two hops from a seed (via a non-infrastructure wallet)      +20
R6  single-use intermediary (1 in / 1 out, < 1 h)               +15
R7  fresh address (first activity < 72 h before the incident)   +10
R8  funded from a privacy layer (shielded token, mixer)         +15
R9  structuring: >= 3 near-equal round outflows                 +10
R10 dormant accumulation (large inflow, never sent: nonce 0)    +10
R11 governance typology: vote with negligible stake, then large
    delegation shortly before voting ends                        +25
M1  established history (activity > 1 year before incident)     -15
M2  resolution recorded by investigators (e.g. funds returned,
    no link) - score is shown but band is overridden to RESOLVED
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from tools import bech32

BANDS = [(80, "SEVERE"), (60, "HIGH"), (30, "MEDIUM"), (0, "LOW")]


@dataclass
class Result:
    address: str
    entity: str
    score: int
    band: str
    reasons: list[str] = field(default_factory=list)
    action: str = ""


def _band(score: int) -> str:
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "LOW"


def _payload(addr: str) -> str | None:
    try:
        hrp, p = bech32.decode(addr)
        return p.hex() if len(p) == 20 else None
    except Exception:
        return None


def score_graph(graph: dict) -> list[Result]:
    nodes = {n["address"]: n for n in graph["nodes"]}
    edges = graph["edges"]
    seeds = {a for a, n in nodes.items() if "seed" in n.get("flags", [])}
    seed_payloads = {_payload(a) for a in seeds} - {None}
    same_key = {a for a in nodes if a not in seeds and _payload(a) in seed_payloads}
    core = seeds | same_key
    incident_ts = graph.get("incident_time")
    infra = {a for a, n in nodes.items() if n.get("entity") == "infrastructure"}
    # undirected adjacency, used for the two-hop rule (R5)
    neighbours: dict[str, set[str]] = {a: set() for a in nodes}
    for e in edges:
        neighbours.setdefault(e["from"], set()).add(e["to"])
        neighbours.setdefault(e["to"], set()).add(e["from"])
    one_hop = set().union(*(neighbours[c] for c in core)) - infra - core if core else set()
    high: set[str] = set()

    def amount_bonus(usd):
        return min(15, int(5 * math.log10(usd + 1))) if usd else 0

    def score_one(a):
        n = nodes[a]
        ent = n.get("entity", "wallet")
        flags = set(n.get("flags", []))
        reasons: list[str] = []
        if ent == "infrastructure":
            return Result(a, ent, 0, "N/A", [f"infrastructure ({n.get('label', '')}) — never scored as owner"])
        pts = 0
        if a in seeds:
            pts = 100
            reasons.append(f"R1 confirmed seed: {n.get('seed_reason', 'incident evidence')}")
        elif a in same_key:
            pts = 95
            reasons.append("R2 same 20-byte account key as a confirmed seed on another chain")
        else:
            ins = [e for e in edges if e["to"] == a and e["from"] in core]
            ins_high = [e for e in edges if e["to"] == a and e["from"] in high]
            outs = [e for e in edges if e["from"] == a and e["to"] in core]
            if ins:
                usd = sum(e.get("usd", 0) for e in ins)
                b = amount_bonus(usd)
                pts += 45 + b
                reasons.append(f"R3 received ${usd:,.0f} directly from seed/same-key address(es) (+{45 + b})")
            elif ins_high:
                usd = sum(e.get("usd", 0) for e in ins_high)
                b = amount_bonus(usd)
                pts += 35 + b
                reasons.append(f"R3b received ${usd:,.0f} from wallet(s) already scored HIGH/SEVERE (+{35 + b})")
            if outs:
                pre = bool(incident_ts) and any(e.get("time", "9") < incident_ts for e in outs)
                pts += 45 if pre else 35
                reasons.append("R4 funded a seed/same-key address" + (" before the incident (+45)" if pre else " (+35)"))
            if not ins and not ins_high and not outs and (neighbours[a] - infra) & one_hop:
                pts += 20
                reasons.append("R5 two hops from a seed via a non-infrastructure wallet (+20)")
            rules = {
                "single_use": ("R6 single-use intermediary: one inflow, one outflow within an hour", 15),
                "fresh": ("R7 fresh address: first activity < 72 h before the incident", 10),
                "privacy_funded": ("R8 funded from a privacy layer", 15),
                "structuring": ("R9 structuring: >= 3 near-equal round-number outflows", 10),
                "dormant_accumulation": ("R10 dormant accumulation: large inflow, never sent a tx", 10),
                "late_stake_vote": ("R11 voted with negligible stake, then large delegation minutes before close", 25),
            }
            for f, (text, p) in rules.items():
                if f in flags:
                    pts += p
                    reasons.append(f"{text} (+{p})")
            if "established" in flags:
                pts -= 15
                reasons.append("M1 established history > 1 year before incident (-15)")
        pts = max(0, min(100, pts))
        band, action = _band(pts), ""
        if ent == "service":
            band = f"EXPOSURE-{band}"
            action = n.get("action", "VASP/service: freeze + KYC request with tx list")
        if n.get("resolution"):
            reasons.append(f"M2 resolution: {n['resolution']}")
            band = "RESOLVED"
        return Result(a, ent, pts, band, reasons, action)

    results = {}
    for _ in range(3):  # propagate taint along the flow
        results = {a: score_one(a) for a in nodes}
        new_high = {a for a, r in results.items()
                    if r.score >= 60 and r.entity == "wallet" and r.band != "RESOLVED"}
        if new_high == high:
            break
        high = new_high
    out = sorted(results.values(), key=lambda r: (-r.score, r.address))
    return out


def render_markdown(graph: dict, results: list[Result]) -> str:
    nodes = {n["address"]: n for n in graph["nodes"]}
    lines = [f"# Risk scoring — {graph['title']}", "",
             "Generated by `python -m risk.score " + graph["id"] + "`. Model and rules: `risk/model.py`.",
             "Graph inputs (nodes, edges, cited transactions): `graphs/" + graph["id"] + ".json`.", "",
             "| Score | Band | Entity | Label | Address | Reasons | Action |", "|---:|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r.score} | {r.band} | {r.entity} | {nodes[r.address].get('label', '')} | `{r.address}` | "
                     + "<br>".join(r.reasons) + f" | {r.action} |")
    lines += ["", "## Edges used", "", "| From | To | Asset | USD | Tx | Note |", "|---|---|---|---:|---|---|"]
    for e in graph["edges"]:
        lines.append(f"| `{e['from']}` | `{e['to']}` | {e.get('asset', '')} | {e.get('usd', 0):,.0f} | "
                     f"`{e.get('tx', '')}` | {e.get('note', '')} |")
    return "\n".join(lines) + "\n"


def load(case_id: str) -> dict:
    return json.loads((Path(__file__).resolve().parent.parent / "graphs" / f"{case_id}.json").read_text())
