"""Case 03 — Chainflip Tron vault: extra refunds via attacker-submitted fetches with a memo.

Every number in this folder's README.md is re-derived here from raw TronGrid, THORNode,
mempool.space, Ethereum RPC and Chainflip State Chain RPC responses.

Run:  python cases/03-chainflip-tron-duplicate-payouts/checks.py            (TRONGRID_API_KEY optional, raises rate limits)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                       # repository root, for `tools` / `risk`
os.environ.setdefault("CIP_CACHE", str(HERE / "data" / "cache"))  # this case's raw-data snapshot

import itertools
from decimal import Decimal

from tools.claims import Report, D
from tools import chainflip, tron
from tools.net import ethereum

# --- addresses ----------------------------------------------------------------------------
VAULT = "TEcDijvKSXcfWT7S6rd44H5vNgufm7Y4XC"          # Chainflip Tron Vault (docs: mainnet addresses)
ATTACKER = "TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ"       # B
TC_VAULT = "TLGFEbHhDS1wHYX4SQwHhdukPKZYtJ4xzt"       # THORChain Tron vault used for the exit (H)
TC_VAULT_USDT_OUT = "TDGbEeTP6QQ1iCJ6twP5FNCDrbHTBme44f"  # THORChain Tron vault that paid the funding USDT
TC_VAULT_TRX_OUT = "TMKfq5gixvpSavgqXhe4yfAbnAzW1a1UeL"   # THORChain Tron vault that paid the funding TRX
ETH_FUNDER = "0x9c7a63fadc892df1236f959f76cd0f686de14697"
BTC_DEST = "bc1qjqda2hp3yajkkm74t8j9rz7ljghfp8akyyqv55"
BTC_LOOP = "bc1quufu2t6pzgzg66wqsat4vjsh9llddda96hweys"
BTC_NEXT = {"bc1q6lmjljevzrtjrpjjn9y2p4laegpr26zvztdegd": Decimal("7.5450169"),
            "bc1q8w445lug39qj4fd9n84cmu8nccl8jthfmvuve6": Decimal("2.1")}
CHANNELS = [  # deposit channels the attacker used, in order
    "TBuFHA6cxBKRuE7QcdkzqYyWhtSM6gXnCZ", "TRQ88sGrerfrPgHiQQgWqBUSjsqb11gdxm",
    "TLQ3YSviESxx3nim9dhcvFrs6Gyn8zKfu2", "TPMHrJf1qiXVAnWZpa3FeDaFYg7uSmrySv",
    "TWDWWXZv74W33PYXPiZqkjYcKdwj3aKPSU", "TCKv1KpizuUfrQFr8pzwPtQRtrQBaBEVF3",
    "TKDcouiTiqwV7uEkuvwm3Y1PdBBW8AUQVB", "TT2fLntae72J9Kkw24je7VLSecFwFT4U3P"]
FALSE_LEAD_ENDPOINTS = {"TMxnc434PYthRnaBxEA494xrk7iyufrAZP": "I", "TCrb6pVQ4BSBhZtNLYuba5RSJjudpptTiE": "J"}

# --- transactions -------------------------------------------------------------------------
TX_FUND_USDT = "4d6ef5350dbdd4ac550761634bd584e3ee9b51856a426c09a7f99b34967f4bc8"
TX_FUND_TRX = "f558f1ed8c7f90029058776cadfb875158e171ebf6ea10d0fbdb5f1549422e7e"
TX_EXIT = "1060f5bbdc3ef776d156e0b18e46bc5ea31a1907e7b4e16dd8c89073db7be52a"
TX_LOOP_IN = "019f5e4694fb52fdf01e4fd76a140ef3c9391a49d97ecb94b1cf5cf38cedecdc"
TX_LOOP_OUT = "2740a19dff0193d94d78686a262211576a4940895bf8c74e482265a3306b8b10"
BTC_TX_SPLIT = "84a884899f09e7b63e26d79f2d5c0f4edfe713cb5d6689de2690fda5b9f65b32"
BTC_TX_CONSOLIDATE = "e473cc08d6b722603211e9efe86260a63878cfdbd80986dbc366dacc2998d5c1"

WINDOW = ("2026-09-12T00:00", "2026-09-12T12:00")
REPORTED_LOSS = Decimal("736442.17")
SELECTOR_FETCH = "5f8c0f9a"   # Vault function called by every channel -> vault forward
ATT_HEX20 = tron.to_hex(ATTACKER)[2:]

R = Report(HERE, "Case 03 — Chainflip Tron duplicate payouts")
_cache: dict = {}


def att_rows():
    if "att" not in _cache:
        _cache["att"] = tron.trc20(ATTACKER)
    return _cache["att"]


def deposits():
    """Attacker -> deposit channel transfers, in time order."""
    return [r for r in att_rows() if r["from"] == ATTACKER and r["to"] in CHANNELS]


def payouts():
    return [r for r in att_rows() if r["from"] == VAULT and r["to"] == ATTACKER]


def forwards():
    """Channel -> Vault forwards of the attacker's deposits (one per channel in the window)."""
    out = {}
    for ch in CHANNELS:
        rows = [r for r in tron.trc20(ch, start=WINDOW[0], end=WINDOW[1]) if r["to"] == VAULT]
        out[ch] = rows
    return out


