"""Tron data client (TronGrid) + address codec + THORNode / Bitcoin (mempool.space) lookups.

Same conventions as ``tools/net.py``:

* standard library only;
* every raw response is cached under ``data/cache/<namespace>/`` keyed by the
  request (never by the API key), so checks re-run offline (``CIP_OFFLINE=1``);
* figures are always computed from raw responses, never from explorer pages.

TronGrid works without a key but rate-limits hard (HTTP 429). Set
``TRONGRID_API_KEY`` in the environment to raise the limit. The key is sent as
the ``TRON-PRO-API-KEY`` header only and is never written to the cache.

CLI:
    python -m tools.tron addr 41e092bce6dc52c38fbf7441edc8ea5b89b48a8a5a   # hex -> base58
    python -m tools.tron hex  TWSe9ZFc26fQo5vgramdwMCUWi2oKwo2BZ           # base58 -> hex
    python -m tools.tron note <txid>                                       # decode a tx note
    python -m tools.tron trc20 <address> [--from 2026-09-12T00:00] [--to 2026-09-13T00:00]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
from decimal import Decimal

from tools.net import FetchError, _http, cached

TRONGRID = os.environ.get("TRONGRID_URL", "https://api.trongrid.io")
THORNODE = os.environ.get("THORNODE_URL", "https://thorchain-thornode-lb-1.thorwallet.org")
MEMPOOL = os.environ.get("MEMPOOL_URL", "https://mempool.space/api")
API_KEY = os.environ.get("TRONGRID_API_KEY", "")

USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"  # Tether USD (TRC-20), 6 decimals
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


# --------------------------------------------------------------------------- address codec
def _dsha(b: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(b).digest()).digest()


def to_base58(hex_addr: str) -> str:
    """'41' + 20-byte hex (or 0x-prefixed 20-byte EVM hex) -> T... base58check address."""
    h = hex_addr.lower().removeprefix("0x")
    if len(h) == 40:
        h = "41" + h
    raw = bytes.fromhex(h)
    raw += _dsha(raw)[:4]
    n, s = int.from_bytes(raw, "big"), ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    return s


def to_hex(addr: str) -> str:
    """T... base58check -> '41' + 20-byte hex (checksum verified)."""
    n = 0
    for ch in addr:
        n = n * 58 + _B58.index(ch)
    raw = n.to_bytes(25, "big")
    if _dsha(raw[:21])[:4] != raw[21:]:
        raise ValueError(f"bad Tron address checksum: {addr}")
    return raw[:21].hex()


# --------------------------------------------------------------------------- transport
def _tron_http(url: str, body: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["TRON-PRO-API-KEY"] = API_KEY
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(7):
        try:
            return _http(url, data=data, headers=headers, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"tron: no answer for {url}")


def get(path: str):
    return cached("tron", f"GET|{path}", lambda: _tron_http(TRONGRID + path))


def post(path: str, body: dict):
    return cached("tron", f"POST|{path}|{json.dumps(body, sort_keys=True)}",
                  lambda: _tron_http(TRONGRID + path, body))


# --------------------------------------------------------------------------- queries
def ms(iso: str) -> int:
    """'2026-09-12T01:00' (UTC) -> epoch milliseconds."""
    return int(dt.datetime.fromisoformat(iso).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def iso(ms_: int) -> str:
    return dt.datetime.fromtimestamp(ms_ / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def trc20(address: str, token: str = USDT, start: str | None = None, end: str | None = None,
          max_rows: int = 5000) -> list[dict]:
    """All TRC-20 transfers of ``token`` touching ``address`` (both directions), oldest first."""
    q = f"/v1/accounts/{address}/transactions/trc20?limit=200&order_by=block_timestamp,asc&contract_address={token}"
    if start:
        q += f"&min_timestamp={ms(start)}"
    if end:
        q += f"&max_timestamp={ms(end)}"
    rows, path = [], q
    while path and len(rows) < max_rows:
        page = get(path)
        rows += page.get("data", [])
        nxt = page.get("meta", {}).get("links", {}).get("next")
        path = nxt.replace(TRONGRID, "") if nxt else None
    return rows


def transactions(address: str, limit: int = 200) -> list[dict]:
    """First ``limit`` native transactions involving ``address`` (oldest first)."""
    return get(f"/v1/accounts/{address}/transactions?limit={limit}&order_by=block_timestamp,asc").get("data", [])


def amount(row: dict) -> Decimal:
    return Decimal(int(row["value"])) / (Decimal(10) ** int(row["token_info"]["decimals"]))


def account(address: str) -> dict:
    d = get(f"/v1/accounts/{address}").get("data", [])
    return d[0] if d else {}


def contract_creator(address: str) -> str | None:
    """origin_address of a smart contract (None for ordinary accounts)."""
    c = post("/wallet/getcontract", {"value": address, "visible": True})
    return c.get("origin_address")


def tx(txid: str) -> dict:
    return post("/wallet/gettransactionbyid", {"value": txid})


def tx_info(txid: str) -> dict:
    return post("/wallet/gettransactioninfobyid", {"value": txid})


def call_summary(txid: str) -> dict:
    """Signer, called contract, 4-byte selector and note of a transaction."""
    t = tx(txid)
    raw = t["raw_data"]
    c = raw["contract"][0]
    v = c["parameter"]["value"]
    data = v.get("data", "")
    return {
        "type": c["type"],
        "signer": to_base58(v["owner_address"]),
        "contract": to_base58(v["contract_address"]) if v.get("contract_address") else None,
        "to": to_base58(v["to_address"]) if v.get("to_address") else None,
        "amount_sun": v.get("amount", 0),
        "selector": data[:8] or None,
        "note_hex": raw.get("data", ""),
        "note": note_text(raw.get("data", "")),
        "result": t.get("ret", [{}])[0].get("contractRet"),
    }


def note_text(note_hex: str) -> str | None:
    """Decode a Tron tx note as UTF-8 if it is printable text (THORChain memos are)."""
    if not note_hex:
        return None
    try:
        s = bytes.fromhex(note_hex).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return s if s.isprintable() else None


def usdt_blacklisted(address: str) -> bool:
    """Tether's on-chain freeze list: USDT.isBlackListed(address) via a constant call."""
    param = to_hex(address)[2:].rjust(64, "0")
    r = post("/wallet/triggerconstantcontract", {
        "owner_address": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",  # zero address, read-only call
        "contract_address": USDT, "function_selector": "isBlackListed(address)",
        "parameter": param, "visible": True})
    return int(r["constant_result"][0], 16) == 1


