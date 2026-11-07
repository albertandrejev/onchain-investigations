"""Case 04 — Solana arbitrage bot "King": wallet drained by its own key, exit through Mayan to Ethereum.

Every number in this folder's README.md is re-derived here from raw Solana RPC, Ethereum RPC,
Blockscout, Mayan explorer API and Relay API responses.

Run:  python cases/04-solana-king-mev-bot-drain/checks.py
      (set SOLANA_RPC to a Helius or other keyed endpoint when refreshing: the bot's own
       transactions are version 1 and the public endpoint rate-limits the ~300 fetches)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                       # repository root, for `tools` / `risk`
os.environ.setdefault("CIP_CACHE", str(HERE / "data" / "cache"))  # this case's raw-data snapshot

import datetime as dt
from decimal import Decimal

from tools.claims import Report, D
from tools.net import solana, ethereum, cached, _http

# --- addresses ----------------------------------------------------------------------------
VICTIM = "7dGrdJRYtsNR8UYxZ3TnifXGjGc9eRYLq9sELwYpuuUu"     # King arbitrage bot wallet
A = "BHRayETPjvgg3BCr9H82V1D6NRwxu5v44JAaVuaod3jU"          # drainer: received everything, swapped stables to SOL
B = "Ddmy5oM8xtTs1EBC6eF2SZwQfBreewQpFgtUDm51Hkqj"          # forwarder: deposit account of a swap service, Mayan orders
C = "3UECQUbsLTAfYYtEf3kzvgpw2F5GTu9YFK9dMyokswMy"          # 500 SOL to Relay, blocked
G = "B2N8LwcUiXD6dCqdnPkyi1TMJQtroefGVLHjjRWrVvCc"          # 1 SOL to Relay: gas for the Ethereum address
E = "0xf2fbf0292215a597f85409e753a4fe4f191663c1"            # Ethereum destination of every Mayan and Relay order
RELAYER = "6XQTpahMTFf1Rq1MtzayMSCi2dr6ZE5YJdJpCZ5DuFTG"    # sole signer and fee payer of every B transaction
RELAY_SOL = "7uTT8Xi5RWXzy7h9XL244GRgEycDYDhLjr3ZyNdXi8pZ"  # Relay's Solana depository (received C's and G's SOL)
MAYAN_REFUNDER = "FRoK4LMVwQRrmC9h4YgYzSAB5KJtpGzQM4gKym1iTnae"  # signed the two Mayan refunds to B
SWIFT_DEST = "0xD78D199f8C402e7B5Cc2abE278dF0412400a3BAe"   # Mayan SwiftDest contract on Ethereum (paid E)
MAYAN = "mayan34VedncxdK2XobtvWFDXQASUTBXhUVzt2kKgny"
JUPITER = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
COMPUTE_BUDGET = "ComputeBudget111111111111111111111111111111"

MINTS = {
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": ("USDT", 6),
    "USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB": ("USD1", 6),
    "So11111111111111111111111111111111111111112": ("wSOL", 9),
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": ("whETH", 8),
}
SYM = {v[0]: k for k, v in MINTS.items()}
USDC_ETH = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT_ETH = "0xdac17f958d2ee523a2206206994597c13d831ec7"

# --- transactions -------------------------------------------------------------------------
THEFT = [  # the five transfers signed by the victim's key, in order
    "2sUAaakTAfQ1J1WdbkafEMemG9m96aHqvo887Ajix2i4Z4QoGtinPTh3QdtwGvzcjmHuChr6Mx7CVs7na7xhG65r",  # USDC
    "4AJoXUr3SMVqvXptuZUSPag4bSB8zKfSehL3Bg7bPZqhtGh81SRZ6jXUtbuioWrebXNJYArEM4TveNcYqsKKNDd4",  # USDT
    "3FskNQ4qbXSBoHgApgXKMqGDxRVsPxFj4u48kFYtYFDjP2QxzwFYroRCfohsAxbREf8F6unpXLDYVkZ7nNmcGRNP",  # USD1
    "5qKUfKnMqvs2QxF2vj1pTpJExMfgSd2b65fKnhvF77DmbPfhKgHAPhaGMF5L9nFpJQ61T9kfTrhnZCVJkaK2w78Z",  # wSOL
    "2tYN1nHbmrRqu8NfrGxKba7y9uxSzoCFfqiSs9JWGL1w6rzG2whWudkPdL9Ti15XmqvYn97LwgVRLVJ11kshj1uh",  # SOL
]
RELAY_GAS_TX = "4GDQEULcjo7oLBcdyvXHwAbgnZRMGsQGZp9mM9ND6ao1XuwU36v4sbSfGHXF75E8kqnvDkGv5n3zRAAkPi8rRCPE"
RELAY_GAS_OUT = "0x32c633f0a03510cd3d31f5ac4d27a18371132b759402df12001f69944a727391"
RELAY_BLOCKED_TX = "3ZhURdE35CPyJ5A7gVg46VAG1zA6Znay5yf3n3iPwYCTxwX3yTFaQNbgAeQ19J2aENR8pG86RD2RMBdBuiK4AcmD"
MAYAN_REFUNDS = ["YTcsboppzhewGQjLSwmJ8XpbkHCK68fSuWTVZQCPF5rBPkC6pQECMxMkGBEUMYqgz6XBQ2eqcvRbrCs9sYye7Tf",
                 "3FTataS3m4B2CtVXRWk8fii8SwRAHvZ2khybU4eSGrnQvKjWqydkrtaky6HaVW6ozmp6RzxGmF1uKSaWaS6Wjq5V"]
ESCROWS = {  # Mayan Swift source-state accounts of the three orders that were never fulfilled or refunded
    "Fj2PPeNbkfS1vagKj9XnwVxKRg2bztLmLqoGXVJrG2U6": Decimal("93996.659573"),
    "QLcnnbAjX6Db564MARQHG1yq3XPxHVf3hdDSQQYE9Z1": Decimal("94148.525771"),
    "Ff4uihAPMdPYuF1DgEzEjRaWnGaNpGjVWvcEAGMgBCU8": Decimal("44729.481555"),
}
THEFT_TS = 1793604770  # 2026-11-02 07:32:50 UTC, first theft transaction
THEFT_END = 1793604916  # 07:35:16 UTC, the fifth transfer
KING = "King7ki4SKMBPb3iupnQwTyjsq294jaXsgLmJo8cb7T"   # the bot's own program: every pre-theft transaction calls it
OPERATOR = "Ace7hXUYzheTYG6EAYEYec25Y6SXUfKvauavEGy3KRby"  # the bot's treasury: funded by the victim since 2 Jul 2026
DUST_ECHO = "42q8iZYDQVj8im4W9FKUd53Bqy7cG4NNMAT279RrCnTZpqiutWz5feddPtwrDkwoZz3Tb8hdfkUPYQ7qNYDTKYoN"
OPERATOR_MANUAL_TX = "3CTQRjxLmMwhP1uN3W7WvfJLBVKNZcbho9Ne8q1S6UMTCMM3gU3MHKpoRSWKSXyMDnfZZzSgNhJ6znAoppYqd7Dw"
OFFER_TX = "45N4TzDwdkihMMS3d2qU7G29HY8NYyHeQuvLa6rHSmaRqjD2eChQmpFFnieAon1ZXR1rAjYsVT4dKEtK4JFNZG5q"  # treasury -> A, memo with a bounty offer

R = Report(HERE, "Case 04 — Solana King bot drain")
_cache: dict = {}


# --- fetchers -----------------------------------------------------------------------------
def tx(sig: str) -> dict:
    """The bot's own transactions are version 1; the shared helper only accepts version 0."""
    return solana("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])


def sigs(address: str, limit: int = 1000, before: str | None = None) -> list[dict]:
    p = {"limit": limit}
    if before:
        p["before"] = before
    return solana("getSignaturesForAddress", [address, p]) or []


def history(address: str) -> list[dict]:
    """Every confirmed transaction of an address (one signature page, oldest first), decoded."""
    if address not in _cache:
        out = []
        for s in sigs(address):
            if s.get("err"):
                continue
            out.append(tx(s["signature"]))
        _cache[address] = sorted(out, key=lambda t: t["slot"])
    return _cache[address]


def rest(namespace: str, url: str):
    return cached(namespace, url, lambda: _http(url))


def mayan_order(sig: str) -> dict:
    return rest("mayan", f"https://explorer-api.mayan.finance/v3/swap/trx/{sig}")


def relay_request(h: str) -> dict:
    return (rest("relay", f"https://api.relay.link/requests/v2?hash={h}") or {}).get("requests", [{}])[0]


def account(address: str) -> dict:
    return (solana("getAccountInfo", [address, {"encoding": "jsonParsed"}]) or {}).get("value") or {}


def token_accounts(owner: str, mint: str | None = None) -> list[dict]:
    f = {"mint": mint} if mint else {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}
    return (solana("getTokenAccountsByOwner", [owner, f, {"encoding": "jsonParsed"}]) or {}).get("value", [])


# --- decoders -----------------------------------------------------------------------------
def when(t: dict) -> str:
    return dt.datetime.fromtimestamp(t["blockTime"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def keys(t: dict) -> list[str]:
    return [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]


def signers(t: dict) -> list[str]:
    return [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"] if k["signer"]]


def programs(t: dict) -> set[str]:
    out = {i.get("programId") for i in t["transaction"]["message"]["instructions"]}
    for inner in t["meta"].get("innerInstructions", []):
        out |= {i.get("programId") for i in inner["instructions"]}
    return out - {None}


def token_deltas(t: dict) -> dict[tuple[str, str], Decimal]:
    """{(owner, symbol): delta} over all mints in MINTS."""
    out: dict[tuple[str, str], Decimal] = {}
    pre = {b["accountIndex"]: b for b in t["meta"]["preTokenBalances"]}
    post = {b["accountIndex"]: b for b in t["meta"]["postTokenBalances"]}
    for i in set(pre) | set(post):
        b = post.get(i) or pre.get(i)
        if b["mint"] not in MINTS:
            continue
        sym, dec = MINTS[b["mint"]]
        d = (Decimal(post.get(i, {}).get("uiTokenAmount", {}).get("amount", "0"))
             - Decimal(pre.get(i, {}).get("uiTokenAmount", {}).get("amount", "0"))) / Decimal(10 ** dec)
        if d:
            k = (b["owner"], sym)
            out[k] = out.get(k, Decimal(0)) + d
    return out


def sol_delta(t: dict, address: str) -> Decimal:
    k = keys(t)
    if address not in k:
        return Decimal(0)
    i = k.index(address)
    return (Decimal(t["meta"]["postBalances"][i]) - Decimal(t["meta"]["preBalances"][i])) / Decimal(10 ** 9)


_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(s: str) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    out = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + out


_P = 2 ** 255 - 19
_D = (-121665 * pow(121666, _P - 2, _P)) % _P


def on_curve(address: str) -> bool:
    """True when the 32 bytes decompress to a point on ed25519, i.e. a key pair can exist for the address.
    Program-derived addresses are chosen off the curve, so nobody can hold their private key."""
    y = int.from_bytes(b58decode(address).rjust(32, b"\0"), "little") & ((1 << 255) - 1)
    if y >= _P:
        return False
    x2 = (y * y - 1) * pow((_D * y * y + 1) % _P, _P - 2, _P) % _P
    return x2 == 0 or pow(x2, (_P - 1) // 2, _P) == 1


def compute_budget(t: dict) -> tuple[int | None, int | None]:
    """(cu_limit, cu_price) set by the ComputeBudget instructions, None when absent."""
    limit = price = None
    for ins in t["transaction"]["message"]["instructions"]:
        if ins.get("programId") != COMPUTE_BUDGET or "data" not in ins:
            continue
        raw = b58decode(ins["data"])
        if raw[:1] == b"\x02":
            limit = int.from_bytes(raw[1:5], "little")
        elif raw[:1] == b"\x03":
            price = int.from_bytes(raw[1:9], "little")
    return limit, price


def plain_transfers_out(address: str) -> list[tuple[dict, str, Decimal]]:
    """System transfers signed by `address` (no DEX/bridge program): (tx, recipient, SOL)."""
    out = []
    for t in history(address):
        if programs(t) - {COMPUTE_BUDGET, "11111111111111111111111111111111"} or address not in signers(t):
            continue
        for k in keys(t):
            if k != address and (d := sol_delta(t, k)) > 0:
                out.append((t, k, d))
    return out


# --- checks -------------------------------------------------------------------------------
def c_theft(r: Report):
    txs = [tx(s) for s in THEFT]
    r.claim("C4-01", "All five theft transactions were signed by the victim's own key, 07:32:50 to 07:35:16 UTC on 2 Nov 2026",
            ([VICTIM] * 5, "2026-11-02 07:32:50", "2026-11-02 07:35:16"),
            ([s for t in txs for s in signers(t)], when(txs[0]), when(txs[-1])), evidence=THEFT)
    r.ev("victim: King bot wallet", VICTIM)
    r.ev("A: drainer", A)
    for s in THEFT:
        r.ev("theft tx", s)
    got = {}
    for t in txs:
        for (owner, sym), d in token_deltas(t).items():
            if owner == A:
                got[sym] = d
    got["SOL"] = sol_delta(txs[4], A)
    r.claim("C4-02", "Amounts moved to A: 359,094.73421 USDC, 69,868.765015 USDT, 7,173.929438 USD1, 4,264.570828 wSOL, 191.242413486 SOL",
            {"USDC": D("359094.73421"), "USDT": D("69868.765015"), "USD1": D("7173.929438"),
             "wSOL": D("4264.570828378"), "SOL": D("191.242413486")}, got, evidence=THEFT)
    dests = []
    for t in txs[:4]:
        for ins in t["transaction"]["message"]["instructions"]:
            p = ins.get("parsed") or {}
            if p.get("type") == "transferChecked":
                dests.append(p["info"]["destination"])
    wallets = [ins["parsed"]["info"]["wallet"] for t in txs[:4] for ins in t["transaction"]["message"]["instructions"]
               if (ins.get("parsed") or {}).get("type") == "create" and ins["parsed"]["info"]["account"] in dests]
    r.claim("C4-03", "The four token destinations are associated token accounts created in the same transactions for wallet A (programs used: associated-token, token, system; no other program, no delegate)",
            [A] * 4, wallets, evidence=dests)
    for d in dests:
        r.ev("A token account", d)
    victim_fp = [compute_budget(t) for t in txs]
    r.claim("C4-04", "Client fingerprint of the theft: compute-unit price 50,000 and no compute-unit limit on all five",
            [(None, 50000)] * 5, victim_fp, evidence=THEFT)
    page = sigs(VICTIM)
    pre = [x for x in page if x["blockTime"] < THEFT_TS]
    before = [tx(x["signature"]) for x in pre[:100]]
    fps = {compute_budget(t) for t in before}
    r.claim("C4-05", "The bot's own client never sets a compute budget: the 100 transactions it signed right before the theft (all calls to its program King7ki…) carry no ComputeBudget instruction, so the theft's fingerprint is foreign to it",
            (100, {(None, None)}, True, True),
            (len(before), fps, all(VICTIM in signers(t) for t in before), all(KING in programs(t) for t in before)),
            evidence=[t["transaction"]["signatures"][0] for t in before[:3]] + [KING])
    r.ev("King bot program", KING)
    last = dt.datetime.fromtimestamp(pre[0]["blockTime"], dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    r.claim("C4-06", "The bot stopped with the theft: its last program call was at 07:32:26, 24 seconds before the first transfer, and none of the 94 transactions after the theft calls the program",
            ("2026-11-02 07:32:26", True, 0),
            (last, KING in programs(before[0]), sum(1 for x in page if x["blockTime"] > THEFT_END and KING in programs(tx(x["signature"])))),
            evidence=[pre[0]["signature"]])
    post = [tx(x["signature"]) for x in page if x["blockTime"] > THEFT_END and not x.get("err")]
    mine = [t for t in post if VICTIM in signers(t)]
    kinds: dict[str, int] = {}
    closed = withdrawn = 0
    for t in mine:
        for ins in t["transaction"]["message"]["instructions"]:
            p = ins.get("parsed") or {}
            k = p.get("type") or ins.get("programId", "")[:8]
            kinds[k] = kinds.get(k, 0) + 1
            closed += p.get("type") == "closeAccount"
            withdrawn += p.get("type") == "withdrawFromNonce"
    to_op = sum(sol_delta(t, OPERATOR) for t in mine)
    r.claim("C4-06b", "After the theft the key was used to dismantle the bot: 88 transactions closed its token accounts (2 Nov 12:07 to 12:09) and withdrew its durable-nonce accounts (3 Nov 15:36 to 15:38); every lamport of rent, 7.94 SOL, went to the bot's treasury Ace7h…",
            (88, True, True, D("7.94")),
            (len(mine), closed > 1000, withdrawn > 1000, to_op.quantize(D("0.01"))),
            evidence=[mine[0]["transaction"]["signatures"][0], mine[-1]["transaction"]["signatures"][0], OPERATOR])
    r.note("C4-06c", "Token accounts closed and nonce accounts withdrawn by those transactions", (closed, withdrawn))
    r.ev("operator treasury (victim side)", OPERATOR)
    manual = compute_budget(tx(OPERATOR_MANUAL_TX))
    r.claim("C4-06d", "The operator's own hand-made transaction (0.0103 SOL to the treasury at 12:11) carries a third fingerprint, limit 562 and price 133,333,334, unlike both the bot and the thief",
            (562, 133333334), manual, evidence=[OPERATOR_MANUAL_TX])
    co = [t for t in mine if OPERATOR in signers(t)]
    r.claim("C4-06e", "Four of the clean-up transactions, at 12:38 on 2 Nov, carry two signatures: the treasury pays the fee and the victim's key authorises the token transfers and closures. One client held both keys",
            (4, {"2026-11-02 12:38"}, [[OPERATOR, VICTIM]] * 4),
            (len(co), {when(t)[:16] for t in co}, [signers(t) for t in co]), evidence=[t["transaction"]["signatures"][0] for t in co])
    frozen = [(a["pubkey"], a["account"]["data"]["parsed"]["info"]["mint"]) for a in token_accounts(VICTIM)
              if a["account"]["data"]["parsed"]["info"]["state"] == "frozen"]
    r.claim("C4-07", "The victim's three frozen token accounts hold unrelated tokens (none of the stolen mints): spam, not a freeze on the stolen funds",
            (3, False), (len(frozen), any(m in MINTS for _, m in frozen)), evidence=[a for a, _ in frozen])


def c_a_wallet(r: Report):
    h = history(A)
    r.claim("C4-08", "A was created by the first theft transaction: its oldest signature is that transfer (fresh address)",
            THEFT[0], h[0]["transaction"]["signatures"][0], evidence=[A])
    swaps = [t for t in h if JUPITER in programs(t)]
    tot: dict[str, Decimal] = {}
    for t in swaps:
        for (o, sym), d in token_deltas(t).items():
            if o == A:
                tot[sym] = tot.get(sym, Decimal(0)) + d
    sol_in = sum(sol_delta(t, A) for t in swaps)
    first, last_ = when(swaps[0]), when(swaps[-1])
    r.claim("C4-09", "A swapped every stablecoin and the wSOL into SOL through Jupiter: 66 swaps between 07:54:48 and 08:08:59 (the USDC and USDT sold include the dust A was sent)",
            (66, "2026-11-02 07:54:48", "2026-11-02 08:08:59", D("-359094.736732"), D("-69868.766126"), D("-7173.929438"), D("-4264.570828378")),
            (len(swaps), first, last_, tot.get("USDC"), tot.get("USDT"), tot.get("USD1"), tot.get("wSOL")),
            evidence=[t["transaction"]["signatures"][0] for t in (swaps[0], swaps[-1])])
    lots: dict[tuple[str, Decimal], int] = {}
    for t in swaps:
        for (o, sym), d in token_deltas(t).items():
            if o == A and d < 0 and sym != "wSOL":
                lots[(sym, d)] = lots.get((sym, d), 0) + 1
    run20 = [when(t) for t in swaps if token_deltas(t).get((A, "USDT")) == D("-20")]
    r.claim("C4-09b", "Lot structure: 7 sales of 50,000 USDC, then 52 sales of 20 USDT each from 07:58:47 to 08:06:46 (about nine seconds apart), then 3 sales of 20,000 USDT; the remainders and the USD1 went in one sale each. The 52 small sales look like a mistyped chunk size (20 for 20,000) in a script, corrected after eight minutes",
            (7, 52, 3, "2026-11-02 07:58:47", "2026-11-02 08:06:46", 4),
            (lots.get(("USDC", D("-50000"))), lots.get(("USDT", D("-20"))), lots.get(("USDT", D("-20000"))), run20[0], run20[-1],
             sum(1 for k, n in lots.items() if n == 1)),
            evidence=[t["transaction"]["signatures"][0] for t in swaps if token_deltas(t).get((A, "USDT")) == D("-20")][:2])
    r.claim("C4-10", "SOL that A gained from those swaps (unwrap plus stablecoin sales), about 8,886 SOL",
            D("8886.418"), sol_in, tol=D("0.01"), evidence=[A])
    big = [t for t in swaps if token_deltas(t).get((A, "USDC")) == D("-50000")]
    sol_for_350k = sum(sol_delta(t, A) for t in big)
    px = (D("350000") / sol_for_350k).quantize(D("0.01"))
    r.claim("C4-11", "Price basis: seven 50,000 USDC sales returned 3,710.28 SOL, $94.33 per SOL",
            (7, D("3710.28"), D("94.33")), (len(big), sol_for_350k.quantize(D("0.01")), px),
            evidence=[t["transaction"]["signatures"][0] for t in big[:2]])
    _cache["sol_px"] = px
    stable = D("359094.73421") + D("69868.765015") + D("7173.929438")
    total = stable + (D("4264.570828") + D("191.242413486")) * px
    r.claim("C4-12", "Value stolen at that price: 436,137.43 in stablecoins plus 4,455.81 SOL, about $856k",
            D("856454"), total.quantize(D("1")), tol=D("50"), evidence=THEFT)
    gap = dt.datetime.fromtimestamp(swaps[0]["blockTime"], dt.timezone.utc) - dt.datetime.fromtimestamp(THEFT_TS, dt.timezone.utc)
    r.claim("C4-13", "Freeze window on the stablecoins: the first sale came 21 minutes 58 seconds after the first theft transfer",
            "0:21:58", str(gap), evidence=[THEFT[0], swaps[0]["transaction"]["signatures"][0]])
    outs = plain_transfers_out(A)
    by = {}
    for _, k, d in outs:
        by[k] = by.get(k, Decimal(0)) + d
    r.claim("C4-14", "A handed the SOL on in plain transfers: 8,576.651 SOL to B in 13 transfers, 500.0001 SOL to C, 1.01 SOL to G",
            ({B: D("8576.651"), C: D("500.0001"), G: D("1.01")}, 13),
            ({k: v for k, v in by.items() if v >= 1}, sum(1 for _, k, _d in outs if k == B)),
            evidence=[t["transaction"]["signatures"][0] for t, k, _d in outs if k in (C, G)])
    r.ev("B: forwarder (swap-service deposit account)", B)
    r.ev("C: Relay attempt, blocked", C)
    r.ev("G: Relay gas top-up", G)
    r.claim("C4-15", "A holds nothing now: 0.00076924 SOL and 0.0002 USDC left behind",
            (D("0.00076924"), D("0.0002")),
            (Decimal(account(A)["lamports"]) / Decimal(10 ** 9),
             sum(Decimal(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmountString"]) for a in token_accounts(A))),
            evidence=[A])


def c_relay(r: Report):
    g = relay_request(RELAY_GAS_TX)
    m = g["data"]["metadata"]
    r.claim("C4-16", "G's 1 SOL went through Relay and paid 0.040953 ETH to E on Ethereum (Relay order, status success)",
            ("success", G, E, "SOL", D("1"), "ETH", D("0.040953161366304933"), RELAY_GAS_OUT),
            (g["status"], g["user"], g["recipient"].lower(), m["currencyIn"]["currency"]["symbol"], D(m["currencyIn"]["amountFormatted"]),
             m["currencyOut"]["currency"]["symbol"], D(m["currencyOut"]["amountFormatted"]), g["data"]["outTxs"][0]["hash"]),
            evidence=[RELAY_GAS_TX, RELAY_GAS_OUT, g["id"]])
    r.ev("Relay order (gas top-up)", g["id"])
    r.ev("E: Ethereum destination", E)
    c = relay_request(RELAY_BLOCKED_TX)
    r.claim("C4-17", "C's 499.99 SOL hit Relay's compliance block: status failure, BLOCKED_WALLET, no payout, no refund",
            ("failure", "BLOCKED_WALLET", C, E, D("499.99"), None, "N/A"),
            (c["status"], c["data"]["failReason"], c["user"], c["recipient"].lower(), D(c["data"]["metadata"]["currencyIn"]["amountFormatted"]),
             c["data"]["outTxs"][0].get("hash"), c["data"]["refundFailReason"]),
            evidence=[RELAY_BLOCKED_TX, c["id"]])
    r.ev("Relay order (blocked)", c["id"])
    t = tx(RELAY_BLOCKED_TX)
    r.claim("C4-18", "That SOL sits with Relay: the blocked transfer credited Relay's Solana depository 499.99 SOL, and C keeps 0.010095001 SOL",
            (D("499.99"), D("0.010095001")), (sol_delta(t, RELAY_SOL), Decimal(account(C)["lamports"]) / Decimal(10 ** 9)),
            evidence=[RELAY_BLOCKED_TX, RELAY_SOL])
    r.ev("Relay Solana depository (infrastructure)", RELAY_SOL)
    single = {}
    for name, addr in (("C", C), ("G", G)):
        signed = [t for t in history(addr) if addr in signers(t)]
        single[name] = (len(signed), {k for t in signed for k in keys(t) if k != addr and sol_delta(t, k) > 0})
    r.claim("C4-18b", "C and G each signed exactly one transaction, their Relay deposit, and nothing else: the thief did not try Relay again from these addresses, and A's own outflows are all accounted for (C4-14)",
            {"C": (1, {RELAY_SOL}), "G": (1, {RELAY_SOL})}, single, evidence=[RELAY_BLOCKED_TX, RELAY_GAS_TX])
    blocked_at = dt.datetime.fromisoformat(c["updatedAt"].replace("Z", "+00:00"))
    r.note("C4-19", "Time between the first theft transfer and Relay's block decision",
           str(blocked_at - dt.datetime.fromtimestamp(THEFT_TS, dt.timezone.utc)).split(".")[0], evidence=[c["id"]])


def c_b_wallet(r: Report):
    h = history(B)
    sg = {s for t in h for s in signers(t)}
    r.claim("C4-20", "B never signed anything: its 44 transactions carry one signature each, from A (the SOL hand-offs), the service relayer (swaps, orders), Mayan's refund relayer or a dust sender",
            (44, False, {A, RELAYER, MAYAN_REFUNDER, "653pnYtpZGMvFytHWsF6yB1DpjBRgHBjswg3pnPfmpsG"}, {1}), (len(h), B in sg, sg, {len(t["transaction"]["signatures"]) for t in h}), evidence=[B, RELAYER])
    r.ev("service relayer (infrastructure)", RELAYER)
    swaps = [t for t in h if JUPITER in programs(t)]
    tot: dict[str, Decimal] = {}
    for t in swaps:
        for (o, sym), d in token_deltas(t).items():
            if o == B:
                tot[sym] = tot.get(sym, Decimal(0)) + d
    r.claim("C4-21", "B turned the SOL back into stablecoins: 13 Jupiter swaps, 8,576.65 SOL out, 797,951.48 USDC and 4.15266427 whETH in",
            (13, D("-8576.65"), D("797951.48"), D("4.15266427")),
            (len(swaps), sum(sol_delta(t, B) for t in swaps).quantize(D("0.01")), tot["USDC"].quantize(D("0.01")), tot["whETH"]),
            evidence=[t["transaction"]["signatures"][0] for t in (swaps[0], swaps[-1])])
    orders = [mayan_order(t["transaction"]["signatures"][0]) for t in h if MAYAN in programs(t)]
    # A refund transaction resolves to the order it refunded, so the two refunds return orders already in the list: de-duplicate by orderId.
    orders = list({o["orderId"]: o for o in orders if "orderId" in o}.values())
    done = [o for o in orders if o["status"] == "ORDER_UNLOCKED"]
    r.claim("C4-22", "15 Mayan Swift orders (10 filled, 2 refunded, 3 cancelled), all from B to the same Ethereum address E, all paying out as ETH",
            (15, {E}, {"ETH"}, {"2"}, {"ORDER_UNLOCKED": 10, "ORDER_REFUNDED": 2, "ORDER_CANCELED": 3}),
            (len(orders), {o["destAddress"].lower() for o in orders}, {o["toTokenSymbol"] for o in orders},
             {o["destChain"] for o in orders}, {s: sum(1 for o in orders if o["status"] == s) for s in {o["status"] for o in orders}}),
            evidence=[o["orderId"] for o in orders])
    usdc = sum(D(o["fromAmount"]) for o in done if o["fromTokenSymbol"] == "USDC")
    weth = sum(D(o["fromAmount"]) for o in done if o["fromTokenSymbol"] == "WETH")
    eth = sum(D(o["toAmount"]) for o in done)
    r.claim("C4-23", "10 orders were filled: 565,076.3112 USDC and 4.1527 WETH in, 251.146683 ETH out to E (13:49 to 14:05 UTC)",
            (10, D("565076.3112"), D("4.1527"), D("251.146683")),
            (len(done), usdc.quantize(D("0.0001")), weth.quantize(D("0.0001")), eth.quantize(D("0.000001"))),
            evidence=[o["fulfillTxHash"] for o in done])
    for o in done:
        r.ev("Mayan fill on Ethereum", o["fulfillTxHash"])
    eth_from_usdc = sum(D(o["toAmount"]) for o in done if o["fromTokenSymbol"] == "USDC")
    px = (usdc / eth_from_usdc).quantize(D("0.01"))
    r.claim("C4-24", "Price basis: the USDC orders bought ETH at $2,287.81", D("2287.81"), px, tol=D("0.05"), evidence=[o["orderId"] for o in done[2:4]])
    _cache["eth_px"] = px
    internal = rest("blockscout", f"https://eth.blockscout.com/api/v2/addresses/{E}/internal-transactions")["items"]
    ins = [i for i in internal if i["to"]["hash"].lower() == E]
    r.claim("C4-25", "Ethereum side: E received exactly those 10 fills as internal transfers from Mayan's SwiftDest contract, 251.146683 ETH in total",
            (10, {SWIFT_DEST.lower()}, D("251.146683"), {o["fulfillTxHash"] for o in done}),
            (len(ins), {i["from"]["hash"].lower() for i in ins}, (sum(Decimal(i["value"]) for i in ins) / Decimal(10 ** 18)).quantize(D("0.000001")),
             {i["transaction_hash"] for i in ins}), evidence=[E, SWIFT_DEST])
    r.ev("Mayan SwiftDest (infrastructure)", SWIFT_DEST)
    refunded = {o["sourceTxHash"]: o for o in orders if o["status"] == "ORDER_REFUNDED"}
    back = {}
    for s in MAYAN_REFUNDS:
        back[s] = token_deltas(tx(s)).get((B, "USDC"))
    r.claim("C4-26", "Two orders (94,148.770677 and 44,729.735102 USDC) expired unfilled and were refunded to B on 3 Nov 11:07, less relayer fees",
            (2, D("94148.770677"), D("44729.735102"), D("94148.525771"), D("44729.481555")),
            (len(refunded), *(D(o["fromAmount"]) for o in sorted(refunded.values(), key=lambda o: -D(o["fromAmount"]))),
             *sorted(back.values(), reverse=True)), evidence=MAYAN_REFUNDS + [o["refundTxHash"] for o in refunded.values()])
    stuck = [o for o in orders if o["status"] == "ORDER_CANCELED"]
    r.claim("C4-27", "Three orders are cancelled in Mayan's records but never refunded: one from 2 Nov 14:11 and the two re-submissions of 3 Nov 11:07",
            (3, {"2026-11-02T14:11", "2026-11-03T11:07"}, {None}),
            (len(stuck), {o["initiatedAt"][:16] for o in stuck}, {o["refundTxHash"] for o in stuck}), evidence=[o["orderId"] for o in stuck])
    resub = {}
    for o in stuck:
        for s in MAYAN_REFUNDS:
            if back[s] == D(o["fromAmount"]):
                src = tx(o["sourceTxHash"])
                resub[s[:8]] = (signers(src), src["blockTime"] - tx(s)["blockTime"], src["slot"] - tx(s)["slot"])
    r.claim("C4-27b", "Each refund was re-ordered to E by the service relayer 2 s and 1 s later (5 slots): the service re-submits a refunded order by itself, so a Mayan refund would go straight back into a new order to E",
            {MAYAN_REFUNDS[0][:8]: ([RELAYER], 2, 5), MAYAN_REFUNDS[1][:8]: ([RELAYER], 1, 5)}, resub,
            evidence=[o["sourceTxHash"] for o in stuck if o["initiatedAt"].startswith("2026-11-03")])
    held = {}
    for st, _ in ESCROWS.items():
        accts = token_accounts(st, SYM["USDC"])
        held[st] = (sum(Decimal(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmountString"]) for a in accts),
                    {a["account"]["data"]["parsed"]["info"]["state"] for a in accts})
    r.claim("C4-28", "Their USDC is still in the three Mayan escrow accounts on Solana, 232,874.666899 USDC in total, token accounts initialized (not frozen)",
            ({k: (v, {"initialized"}) for k, v in ESCROWS.items()}, D("232874.666899")),
            (held, sum(v for v, _ in held.values())), evidence=list(ESCROWS))
    for st in ESCROWS:
        r.ev("Mayan Swift escrow (holds stolen USDC)", st)
    r.claim("C4-29", "B is empty now: 0.00065025 SOL, no token accounts",
            (D("0.00065025"), 0), (Decimal(account(B)["lamports"]) / Decimal(10 ** 9), len(token_accounts(B))), evidence=[B])


def c_ethereum(r: Report):
    bal = Decimal(int(ethereum("eth_getBalance", [E, "latest"]), 16)) / Decimal(10 ** 18)
    nonce = int(ethereum("eth_getTransactionCount", [E, "latest"]), 16)
    r.claim("C4-30", "E holds 251.187636 ETH (the fills plus the Relay gas top-up) and has never sent a transaction (nonce 0)",
            (D("251.187636"), 0), (bal.quantize(D("0.000001")), nonce), evidence=[E])
    r.claim("C4-30b", "E is an externally owned account (no contract code), so whoever holds its private key can move the ETH at any time",
            "0x", ethereum("eth_getCode", [E, "latest"]), evidence=[E])
    usdc_bl = ethereum("eth_call", [{"to": USDC_ETH, "data": "0xfe575a87" + E[2:].rjust(64, "0")}, "latest"])
    usdt_bl = ethereum("eth_call", [{"to": USDT_ETH, "data": "0xe47d6060" + E[2:].rjust(64, "0")}, "latest"])
    r.claim("C4-31", "E is on neither Circle's nor Tether's Ethereum blacklist (isBlacklisted / isBlackListed both false); it holds ETH, which no issuer can freeze",
            (0, 0), (int(usdc_bl, 16), int(usdt_bl, 16)), evidence=[E, USDC_ETH, USDT_ETH])
    native = rest("blockscout", f"https://eth.blockscout.com/api/v2/addresses/{E}/transactions")["items"]
    r.claim("C4-32", "Only two external transactions touch E: the Relay gas top-up and a 1 wei dust transfer from a third party on 3 Nov",
            (2, {RELAY_GAS_OUT}), (len(native), {t["hash"] for t in native if t["from"]["hash"].lower() == "0xa67d7eb4dc68fa6ce8e34ef8cadaf075b9893fbb"}),
            evidence=[t["hash"] for t in native])


def c_freeze(r: Report):
    auth = {}
    for mint, (sym, _) in MINTS.items():
        auth[sym] = account(mint)["data"]["parsed"]["info"].get("freezeAuthority")
    r.claim("C4-33", "USDC, USDT and USD1 on Solana have a freeze authority (the issuer could have frozen A's accounts); wSOL and wrapped ETH have none",
            {"USDC": "7dGbd2QZcCKcTndnHcTL8q7SMVXAkp688NTQYwrRCrar", "USDT": "Q6XprfkF8RQQKoQVG33xT88H7wi8Uk1B1CC7YAs69Gi",
             "USD1": "84ssq8Ud2WRzxVCuEmPa9xLPBUt4odmB8wuE8svZkh71", "wSOL": None, "whETH": None}, auth, evidence=list(MINTS))
    states = {a["pubkey"]: a["account"]["data"]["parsed"]["info"]["state"] for a in token_accounts(A)}
    r.claim("C4-34", "No freeze was ever applied on the path: A's USDC, USDT and USD1 accounts are all 'initialized' and were emptied by swaps, not by the issuers",
            {"initialized"}, set(states.values()), evidence=list(states))


def c_reconcile(r: Report):
    px, eth_px = _cache["sol_px"], _cache["eth_px"]
    exits = {"ETH at E": (D("251.146683") * eth_px).quantize(D("1")),
             "USDC in Mayan escrow": D("232874.666899").quantize(D("1")),
             "SOL held by Relay": (D("499.99") * px).quantize(D("1"))}
    total = sum(exits.values())
    r.claim("C4-35", "Where the money is: about $575k as ETH at E, $233k as USDC in Mayan escrow, $47k as SOL at Relay; together about $855k of the $856k taken (the rest is swap fees)",
            (D("574576"), D("232875"), D("47164"), D("854615")),
            (exits["ETH at E"], exits["USDC in Mayan escrow"], exits["SOL held by Relay"], total), tol=D("200"), evidence=[E, RELAY_SOL, *ESCROWS])


def c_relayer(r: Report):
    h = history(RELAYER)
    mayan = [t for t in h if MAYAN in programs(t)]
    owners = set()
    for t in mayan:
        for (o, _), d in token_deltas(t).items():
            if d < 0 and o != RELAYER:
                owners.add(o)
    first = dt.datetime.fromtimestamp(h[0]["blockTime"], dt.timezone.utc).strftime("%Y-%m-%d")
    r.claim("C4-36", "The relayer is shared infrastructure, not the attacker: active since 23 Jul 2026, it has signed Mayan orders for 32 different deposit accounts, B being one",
            ("2026-07-23", True, 32), (first, len(h) > 100, len(owners)), evidence=[RELAYER, h[0]["transaction"]["signatures"][0]])
    r.claim("C4-37", "The deposit accounts are plain system accounts (the service moves their funds by program signature, so B's funds moved without B ever signing)",
            "11111111111111111111111111111111", account(B)["owner"], evidence=[B])


def c_reports(r: Report):
    """What Onchain Lens published against what the chain shows."""
    r.claim("C4-38", "Onchain Lens: '4.26K WSOL, 191 SOL and $366K in stablecoins' (~$786K). Chain: the stablecoins were 436,137 (the 69,868.77 USDT was left out), total about $856k",
            (D("436137"), D("856454")),
            ((D("359094.73421") + D("69868.765015") + D("7173.929438")).quantize(D("1")),
             (D("436137.428663") + (D("4264.570828") + D("191.242413486")) * _cache["sol_px"]).quantize(D("1"))), tol=D("50"), evidence=THEFT)


def c_noise(r: Report):
    look = "BHRaXMvvhobJPpFm9x28M5vzWbcGwRTDjW76XH4fY3jU"
    t = tx("5DcAJvZhLVYrX7q2CF8zFLzjuaaq7EP8qrByqc6BHqJBjnh4FPwc7bfcT7qiWLEAio4FVfeUMEaeAUinS7EBsfmg")
    e = tx(DUST_ECHO)
    r.claim("C4-39", "Dust from a look-alike of A (BHRaXMvv…3jU, same first 4 and last 3 characters) reached the victim at 07:34:54, after three of the five transfers; three seconds later the thief's key echoed 0.001111 USDC to the real A. A poisoning bot reacting to the theft, not its cause",
            ("2026-11-02 07:34:54", D("0.001111"), [look], "2026-11-02 07:34:57", [VICTIM], (None, 50000)),
            (when(t), token_deltas(t).get((VICTIM, "USDC")), signers(t), when(e), signers(e), compute_budget(e)),
            evidence=[t["transaction"]["signatures"][0], DUST_ECHO, look])
    r.ev("look-alike dust sender (third party)", look)
    theft = [tx(s) for s in THEFT]
    usdt_dust = next(x["signature"] for x in sigs(VICTIM) if x["signature"].startswith("5jYL5HLtedDy"))
    usdt_sold = sum(d for t in history(A) if JUPITER in programs(t) for (o, s), d in token_deltas(t).items() if o == A and s == "USDT")
    victim_left = Decimal(theft[4]["meta"]["postBalances"][keys(theft[4]).index(VICTIM)]) / Decimal(10 ** 9)
    r.claim("C4-39b", "The echo is the drain script's sweep loop: the dust landed at 07:34:54 and the victim's key forwarded it at 07:34:57, between the USD1 transfer (07:34:50) and the wSOL transfer (07:35:06). The USDT dust that landed at 07:36:47, after the final SOL transfer, was never forwarded (A's USDT equals the theft plus one dust from another look-alike), and the key left the victim 0.0009947 SOL. The drain was scripted and stopped once it had the SOL",
            ("2026-11-02 07:34:54", "2026-11-02 07:34:57", "2026-11-02 07:34:50", "2026-11-02 07:35:06", "2026-11-02 07:36:47", D("0"), D("0.0009947")),
            (when(t), when(e), when(theft[2]), when(theft[3]), when(tx(usdt_dust)), usdt_sold + D("69868.765015") + D("0.001111"), victim_left),
            evidence=[DUST_ECHO, usdt_dust, THEFT[4]])
    look_v = "7dGrPwHjdeAEcU2VKjFj7GhdoSnb3JqfRxWLkfjGuuUu"
    lv = [t for t in history(A) if look_v in signers(t)]
    bx = {compute_budget(tx(x["signature"])) for x in sigs(VICTIM) if x["blockTime"] > THEFT_TS and look in signers(tx(x["signature"]))}
    r.claim("C4-39c", "A second look-alike, 7dGrPwHj…uuUu (first four and last four characters of the victim), dusted A with 0.001111 USDC at 07:34:54, 0.001111 USDT at 07:36:43 and 0.00001 SOL at 07:37:22, with the same client fingerprint (limit 1,000,000, price 5) as BHRaXMvv…3jU used on the victim: one poisoning operation working both sides of the theft",
            (["2026-11-02 07:34:54", "2026-11-02 07:36:43", "2026-11-02 07:37:22"], {(1000000, 5)}, {(1000000, 5)}),
            ([when(t) for t in lv], {compute_budget(t) for t in lv}, bx), evidence=[t["transaction"]["signatures"][0] for t in lv] + [look_v])
    r.ev("look-alike of the victim: dust sender (third party)", look_v)
    reals = {"victim": VICTIM, "B": B, "C": C, "G": G, "treasury": OPERATOR}
    alike: dict[str, int] = {}
    for t in history(A):
        s = signers(t)[0]
        for n, a in reals.items():
            if s != a and s[:4] == a[:4]:
                alike[n] = alike.get(n, 0) + 1
    r.note("C4-39d", "Dust transfers A received from look-alikes of its counterparties (first four characters shared), by counterparty imitated: poisoning bots following A's own transfers, none of them a lead",
           alike, evidence=[A])


def c_operator(r: Report):
    h = history(OPERATOR)
    funded = [(t, sol_delta(t, OPERATOR)) for t in h if VICTIM in signers(t) and t["blockTime"] < THEFT_TS]
    days = sorted({dt.datetime.fromtimestamp(t["blockTime"], dt.timezone.utc).strftime("%Y-%m-%d") for t, _ in funded})
    r.claim("C4-40", "Ace7h… is the bot's treasury, not the thief's: the victim's key signed 22 payments to it on 16 days from 2 Jul 2026 to 22 Oct 2026, long before the theft, starting with 1 SOL",
            (22, "2026-07-02", "2026-10-22", 16, D("1")),
            (len(funded), days[0], days[-1], len(days), funded[0][1]), evidence=[funded[0][0]["transaction"]["signatures"][0], OPERATOR])
    r.note("C4-40b", "SOL the treasury received from the victim before the theft, and its signature count in the page read",
           (sum(v for _, v in funded).quantize(D("0.01")), len(h)), evidence=[OPERATOR])
    r.claim("C4-41", "The treasury signs for itself (30 of its transactions) and was active on 6 Nov; it sent no value to A, B, C or G",
            (30, True, D("0")),
            (sum(1 for t in h if OPERATOR in signers(t)), any(t["blockTime"] > 1793980800 for t in h),
             sum(sol_delta(t, k) for t in h if OPERATOR in signers(t) for k in (A, B, C, G) if k in keys(t) and sol_delta(t, k) > D("0.000001"))),
            evidence=[OPERATOR])
    offer = tx(OFFER_TX)
    memo = next(i["parsed"] for i in offer["transaction"]["message"]["instructions"] if i.get("program") == "spl-memo")
    r.claim("C4-43", "At 13:22:50 on 2 Nov, 5 h 50 min after the theft, the treasury sent A one lamport with a memo offering a 20 % white-hat bounty for the return of 80 % within 48 hours",
            ("2026-11-02 13:22:50", [OPERATOR], True, True),
            (when(offer), signers(offer), "20% as a white-hat bounty" in memo, "within 48 hours" in memo), evidence=[OFFER_TX])
    r.note("C4-43b", "Memo text as recorded on chain (data, not a statement of fact)", memo, evidence=[OFFER_TX])
    r.ev("operator's bounty offer (memo)", OFFER_TX)
    replies = [t for t in history(A) if A in signers(t) and any(i.get("program") == "spl-memo" for i in t["transaction"]["message"]["instructions"])]
    back = sum(sol_delta(t, OPERATOR) for t in history(A) if A in signers(t) and OPERATOR in keys(t))
    r.claim("C4-44", "No reply and no return: A never signed a memo, and nothing went from A to the treasury; A had already handed everything on by 14:12",
            (0, D("0")), (len(replies), back), evidence=[A, OPERATOR])

def c_pda(r: Report):
    r.claim("C4-42", "B is off the ed25519 curve: it is a program-derived address with no private key, so it can only be moved by the program that derived it. A, C, G, the victim and the relayer are ordinary key pairs",
            {"B": False, "A": True, "C": True, "G": True, "victim": True, "relayer": True},
            {"B": on_curve(B), "A": on_curve(A), "C": on_curve(C), "G": on_curve(G), "victim": on_curve(VICTIM), "relayer": on_curve(RELAYER)},
            evidence=[B])


if __name__ == "__main__":
    for fn in (c_theft, c_a_wallet, c_relay, c_b_wallet, c_ethereum, c_freeze, c_reconcile, c_relayer, c_reports, c_noise, c_operator, c_pda):
        R.run(fn)
    ok = R.write()
    sys.exit(0 if ok else 1)