def c_vault_outflows(r: Report):
    rows = [x for x in tron.trc20(VAULT, start=WINDOW[0], end=WINDOW[1]) if x["from"] == VAULT and x["to"] == ATTACKER]
    total = sum(tron.amount(x) for x in rows)
    r.claim("C3-01", "Vault paid the attacker address 14 times on 12 Sep, total 1,861,409.334334 USDT",
            (14, Decimal("1861409.334334")), (len(rows), total), evidence=[VAULT, ATTACKER])
    r.ev("Chainflip Tron Vault", VAULT)
    r.ev("attacker address (B)", ATTACKER)
    vals = [tron.amount(x) for x in rows]
    hits = [c for k in range(1, len(vals) + 1) for c in itertools.combinations(range(len(vals)), k)
            if abs(sum(vals[i] for i in c) - REPORTED_LOSS) <= D("0.01")]
    r.claim("C3-02", "Exactly one subset of those payouts sums to the reported loss 736,442.17 (±0.01)",
            (1, 6), (len(hits), len(hits[0]) if hits else 0))
    _cache["loss_subset"] = {rows[i]["transaction_id"] for i in hits[0]} if hits else set()


def c_funding(r: Report):
    first = att_rows()[0]
    r.claim("C3-03", "First USDT ever received by B: 13,260.80 from THORChain Tron vault at 00:49:42",
            (TC_VAULT_USDT_OUT, Decimal("13260.798955"), "2026-09-12 00:49:42"),
            (first["from"], tron.amount(first), tron.iso(first["block_timestamp"])),
            evidence=[TX_FUND_USDT])
    memo = tron.call_summary(TX_FUND_USDT)["note"]
    inb = memo.split(":")[1]
    st = tron.thornode_tx(inb)
    r.claim("C3-04", "Funding USDT = THORChain swap of 5.3 ETH from the Ethereum funder, destination B",
            ("ETH", ETH_FUNDER, Decimal("5.3"), True),
            (st["tx"]["chain"], st["tx"]["from_address"].lower(), D(st["tx"]["coins"][0]["amount"]) / D(10**8),
             ATTACKER in st["tx"]["memo"]), evidence=[TX_FUND_USDT, inb, ETH_FUNDER])
    r.ev("THORChain inbound (ETH→TRON.USDT)", inb)
    r.ev("Ethereum funder", ETH_FUNDER)
    trx = tron.call_summary(TX_FUND_TRX)
    st2 = tron.thornode_tx(trx["note"].split(":")[1])
    r.claim("C3-05", "Gas money: 1,105.34675 TRX via THORChain from the same ETH funder (0.15 ETH)",
            (TC_VAULT_TRX_OUT, Decimal("1105.34675"), ETH_FUNDER, Decimal("0.15")),
            (trx["signer"], D(trx["amount_sun"]) / D(10**6), st2["tx"]["from_address"].lower(),
             D(st2["tx"]["coins"][0]["amount"]) / D(10**8)), evidence=[TX_FUND_TRX, trx["note"].split(":")[1]])
    r.ev("THORChain inbound (ETH→TRON.TRX)", trx["note"].split(":")[1])
    acct = tron.account(ATTACKER)
    r.claim("C3-06", "B was activated after it had already received the funding USDT (fresh address)",
            True, acct.get("create_time", 0) > first["block_timestamp"],
            evidence=[ATTACKER])
    nonce = int(ethereum("eth_getTransactionCount", [ETH_FUNDER, "latest"]), 16)
    r.note("C3-07", "Ethereum funder: outgoing tx count (nonce) at fetch time", nonce, evidence=[ETH_FUNDER])


