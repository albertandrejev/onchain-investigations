"""Case 02 — Neutron governance takeover — every number re-derived from chain data.

Run:  python -m checks.case02
"""
from __future__ import annotations

import base64
import datetime as dt
import json
from decimal import Decimal

from tools import bech32, cctp
from tools.net import Cosmos, events, ethereum, tendermint_rpc, parse_coins
from checks.framework import Report, micro, D

NEUTRON, HUB, NOBLE, SECRET, DYDX = (Cosmos(c) for c in ("neutron", "cosmoshub", "noble", "secretnetwork", "dydx"))

ATTACKER = "neutron1dd25c4sshelrpfs0433apg24c5phrhk8l6n605"
VOTER = "neutron1ekgfga6vv4zdrrjn3dux6f62fuzektfndgaehm"
ATT_HUB = bech32.convert(ATTACKER, "cosmos")
VOTER_HUB = bech32.convert(VOTER, "cosmos")
ATT_NOBLE = bech32.convert(ATTACKER, "noble")
VOTER_NOBLE = bech32.convert(VOTER, "noble")
ATT_DYDX = bech32.convert(ATTACKER, "dydx")
SECRET_KEY = "secret1mru6cp7ft8cfasaye4g6vum52qygnkq0cgw0az"
ETH_WORK = "0xe149310eb8b1b3d9c471ccd81819d393621fba5c"
ETH_COLLECT = "0xef6c5a31df984c8569236a0abc1f27580e2a5d54"
HUB_RECOVERY = "cosmos1z8pq5cn7tdrwwzlwm0e44fgq07e43ner6vph64"
USDC = "ibc/B559A80D62249C8AA07A380E2A2BEA6E5CA9A6F079C912C3A9E9B494105E4F81"
DELEGATION_TX = "71FB94AE30C7CEC1F0D9B2B8BC74961DD1F3053A0BA2B4B2F0CF6E4C6C55C266"
FIRST_DRAIN_TX = "7B155828BAB0B4325B86793D226F9872922EBAFAAAF62F341A1FDDE13E162C96"
ETH_500 = "0x1c3a5dfe64998aabfa18ea17a894b12c5e4d06507c96738ddf236ab4348cefc4"
ETH_170 = "0xc19ea5b70bae47619d73b24f51456dfd6c84c585e19166d4a44b41feb95818df"
ETH_94 = "0x4c3852241b01c3070aefe65ad69d1b7723da7600fb2195d45850601aff06bf9e"


def T(s):
    return dt.datetime.fromisoformat(s[:19] + "+00:00")


def all_txs(chain: Cosmos, query: str):
    s = chain.search(query, limit=100)
    return list(zip(s["txs"], s["tx_responses"]))


def c_proposal(r: Report):
    p = NEUTRON.get("/cosmos/gov/v1/proposals/9", valid=lambda x: "proposal" in x)["proposal"]
    msgs = p["messages"]
    r.claim("C2-01", "Proposal 9: 11 × MsgUpdateAdmin, all to the attacker", (11, {ATTACKER}),
            (sum(m["@type"].endswith("MsgUpdateAdmin") for m in msgs), {m["new_admin"] for m in msgs}),
            evidence=["neutron gov proposal 9", ATTACKER])
    r.claim("C2-01b", "Expedited, proposer = attacker", (True, ATTACKER), (p["expedited"], p["proposer"]))
    for i, m in enumerate(msgs):
        info = NEUTRON.get(f"/cosmwasm/wasm/v1/contract/{m['contract']}", height=61632000,
                           valid=lambda x: "contract_info" in x)["contract_info"]
        r.ev(f"target contract {i+1}: {info['label']}", m["contract"])
    p5 = NEUTRON.get("/cosmos/gov/v1/proposals/5", valid=lambda x: "proposal" in x)["proposal"]
    t5 = p5["final_tally_result"]
    r.claim("C2-02", "Proposal 5 rejected: Yes ≈0.32M vs No ≈10.42M NTRN", ("PROPOSAL_STATUS_REJECTED", D("0.32"), D("10.42")),
            (p5["status"], round(micro(t5["yes_count"]) / 10**6, 2), round(micro(t5["no_count"]) / 10**6, 2)),
            evidence=["neutron gov proposal 5"])
    sub = [(t, x) for t, x in all_txs(NEUTRON, f"message.sender='{ATTACKER}'")
           if t["body"]["messages"][0]["@type"].split(".")[-1] in ("MsgSubmitProposal", "MsgCancelProposal", "MsgStoreCode")]
    for t, x in sub:
        r.ev(f"{t['body']['messages'][0]['@type'].split('.')[-1]} @ {x['timestamp']}", x["txhash"])
    return p