# --------------------------------------------------------------------------- THORChain / Bitcoin
def thornode_tx(txid: str) -> dict:
    """THORNode /thorchain/tx/status: inbound tx, memo, planned and signed outbound txs."""
    return cached("thornode", f"tx/status/{txid.upper()}",
                  lambda: _http(f"{THORNODE}/thorchain/tx/status/{txid.upper()}", timeout=60))


def btc(path: str):
    return cached("bitcoin", path, lambda: _http(MEMPOOL + path, timeout=60))


def btc_tx(txid: str) -> dict:
    return btc(f"/tx/{txid}")


def btc_address_txs(address: str) -> list[dict]:
    return btc(f"/address/{address}/txs")


# --------------------------------------------------------------------------- CLI
if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "addr":
        print(to_base58(a[1]))
    elif a[0] == "hex":
        print(to_hex(a[1]))
    elif a[0] == "note":
        print(json.dumps(call_summary(a[1]), indent=1))
    elif a[0] == "trc20":
        kw = {}
        if "--from" in a:
            kw["start"] = a[a.index("--from") + 1]
        if "--to" in a:
            kw["end"] = a[a.index("--to") + 1]
        for r in trc20(a[1], **kw):
            d = "IN " if r["to"] == a[1] else "OUT"
            other = r["from"] if d == "IN " else r["to"]
            print(iso(r["block_timestamp"]), d, f"{amount(r):>16,.6f}", other, r["transaction_id"])