def c_channels(r: Report):
    deps = deposits()
    r.claim("C3-08", "Attacker made 8 deposits, one per deposit channel, in this order",
            CHANNELS, [d["to"] for d in deps], evidence=[d["transaction_id"] for d in deps])
    amounts = [tron.amount(d) for d in deps]
    r.claim("C3-09", "Deposit sizes (exact, USDT)",
            [D("13000"), D("13000"), D("26240.18962"), D("52467.901204"), D("104923.841453"),
             D("209835.650339"), D("375563.327997"), D("330000")], amounts)
    bal, whole = D(0), []
    for x in att_rows():
        if x["from"] == ATTACKER and x["to"] in CHANNELS:
            whole.append(tron.amount(x) == bal)
        bal += tron.amount(x) if x["to"] == ATTACKER else -tron.amount(x)
    r.claim("C3-09b", "Rounds 3–6 re-deposit B's entire USDT balance to the micro-unit (doubling loop)",
            [False, False, True, True, True, True, False, False], whole)
    creators = {ch: tron.contract_creator(ch) for ch in CHANNELS}
    r.claim("C3-10", "All 8 deposit channels are contracts created by the Chainflip Vault",
            8, sum(1 for c in creators.values() if c == VAULT), evidence=CHANNELS)
    fw = forwards()
    ok = 0
    for d in deps:
        f = fw[d["to"]]
        if len(f) == 1 and f[0]["value"] == d["value"] and 0 < f[0]["block_timestamp"] - d["block_timestamp"] <= 300_000:
            ok += 1
    r.claim("C3-11", "Each channel forwarded exactly the deposited amount to the Vault within 5 min",
            8, ok, evidence=[f[0]["transaction_id"] for f in fw.values() if f])
    for i, ch in enumerate(CHANNELS, 1):
        r.ev(f"deposit channel {i}", ch)


def c_mechanism(r: Report):
    deps, pays, fw = deposits(), payouts(), forwards()
    signed_by_attacker, with_note = [], []
    for d in deps:
        f = fw[d["to"]][0]
        s = tron.call_summary(f["transaction_id"])
        assert s["contract"] == VAULT and s["selector"] == SELECTOR_FETCH, s
        signed_by_attacker.append(s["signer"] == ATTACKER)
        with_note.append(bool(s["note_hex"]) and ATT_HEX20 in s["note_hex"])
        r.ev(f"fetch {d['to'][:6]} (signer {s['signer'][:6]})", f["transaction_id"])
    r.claim("C3-12", "The attacker itself submitted 6 of the 8 fetch calls (Vault selector 0x5f8c0f9a)",
            [False, True, True, True, True, True, False, True], signed_by_attacker)
    r.claim("C3-13", "Exactly those 6 fetch calls carry a note encoding the attacker's address",
            signed_by_attacker, with_note)
    # payouts between deposit i and deposit i+1 belong to deposit i
    times = [d["block_timestamp"] for d in deps] + [10**15]
    per = [[p for p in pays if times[i] < p["block_timestamp"] < times[i + 1]] for i in range(len(deps))]
    counts = [len(x) for x in per]
    r.claim("C3-14", "Payouts per deposit: two for every attacker-submitted fetch, one otherwise",
            [2 if s else 1 for s in signed_by_attacker], counts)
    r.claim("C3-15", "8 attempts, 6 successful (matches Chainflip's statement)",
            (8, 6), (len(deps), sum(1 for c in counts if c == 2)))
    firsts = [x[0] for x in per if len(x) == 2]
    extra = sum(tron.amount(p) for p in firsts)
    r.claim("C3-16", "The reported loss is exactly the FIRST payout of each doubled pair (the extra refund)",
            (REPORTED_LOSS, True), (extra.quantize(D("0.01")), {p["transaction_id"] for p in firsts} == _cache.get("loss_subset")),
            evidence=[p["transaction_id"] for p in firsts])
    paid = sum(tron.amount(p) for p in pays if p["block_timestamp"] < times[-2] + 3_600_000)
    dep = sum(tron.amount(d) for d in deps)
    r.note("C3-17", "Attacker net gain from the loop (payouts − deposits; the gap to the loss is ingress/egress fees)",
           f"{paid - dep:,.6f} USDT")
    _cache["net"] = paid - dep