def c_tally(r: Report):
    p = NEUTRON.get("/cosmos/gov/v1/proposals/9", valid=lambda x: "proposal" in x)["proposal"]
    t = {k: micro(v) for k, v in p["final_tally_result"].items()}
    end = p["voting_end_time"]
    # height closest to voting end: delegation tx height + blocks; we take 61633000 (02:24 +/- seconds)
    H = 61633000
    pool = NEUTRON.get("/cosmos/staking/v1beta1/pool", height=H, valid=lambda x: "pool" in x)["pool"]
    bonded = micro(pool["bonded_tokens"])
    turnout = t["yes_count"] + t["no_count"] + t["no_with_veto_count"] + t["abstain_count"]
    quorum = bonded * D("0.30")
    r.claim("C2-03", "Turnout ≥ quorum (30 % of bonded) — proposal passed",
            True, turnout >= quorum, evidence=["neutron gov proposal 9", f"staking pool @ height {H}"])
    r.note("C2-03b", "Bonded / quorum / turnout (NTRN)", f"{bonded:,.0f} / {quorum:,.0f} / {turnout:,.0f} ({turnout/bonded:.1%})")
    yes_share = t["yes_count"] / (t["yes_count"] + t["no_count"] + t["no_with_veto_count"])
    r.claim("C2-03c", "Yes share above the 67 % expedited threshold", True, yes_share > D("0.67"))
    r.note("C2-03d", "Yes share", f"{yes_share:.1%}")
    # who voted
    votes = all_txs(NEUTRON, "proposal_vote.proposal_id='9'")
    last = {}
    for tx, x in votes:
        for m in tx["body"]["messages"]:
            if m["@type"].endswith("MsgVote"):
                last[m["voter"]] = (m["option"], x["txhash"], x["timestamp"])
    biggest_no = None
    for voter, (opt, h, ts) in last.items():
        if opt != "VOTE_OPTION_NO":
            continue
        # a validator's operator account votes from the same key; most NO voters are not
        # validators, so a "not found" answer (gRPC code 5 / 3) is a valid, final reply here
        val = bech32.convert(voter, "neutronvaloper")
        v = NEUTRON.get(f"/cosmos/staking/v1beta1/validators/{val}", height=H,
                        valid=lambda x: "validator" in x or x.get("code") in (5, 3))
        if "validator" in v:
            tok = micro(v["validator"]["tokens"])
            if biggest_no is None or tok > biggest_no[1]:
                biggest_no = (val, tok, h)
    without = turnout - biggest_no[1]
    r.claim("C2-04", "Quorum paradox: without the single largest validator's NO, turnout < quorum",
            True, without < quorum, evidence=[biggest_no[2]])
    r.note("C2-04b", "Turnout without that validator's No (NTRN, % of bonded)", f"{without:,.0f} ({without/bonded:.1%})")
    r.ev("largest NO vote (validator) tx", biggest_no[2])
    # voter
    vote = last[VOTER]
    r.claim("C2-05", "Voting wallet voted YES early", "VOTE_OPTION_YES", vote[0], evidence=[vote[1]])
    r.ev(f"voting wallet YES vote @ {vote[2]}", vote[1])
    d = NEUTRON.tx(DELEGATION_TX)
    amt = micro(d["tx"]["body"]["messages"][0]["amount"]["amount"])
    r.claim("C2-06", "Last-minute delegation by the voting wallet (NTRN)", D(31620000), amt, evidence=[DELEGATION_TX])
    gap = T(end) - T(d["tx_response"]["timestamp"])
    r.claim("C2-06b", "Minutes between delegation and voting end", 11, int(gap.total_seconds() // 60))
    stake_at_end = NEUTRON.get(f"/cosmos/staking/v1beta1/delegations/{VOTER}", height=H,
                               valid=lambda x: "delegation_responses" in x)
    tot = sum(micro(x["balance"]["amount"]) for x in stake_at_end["delegation_responses"])
    r.claim("C2-06c", "Voting wallet's stake at close ≈ 84.7 % of all YES", D("84.7"),
            round(tot / t["yes_count"] * 100, 1))
    r.ev("voting wallet last-minute delegation (Neutron)", DELEGATION_TX)


def c_purchase(r: Report):
    usdc_in = Decimal(0)
    ntrn_out = Decimal(0)
    hashes = []
    for tx, x in all_txs(NEUTRON, f"message.sender='{VOTER}'"):
        for _, a in events(x, "wasm"):
            if a.get("action") == "swap" and a.get("offer_asset") == USDC:
                usdc_in += micro(a["offer_amount"])
        for _, a in events(x, "transfer"):
            n = parse_coins(a.get("amount", "")).get("untrn", 0)
            if a.get("recipient") == VOTER and n > 10**9:
                ntrn_out += micro(n)
                hashes.append(x["txhash"])
    hashes = sorted(set(hashes))
    r.claim("C2-07", "USDC spent on NTRN by the voting wallet", D(20199), usdc_in, tol=D(1), evidence=hashes)
    r.claim("C2-07b", "NTRN bought", D(31627304), ntrn_out, tol=D(1))
    for h in hashes:
        r.ev(f"NTRN purchase {h[:6]}", h)
    # privacy-USDC funding
    info = SECRET.get("/compute/v1beta1/info/secret1chsejpk9kfj4vt9ec6xvyguw539gsdtr775us2", valid=lambda x: "contract_info" in x)
    red = Decimal(0)
    rh = []
    for tx, x in all_txs(SECRET, f"message.sender='{SECRET_KEY}'"):
        for _, a in events(x, "ibc_transfer"):
            if a.get("receiver") == VOTER_NOBLE:
                red += micro(a["amount"])
                rh.append(x["txhash"])
    r.claim("C2-08", "Private SNIP-20 USDC redeemed and sent to voting wallet on Noble", D("20200.1"), red, evidence=rh)
    r.claim("C2-08b", "Redeemed from contract label", "secret-noble-usdc", info["contract_info"]["label"])
    for h in rh:
        r.ev(f"Secret private-USDC redemption -> {VOTER_NOBLE}", h)
    r.ev("Secret key funding the vote", SECRET_KEY)


def c_link(r: Report):
    for tx, x in all_txs(HUB, f"message.sender='{ATT_HUB}'"):
        m = tx["body"]["messages"][0]
        if m.get("to_address") == VOTER_HUB:
            r.claim("C2-09", "On-chain link: attacker Hub address funds the voting wallet's Hub address (ATOM)",
                    D(1), micro(m["amount"][0]["amount"]), evidence=[x["txhash"]])
            r.ev("link attacker -> voting wallet (Cosmos Hub)", x["txhash"])
            return
    r.claim("C2-09", "link tx found", True, False)


def _ibc_out(txs, receiver: str, denom: str | None = None, decimals: int = 6):
    """Amounts of successful MsgTransfer txs to ``receiver`` (optionally one denom)."""
    out = []
    for tx, x in txs:
        m = tx["body"]["messages"][0]
        if (m["@type"].endswith("MsgTransfer") and x["code"] == 0 and m["receiver"] == receiver
                and (denom is None or m["token"]["denom"] == denom)):
            out.append(micro(m["token"]["amount"], decimals))
    return out


def c_drain(r: Report):
    txs = all_txs(NEUTRON, f"message.sender='{ATTACKER}'")
    mig = [(tx, x) for tx, x in txs if tx["body"]["messages"][0]["@type"].endswith("MsgMigrateContract")]
    wd = [(tx, x) for tx, x in txs if "withdraw_all" in (tx["body"]["messages"][0].get("msg") or {})]
    r.claim("C2-10", "10 contracts migrated and drained with withdraw_all", (10, 10), (len(mig), len(wd)),
            evidence=[x["txhash"] for _, x in wd])
    span = T(wd[-1][1]["timestamp"]) - T(mig[0][1]["timestamp"])
    r.claim("C2-10b", "Drain window, first migrate to last withdraw (minutes, rounded)", 26, round(span.total_seconds() / 60))
    for tx, x in mig:
        r.ev(f"migrate {tx['body']['messages'][0]['contract']}", x["txhash"])
    for tx, x in wd:
        r.ev(f"withdraw_all {tx['body']['messages'][0]['contract']}", x["txhash"])
    # outflows
    rl = [x["txhash"] for tx, x in txs
          if (m := tx["body"]["messages"][0])["@type"].endswith("MsgTransfer") and m["receiver"] == ATT_NOBLE
          and m["token"]["denom"] == USDC and x["code"] != 0 and "Rate Limit" in x.get("raw_log", "")]
    r.claim("C2-11", "USDC that left Neutron for Noble", D(1180010), sum(_ibc_out(txs, ATT_NOBLE, USDC)))
    r.claim("C2-11b", "USDC transfers rejected by the IBC rate limiter (count)", True, len(rl) >= 5, evidence=rl)
    r.note("C2-11c", "Rate-limited USDC transfer attempts", len(rl))
    for h in rl:
        r.ev("IBC rate-limit rejection (Neutron)", h)
    at_halt = NEUTRON.balances(ATTACKER, height=61635574)
    r.claim("C2-11d", "USDC still on attacker account when Neutron halted", D("1671301.712957"), micro(at_halt.get(USDC, 0)))
    r.claim("C2-12", "ATOM moved to the Cosmos Hub", D("1723180.290498"), sum(_ibc_out(txs, ATT_HUB)))
    r.claim("C2-13", "DYDX moved to dYdX", D("803955.137309890275785395"), sum(_ibc_out(txs, ATT_DYDX, decimals=18)))
    one_k = [x["txhash"] for tx, x in txs if tx["body"]["messages"][0]["@type"].endswith("MsgSend")
             and tx["body"]["messages"][0]["to_address"] == "neutron15m3hh904d0cwe4t69ec2w5cmc8535gkxwhgrp5"]
    r.note("C2-13b", "1,000 USDC sent to an unrelated YES voter (returned by owner; false lead)", len(one_k), evidence=one_k)
    for h in one_k:
        r.ev("1,000 USDC to unrelated YES voter (Neutron)", h)


def c_noble_cctp(r: Report):
    total = Decimal(0)
    rec = set()
    for tx, x in all_txs(NOBLE, f"message.sender='{ATT_NOBLE}'"):
        for m in tx["body"]["messages"]:
            if "DepositForBurn" in m["@type"]:
                d = cctp.decode_deposit_for_burn(m)
                total += micro(d["amount"])
                rec.add((d["destination_chain"], d["mint_recipient"]))
                r.ev(f"Noble CCTP burn {micro(d['amount']):,.2f} USDC -> {d['destination_chain']}", x["txhash"])
    r.claim("C2-14", "USDC burned on Noble via CCTP to Ethereum", D("1180004.613819"), total)
    r.claim("C2-14b", "Single CCTP recipient: attacker's Ethereum working wallet", {("Ethereum", ETH_WORK)},
            {(a, b.lower()) for a, b in rec})


def c_hub(r: Report):
    txs = all_txs(HUB, f"message.sender='{ATT_HUB}'")
    thor = [(tx, x) for tx, x in txs if tx["body"]["memo"].startswith("=:e:")]
    big = [t for t in thor if int(t[0]["body"]["messages"][0]["amount"][0]["amount"]) >= 10**11]
    r.claim("C2-15", "THORChain swaps ATOM→ETH to the attacker's Ethereum wallet (ATOM)", D(500000),
            sum(micro(t[0]["body"]["messages"][0]["amount"][0]["amount"]) for t in big),
            evidence=[t[1]["txhash"] for t in big])
    r.claim("C2-15b", "THORChain memo destination = Ethereum working wallet", {ETH_WORK},
            {t[0]["body"]["memo"].split(":")[2].lower() for t in thor})
    for t in thor:
        r.ev(f"THORChain swap {micro(t[0]['body']['messages'][0]['amount'][0]['amount']):,.0f} ATOM", t[1]["txhash"])
    refunds = Decimal(0)
    for tx, x in all_txs(HUB, f"transfer.recipient='{ATT_HUB}'"):
        if tx["body"]["memo"].startswith("REFUND:"):
            a = micro(tx["body"]["messages"][0]["amount"][0]["amount"])
            refunds += a
            r.ev(f"THORChain refund {a:,.6f} ATOM", x["txhash"])
    r.note("C2-15c", "ATOM actually swapped by THORChain (500,000 − refunds)", f"{D(500000) - refunds:,.2f}")
    before = HUB.balances(ATT_HUB, height=33085380).get("uatom", 0)
    r.claim("C2-16", "Attacker Hub balance before the halt (ATOM)", D("1227121.374688"), micro(before))
    br = tendermint_rpc("cosmoshub", "/block_results?height=33086741")["result"]
    evs = (br.get("finalize_block_events") or []) + (br.get("begin_block_events") or [])
    moved = [{a["key"]: a.get("value") for a in e["attributes"]} for e in evs if e["type"] == "transfer"]
    moved = [m for m in moved if m.get("sender") == ATT_HUB]
    r.claim("C2-16b", "Recovery state change at block 33,086,741 moves it to the 4-of-6 recovery multisig",
            (HUB_RECOVERY, "1227121374688uatom"), (moved[0]["recipient"], moved[0]["amount"]),
            evidence=["cosmoshub block 33086741 events"])
    esc = [(tx, x) for tx, x in txs if x["code"] == 0 and tx["body"]["messages"][0]["@type"].endswith("MsgTransfer")
           and x["timestamp"] > "2026-09-23"]
    r.claim("C2-17", "After restart the THORChain refund (168,990 ATOM) was moved to Osmosis",
            D(168990), micro(esc[0][0]["body"]["messages"][0]["token"]["amount"]), evidence=[esc[0][1]["txhash"]])
    r.ev("refund moved to Osmosis (Cosmos Hub)", esc[0][1]["txhash"])
    r.ev("Hub recovery multisig", HUB_RECOVERY)


def c_halts(r: Report):
    n0, n1 = NEUTRON.block_time(61635574), NEUTRON.block_time(61635575)
    r.claim("C2-18", "Neutron halt ≥ 3 days between blocks 61,635,574 and 61,635,575", True,
            (T(n1) - T(n0)).total_seconds() > 3 * 86400)
    r.note("C2-18b", "Neutron halt window", f"{n0} → {n1}")
    h0, h1 = HUB.block_time(33086741), HUB.block_time(33086742)
    r.claim("C2-19", "Cosmos Hub halt ≈ 24 h 48 m between blocks 33,086,741 and 33,086,742", True,
            24 * 3600 < (T(h1) - T(h0)).total_seconds() < 26 * 3600)
    r.note("C2-19b", "Hub halt window", f"{h0} → {h1}")


def c_dydx(r: Report):
    s = DYDX.search(f"message.sender='{ATT_DYDX}'")
    sends = [(tx["body"]["messages"][0], x) for tx, x in zip(s["txs"], s["tx_responses"])]
    total = sum(micro(m["amount"][0]["amount"], 18) for m, _ in sends)
    r.claim("C2-20", "DYDX sent out in transfers (sum)", D(803955), total, evidence=[x["txhash"] for _, x in sends])
    tagged = [x for m, x in sends if (x.get("tx") or {}).get("body", {}).get("memo")]
    r.note("C2-20b", "Distinct recipients / transfers with numeric memo (exchange deposit tag pattern)",
           f"{len({m['to_address'] for m, _ in sends})} / {sum(1 for m, x in sends if x['tx']['body']['memo'].isdigit())}")
    for m, x in sends:
        r.ev(f"DYDX {micro(m['amount'][0]['amount'],18):,.0f} -> {m['to_address']} memo '{x['tx']['body']['memo']}'", x["txhash"])


def c_ethereum(r: Report):
    total = Decimal(0)
    for h in (ETH_500, ETH_170, ETH_94):
        t = ethereum("eth_getTransactionByHash", [h])
        assert t["from"].lower() == ETH_WORK and t["to"].lower() == ETH_COLLECT
        total += Decimal(int(t["value"], 16)) / Decimal(10**18)
        r.ev(f"ETH {Decimal(int(t['value'], 16)) / Decimal(10**18)} working wallet -> collection wallet", h)
    r.claim("C2-21", "ETH sent from working wallet to collection wallet (500 + 170 + 94.4)", D("764.4"), total,
            evidence=[ETH_500, ETH_170, ETH_94])
    bal = Decimal(int(ethereum("eth_getBalance", [ETH_COLLECT, "latest"]), 16)) / Decimal(10**18)
    nonce = int(ethereum("eth_getTransactionCount", [ETH_COLLECT, "latest"]), 16)
    r.claim("C2-21b", "Collection wallet balance (ETH) at fetch time", D("794.05"), bal, tol=D("0.01"))
    r.claim("C2-21c", "Collection wallet has never sent a transaction (nonce)", 0, nonce)
    r.ev("Ethereum working wallet", ETH_WORK)
    r.ev("Ethereum collection wallet", ETH_COLLECT)


def c_prop1056(r: Report):
    p = HUB.get("/cosmos/gov/v1/proposals/1056", valid=lambda x: "proposal" in x)["proposal"]
    t = {k: micro(v) for k, v in p["final_tally_result"].items()}
    veto = t["no_with_veto_count"] / sum(t.values())
    r.claim("C2-22", "Hub proposal 1056 (refund + 500k ATOM bounty to YES voters) rejected, NoWithVeto share",
            D("89.7"), round(veto * 100, 1), evidence=["cosmoshub gov proposal 1056"])
    r.claim("C2-22b", "Proposal 1056 submitted by the fresh key that sold the THORChain refund",
            "cosmos1erq7tre6nk0jfx203z8ey75g4m7yfrckh2nk3v", p["proposer"])
    r.ev("fresh key (Cosmos Hub) - proposer of 1056", p["proposer"])


def main():
    r = Report("case02", "Case 02 — Neutron governance takeover")
    for k, v in {"attacker wallet (Neutron)": ATTACKER, "attacker wallet (Cosmos Hub)": ATT_HUB,
                 "attacker wallet (Noble)": ATT_NOBLE, "attacker wallet (dYdX)": ATT_DYDX,
                 "voting wallet (Neutron)": VOTER, "voting wallet (Cosmos Hub)": VOTER_HUB,
                 "voting wallet (Noble)": VOTER_NOBLE}.items():
        r.ev(k, v)
    for fn in (c_proposal, c_tally, c_purchase, c_link, c_drain, c_noble_cctp, c_hub, c_halts, c_dydx,
               c_ethereum, c_prop1056):
        r.run(fn)
    return r.write()


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
