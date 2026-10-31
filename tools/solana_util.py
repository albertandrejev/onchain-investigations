"""Solana helpers: SPL token balance deltas per transaction, signature lists."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from .net import solana

USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def signatures(address: str, limit: int = 1000, before: str | None = None) -> list[dict]:
    p = {"limit": limit}
    if before:
        p["before"] = before
    return solana("getSignaturesForAddress", [address, p]) or []


def all_signatures(address: str, max_pages: int = 10) -> list[dict]:
    out, before = [], None
    for _ in range(max_pages):
        page = signatures(address, 1000, before)
        out += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    return out


def tx(signature: str) -> dict:
    return solana("getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])


def token_deltas(signature: str, mint: str = USDC_MINT) -> list[dict]:
    """Per token account: {account, owner, delta} for one mint."""
    t = tx(signature)
    keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]
    pre = {b["accountIndex"]: b for b in t["meta"]["preTokenBalances"] if b["mint"] == mint}
    post = {b["accountIndex"]: b for b in t["meta"]["postTokenBalances"] if b["mint"] == mint}
    out = []
    for i in set(pre) | set(post):
        a = Decimal(post.get(i, {}).get("uiTokenAmount", {}).get("amount", "0"))
        b = Decimal(pre.get(i, {}).get("uiTokenAmount", {}).get("amount", "0"))
        if a != b:
            info = post.get(i) or pre.get(i)
            out.append({"account": keys[i], "owner": info.get("owner"), "delta": (a - b) / Decimal(10**6)})
    return out


def block_time(signature: str) -> dt.datetime:
    return dt.datetime.fromtimestamp(tx(signature)["blockTime"], dt.timezone.utc)


def fee_payer(signature: str) -> str:
    return tx(signature)["transaction"]["message"]["accountKeys"][0]["pubkey"]


def token_account_owner(account: str) -> str:
    info = solana("getAccountInfo", [account, {"encoding": "jsonParsed"}])
    return info["value"]["data"]["parsed"]["info"]["owner"]