def c_exit(r: Report):
    s = tron.call_summary(TX_EXIT)
    st = tron.thornode_tx(TX_EXIT)
    out = st["out_txs"][0]
    r.claim("C3-18", "Exit: 749,000 USDT to THORChain with memo swap → BTC to bc1qjqda…",
            (TC_VAULT, D("749000"), BTC_DEST), (st["tx"]["to_address"], D(st["tx"]["coins"][0]["amount"]) / D(10**8),
                                                 s["note"].split(":")[2]), evidence=[TX_EXIT])
    btx = tron.btc_tx(out["id"].lower())
    got = sum(D(o["value"]) for o in btx["vout"] if o.get("scriptpubkey_address") == BTC_DEST) / D(10**8)
    r.claim("C3-19", "THORChain paid 9.64358613 BTC to bc1qjqda… (confirmed in the Bitcoin tx)",
            (D("9.64358613"), D("9.64358613")), (D(out["coins"][0]["amount"]) / D(10**8), got),
            evidence=[out["id"].lower(), BTC_DEST])
    r.ev("exit tx (TRON → THORChain)", TX_EXIT)
    r.ev("THORChain BTC outbound #1", out["id"].lower())
    r.ev("BTC destination", BTC_DEST)
    bal = D("13260.798955") + _cache["net"] - D("749000")
    r.claim("C3-20", "B kept ≈639.22 USDT after the exit (funding + net gain − 749,000)",
            D("639.22"), bal.quantize(D("0.01")))


def c_loop(r: Report):
    split = tron.btc_tx(BTC_TX_SPLIT)
    to_loop = sum(D(o["value"]) for o in split["vout"] if o.get("scriptpubkey_address") == BTC_LOOP) / D(10**8)
    r.claim("C3-21", "bc1qjqda… sent 0.6 BTC to bc1quufu… 14 min after receiving the exit BTC",
            (BTC_DEST, D("0.6")), (split["vin"][0]["prevout"]["scriptpubkey_address"], to_loop),
            evidence=[BTC_TX_SPLIT])
    s_in = tron.call_summary(TX_LOOP_IN)
    st_in = tron.thornode_tx(s_in["note"].split(":")[1])
    r.claim("C3-22", "bc1quufu… swapped 0.599 BTC back to 46,102.64 USDT paid to B",
            ("BTC", BTC_LOOP, D("0.599"), D("46102.638994")),
            (st_in["tx"]["chain"], st_in["tx"]["from_address"], D(st_in["tx"]["coins"][0]["amount"]) / D(10**8),
             D(st_in["out_txs"][0]["coins"][0]["amount"]) / D(10**8)), evidence=[TX_LOOP_IN, st_in["tx"]["id"]])
    st_out = tron.thornode_tx(TX_LOOP_OUT)
    r.claim("C3-23", "B then swapped 46,740 USDT (its whole balance) back to 0.60153218 BTC to bc1qjqda…",
            (D("46740"), BTC_DEST, D("0.60153218")),
            (D(st_out["tx"]["coins"][0]["amount"]) / D(10**8), st_out["out_txs"][0]["to_address"],
             D(st_out["out_txs"][0]["coins"][0]["amount"]) / D(10**8)), evidence=[TX_LOOP_OUT, st_out["out_txs"][0]["id"].lower()])
    left = sum(tron.amount(x) if x["to"] == ATTACKER else -tron.amount(x) for x in att_rows())
    r.claim("C3-24", "USDT left on B after everything ≈ 1.86", D("1.86"), left.quantize(D("0.01")))
    cons = tron.btc_tx(BTC_TX_CONSOLIDATE)
    ins = sorted((i["prevout"]["scriptpubkey_address"], D(i["prevout"]["value"]) / D(10**8)) for i in cons["vin"])
    outs = sorted((o["scriptpubkey_address"], D(o["value"]) / D(10**8)) for o in cons["vout"])
    r.claim("C3-25", "14 Sep: both BTC outputs consolidated and split 7.5450169 / 2.1 BTC",
            ([(BTC_DEST, D("0.60153218")), (BTC_DEST, D("9.04358472"))], sorted(BTC_NEXT.items())), (ins, outs),
            evidence=[BTC_TX_CONSOLIDATE] + list(BTC_NEXT))
    for a in BTC_NEXT:
        r.ev("BTC next hop", a)
    r.ev("BTC loop address", BTC_LOOP)


def c_false_lead(r: Report):
    """H is a THORChain vault: its other outflows are other users' swaps, not the attacker's."""
    rows = [x for x in tron.trc20(TC_VAULT, start="2026-09-12T03:13", end="2026-09-12T12:00")
            if x["from"] == TC_VAULT and x["to"] in FALSE_LEAD_ENDPOINTS]
    foreign = 0
    for x in rows:
        memo = tron.call_summary(x["transaction_id"])["note"] or ""
        if memo.startswith("OUT:"):
            src = tron.thornode_tx(memo.split(":")[1])["tx"]
            if ATTACKER not in (src.get("from_address"), src.get("to_address")) and ATTACKER not in src.get("memo", ""):
                foreign += 1
    r.claim("C3-26", "Every H → I/J payout on 12 Sep is a THORChain outbound for someone else's swap",
            len(rows), foreign, evidence=list(FALSE_LEAD_ENDPOINTS))
    h_in = [x for x in tron.trc20(TC_VAULT) if x["to"] == TC_VAULT]
    r.note("C3-27", "H (THORChain Tron vault): USDT inflows / distinct senders over its lifetime",
           f"{len(h_in)} / {len({x['from'] for x in h_in})}")


def c_status(r: Report):
    for label, a in [("B", ATTACKER), ("H", TC_VAULT)]:
        r.note(f"C3-28{label}", f"Tether freeze list: USDT.isBlackListed({label}) at fetch time",
               tron.usdt_blacklisted(a), evidence=[a])
    acct = tron.account(ATTACKER)
    r.note("C3-29", "TRX remaining on B at fetch time", f"{D(acct.get('balance', 0)) / D(10**6):,.6f} TRX")


# --- operator, funding and the signed payload (added after Chainflip's incident report) -------
LP_ACCOUNT = "cFMKZx5J8NkiJ6JxHatodMRumCnzvmVtF62FGWMnWcspg58bs"
STATE_CHAIN_GATEWAY = "0x6995ab7c4d7f4b03f467cf4c8e920427d9621dbd"   # Chainflip StateChainGateway (Ethereum)
FLIP_TOKEN = "0x826180541412d574cf1336d22c0c0a287822678a"
TX_LP_FUND = "0xc502d392ae07123430905b09fb879dd2f9acf6fb92d2ac58dd11e6c6a64c69e7"   # fundStateChainAccount
TORNADO_1ETH = "0x47ce0c6ed5b0ce3d3a51fdb1c52dc66a7c3c2936"
TOPIC_TORNADO_WITHDRAWAL = "0xe9e508bad6d4c3227e881ca19068f099da81b5164dd6d62b2eaf1e8bc6c34931"
TOPIC_ERC20_TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TX_TORNADO_TO_FUNDER = [
    "0x7318bdacbea1360a6ac07d2e58384a6756a040e5581a8cff995c44f079491b25",
    "0x4b42078e1d255cf97cf7dcf3d9eff83751affd4c46a1e211330dc1a34040395e",
    "0x85bd273c2e891b82c4b4edf19d5581b1b9f402bce450995390e81de0f16393e9",
    "0x3bf8dc53a02f45605831b3286e1e943ee6a1edc6457ae74c608dd3ec71d826ec",
    "0xf4a9282ae8a710118deb8352a17f1c2572dc934d5702f5317383e19073c68367"]
ETH_RELAY = "0x9732b5296711e24bdbd1f7538c6561617478d8da"
TX_TORNADO_TO_RELAY = "0x60a4786f33839565be42c7a6b4cffc59650f16ea264c58c77c22c9d894fec548"
TX_RELAY_TO_FUNDER = "0xd7b474e05424a8909aaf967e463ca08a142e275203fe883ced0dacf8cb50c29f"
TX_THOR_ETH_IN = "0xae4f26ec5cda9d4d5711d80aa64dbbcd395442787a0c3e1f8001b290eac2326c"
ETH_FLIP_BUYER = "0x6985ef5b59f80107cd5ed94e58e299d0dd47d1d9"
TX_FLIP_BUY = "0x1943a16d2589266987b22537abeb7edba6dabe6beaadf7c5671139d4591b3451"
TX_FLIP_TO_FUNDER = "0xc3cec64d8af4c6621c402606afb0e7f98e985a236428759e9cb7acbe27c9ea5f"
TX_FLIP_BUYER_FUNDED = "0x41261f3b3173f1ce99a43cc8200de0866688c4667cda6bceba1fa17b44943931"


def eth_tx(h):
    return ethereum("eth_getTransactionByHash", [h])


def eth_receipt(h):
    return ethereum("eth_getTransactionReceipt", [h])


def eth_time(block_hex: str) -> str:
    b = ethereum("eth_getBlockByNumber", [block_hex, False])
    return tron.iso(int(b["timestamp"], 16) * 1000)


def tornado_recipient(h):
    """(recipient, net ETH) from the Withdrawal event of the 1 ETH Tornado Cash pool in tx h."""
    for log in eth_receipt(h)["logs"]:
        if log["address"].lower() == TORNADO_1ETH and log["topics"][0] == TOPIC_TORNADO_WITHDRAWAL:
            w = [log["data"][2 + 64 * k: 2 + 64 * (k + 1)] for k in range(3)]
            return "0x" + w[0][24:], (D(10**18) - int(w[2], 16)) / D(10**18)
    return None, D(0)


def c_payload(r: Report):
    deps, fw = deposits(), forwards()
    notes, batches = [], []
    for d in deps:
        f = fw[d["to"]][0]
        s = tron.call_summary(f["transaction_id"])
        b = chainflip.all_batch(tron.tx(f["transaction_id"])["raw_data"]["contract"][0]["parameter"]["value"]["data"])
        batches.append((s["result"], b["nonce"]))
        if s["note_hex"]:
            n = chainflip.vault_swap_note(s["note_hex"])
            notes.append((n["output_asset"], n["output_chain"], tron.to_base58(n["destination"]),
                          tron.to_base58(n["refund_address"])))
    r.claim("C3-30", "Each of the 6 notes is a vault swap USDT(Tron) → USDT(Tron) to B with refund address B",
            [("TrxUsdt", "Tron", ATTACKER, ATTACKER)] * 6, notes)
    r.claim("C3-31", "All 8 fetches are Vault allBatch calls that executed successfully (signature accepted)",
            ["SUCCESS"] * 8, [x[0] for x in batches])
    r.note("C3-31b", "Key-manager nonces inside the 8 signed allBatch payloads (rounds 1-8)", [x[1] for x in batches])


def c_operator(r: Report):
    t, rc = eth_tx(TX_LP_FUND), eth_receipt(TX_LP_FUND)
    node_id = t["input"][10:74]
    flip = D(int(t["input"][74:138], 16)) / D(10**18)
    when = eth_time(t["blockNumber"])
    r.claim("C3-32", "The Ethereum funder registered Chainflip State Chain account cFMKZx5… with 100 FLIP at 01:25:11, "
                     "19 min before the first deposit",
            (ETH_FUNDER, STATE_CHAIN_GATEWAY, "0x1", LP_ACCOUNT, D(100), "2026-09-12 01:25:11", True),
            (t["from"].lower(), t["to"].lower(), rc["status"], chainflip.ss58(node_id), flip, when,
             when < tron.iso(deposits()[0]["block_timestamp"])), evidence=[TX_LP_FUND, LP_ACCOUNT])
    acct = chainflip.rpc("cf_account_info", [LP_ACCOUNT])
    r.claim("C3-33", "That account is a liquidity provider whose Tron refund address is B (State Chain, at fetch time)",
            ("liquidity_provider", ATTACKER), (acct["role"], acct["refund_addresses"]["Tron"]), evidence=[LP_ACCOUNT])
    r.ev("Chainflip LP account of the attacker", LP_ACCOUNT)
    r.ev("fundStateChainAccount tx", TX_LP_FUND)
    # the 100 FLIP came from a second wallet that bought them on Uniswap a minute earlier
    buy = eth_receipt(TX_FLIP_BUY)
    bought = sum(D(int(lg["data"], 16)) for lg in buy["logs"] if lg["address"].lower() == FLIP_TOKEN
                 and lg["topics"][0] == TOPIC_ERC20_TRANSFER and lg["topics"][2][-40:] == ETH_FLIP_BUYER[2:]) / D(10**18)
    send = eth_tx(TX_FLIP_TO_FUNDER)
    to, amt = "0x" + send["input"][34:74], D(int(send["input"][74:138], 16)) / D(10**18)
    r.claim("C3-34", "The FLIP came from 0x6985…: bought 675.5556 FLIP for 0.1 ETH, sent all of it to the funder",
            (D("675.555617107256356994"), D("0.1"), ETH_FUNDER, D("675.555617107256356994")),
            (bought, D(int(eth_tx(TX_FLIP_BUY)["value"], 16)) / D(10**18), to.lower(), amt),
            evidence=[TX_FLIP_BUY, TX_FLIP_TO_FUNDER, ETH_FLIP_BUYER])
    fund = eth_tx(TX_FLIP_BUYER_FUNDED)
    r.note("C3-34b", "0x6985… was first funded on 7 Sep (sender, ETH)",
           f"{fund['from']} {D(int(fund['value'], 16)) / D(10**18):.6f}", evidence=[TX_FLIP_BUYER_FUNDED])
    r.ev("FLIP buyer (second Ethereum wallet)", ETH_FLIP_BUYER)


def c_tornado(r: Report):
    rows = [tornado_recipient(h) for h in TX_TORNADO_TO_FUNDER]
    times = [eth_time(eth_tx(h)["blockNumber"]) for h in TX_TORNADO_TO_FUNDER]
    first_out = eth_time(eth_tx(TX_THOR_ETH_IN)["blockNumber"])
    total = sum(x[1] for x in rows)
    r.claim("C3-35", "5 Tornado Cash (1 ETH pool) withdrawals paid the funder 4.97493 ETH, all before its first THORChain deposit",
            ([ETH_FUNDER] * 5, D("4.974933"), True),
            ([x[0] for x in rows], total.quantize(D("0.000001")), max(times) < first_out),
            evidence=TX_TORNADO_TO_FUNDER + [TORNADO_1ETH])
    rec, net = tornado_recipient(TX_TORNADO_TO_RELAY)
    hop = eth_tx(TX_RELAY_TO_FUNDER)
    r.claim("C3-36", "A sixth withdrawal went to 0x9732… on 11 Sep, which forwarded 0.99464 ETH to the funder",
            (ETH_RELAY, ETH_RELAY, ETH_FUNDER, D("0.994643")),
            (rec, hop["from"].lower(), hop["to"].lower(), (D(int(hop["value"], 16)) / D(10**18)).quantize(D("0.000001"))),
            evidence=[TX_TORNADO_TO_RELAY, TX_RELAY_TO_FUNDER, ETH_RELAY])
    r.ev("Tornado Cash 1 ETH pool", TORNADO_1ETH)
    for h in TX_TORNADO_TO_FUNDER + [TX_TORNADO_TO_RELAY]:
        r.ev("Tornado withdrawal", h)


# --- Bitcoin beyond 14 Sep -------------------------------------------------------------------
BTC_BRANCH_754 = "bc1qj4y8adm3h2jxfzzyxldcr05num3spkap9g5vve"
BTC_TX_754_SPLIT = "4230f0b91a30e0b2c792c554abd255b39c3f8fe69d4f5f7a944e5bc612a17056"
BTC_6 = "bc1q06a6qk8s3px4smw6vzp0x36y99yx956p75hyyd5xjqc2kc9p7rjq3pxk2e"
BTC_154 = "bc1qvl9nz6yl6kjcyukq9cc92h8wsmmq6v9y6guk87"
BTC_CHAIN_21 = [  # (tx, address it pays) : single-input, single-output hops of the 2.1 BTC branch
    ("61da18cc9e17ad1e35571f92ce7802cd4e26aceed1fc823a43a29881c3cfc897", "bc1qnglu5q7gjm4z62fj333k5qjgcduqfep4p85q3rf59ckvqx7r6xasatqmdk"),
    ("f7189b0d89dcf7099b0e0dd079b49dbe6c1c4d7d443a03559c8e387d0185bd80", "bc1qnzl7q4vqe5vl9d2xsgna9dwtw4me6pm9n6wsm2"),
    ("fe3290bba67d83f756f434793ea7e39ad5a497c31c7fdc6da16fdb818698003f", "bc1qxg00706w5xmv7v73uxjm9wgpqn3znnk6fu5ggf"),
    ("20c15e4fde26bf28bb79e3f7d68e6ef3fd14ff03963b77747edef060f91faa20", "bc1qferte8zyhltagg6u0k47kp0sagck3d24glq2ne"),
    ("f8012f3c42a4027d4087e04847e9f46c6d308f7d2b0629c568b62678d88e5dbf", "bc1q3taf77uw57eaarephnxzryelc0dslz3tpdky25")]
BTC_SERVICE = "bc1q3taf77uw57eaarephnxzryelc0dslz3tpdky25"
BTC_TX_6_ON = "e7a8b4f283f8efba45d7ec822c8a7aedd4423c42c2857f2c2b6cba9fa2b0b215"     # 6.0 -> bc1qv8crc…
BTC_TX_154_ON = ["02886db3831fec3cbcda831190736fcef8b0302683a5ff70e0c23a4336cac450",   # 1.54 -> bc1q9xuu…
                 "e481aae4bc34b175ffd70ad06b4d700eb7b6397afb516ccab9cc221921784de2"]   # -> bc1qz9fr9…
BTC_COSPEND = "64bd2970d6d3d0e25a2b0a6697f4fba310a317948e2356dfe1d13128798f1a5a"
BTC_V8 = "bc1qv8crcwcjgmmc5t5anz32a5tl9v6p54ayrzxhuj"
BTC_Z9 = "bc1qz9fr9nvqrkjs5gg22tms6hfzw4w5ckg8k0wjn9"


def _outs(t):
    return [(o.get("scriptpubkey_address"), D(o["value"]) / D(10**8)) for o in t["vout"] if o["value"]]


def c_btc_onward(r: Report):
    split = tron.btc_tx(BTC_TX_754_SPLIT)
    r.claim("C3-37", "The 7.54 BTC branch splits into 6.0 and 1.53999 BTC (14 Sep 15:02)",
            (BTC_BRANCH_754, [(BTC_6, D("6")), (BTC_154, D("1.53999"))]),
            (split["vin"][0]["prevout"]["scriptpubkey_address"], _outs(split)), evidence=[BTC_TX_754_SPLIT])
    hops, prev = [], "bc1q8w445lug39qj4fd9n84cmu8nccl8jthfmvuve6"
    for txid, dest in BTC_CHAIN_21:
        t = tron.btc_tx(txid)
        o = _outs(t)
        hops.append(len(t["vin"]) == 1 and t["vin"][0]["prevout"]["scriptpubkey_address"] == prev
                    and len(o) == 1 and o[0][0] == dest)
        prev = dest
    last = _outs(tron.btc_tx(BTC_CHAIN_21[-1][0]))[0]
    r.claim("C3-38", "The 2.1 BTC branch moves through 5 single-input, single-output txs (4 intermediate addresses) into bc1q3taf77… (15 Sep 01:11)",
            ([True] * 5, (BTC_SERVICE, D("2.09996828"))), (hops, last), evidence=[t for t, _ in BTC_CHAIN_21])
    st = tron.btc(f"/address/{BTC_SERVICE}")["chain_stats"]
    r.note("C3-39", "bc1q3taf77…: transactions / BTC received over its lifetime at fetch time (service-like volume)",
           f"{st['tx_count']} / {D(st['funded_txo_sum']) / D(10**8):,.8f}", evidence=[BTC_SERVICE])
    # common-input heuristic: one wallet spends UTXOs from both sub-branches of the 7.54 BTC branch
    six = tron.btc_tx(BTC_TX_6_ON)
    a, b = tron.btc_tx(BTC_TX_154_ON[0]), tron.btc_tx(BTC_TX_154_ON[1])
    linked = (six["vin"][0]["txid"] == BTC_TX_754_SPLIT and _outs(six)[0][0] == BTC_V8
              and a["vin"][0]["txid"] == BTC_TX_754_SPLIT and b["vin"][0]["txid"] == BTC_TX_154_ON[0]
              and _outs(b)[0][0] == BTC_Z9)
    co = tron.btc_tx(BTC_COSPEND)
    ins = {i["prevout"]["scriptpubkey_address"] for i in co["vin"]}
    r.claim("C3-40", "27 Oct: one transaction spends inputs on both sub-branches (bc1qv8crc… from the 6.0, bc1qz9fr9… from the 1.54)",
            (True, True, len(co["vin"])), (linked, {BTC_V8, BTC_Z9} <= ins, 6), evidence=[BTC_COSPEND, BTC_V8, BTC_Z9])
    for x in (BTC_BRANCH_754, BTC_SERVICE, BTC_V8, BTC_Z9):
        r.ev("BTC trail", x)


if __name__ == "__main__":
    for fn in (c_vault_outflows, c_funding, c_channels, c_mechanism, c_payload, c_operator, c_tornado,
               c_exit, c_loop, c_btc_onward, c_false_lead, c_status):
        R.run(fn)
    raise SystemExit(0 if R.write() else 1)
