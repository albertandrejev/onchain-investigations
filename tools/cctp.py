"""Circle CCTP (v1) decoder for Noble transactions.

Two directions matter:

* **Outbound** (Noble -> other chain): ``MsgDepositForBurn[WithCaller]`` carries
  ``destination_domain`` and a 32-byte ``mint_recipient``. For Solana (domain 5)
  the recipient is a USDC *token account* (base58); for EVM domains it is an
  address left-padded to 32 bytes.

* **Inbound** (other chain -> Noble): ``MsgReceiveMessage`` carries the raw CCTP
  message. Its body contains ``messageSender`` - the account that burned USDC on
  the source chain. Explorers usually show only the Noble-side module account as
  "sender"; decoding the body reveals who actually signed the burn.

Message layout (CCTP v1)::

    header: version u32 | sourceDomain u32 | destinationDomain u32 | nonce u64 |
            sender 32B | recipient 32B | destinationCaller 32B
    body  : version u32 | burnToken 32B | mintRecipient 32B | amount u256 |
            messageSender 32B

CLI
---
    python -m tools.cctp tx <noble-tx-hash>
"""
from __future__ import annotations

import base64
import sys

DOMAINS = {0: "Ethereum", 1: "Avalanche", 2: "OP", 3: "Arbitrum", 4: "Noble", 5: "Solana",
           6: "Base", 7: "Polygon PoS", 10: "Unichain"}
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def b58decode(s: str, length: int = 32) -> bytes:
    n = 0
    for ch in s:
        n = n * 58 + _B58.index(ch)
    return n.to_bytes(length, "big")


def render_address(raw32: bytes, domain: int) -> str:
    """Human form of a 32-byte CCTP address for the given domain."""
    if domain == 5:
        return b58encode(raw32)
    if domain == 4:
        from .bech32 import encode
        return encode("noble", raw32[12:])
    return "0x" + raw32[12:].hex()


def decode_deposit_for_burn(msg: dict) -> dict:
    dom = int(msg["destination_domain"])
    out = {
        "from": msg.get("from"),
        "amount": int(msg["amount"]),
        "destination_domain": dom,
        "destination_chain": DOMAINS.get(dom, f"domain {dom}"),
        "mint_recipient": render_address(base64.b64decode(msg["mint_recipient"]), dom),
    }
    if msg.get("destination_caller"):
        out["destination_caller"] = render_address(base64.b64decode(msg["destination_caller"]), dom)
    return out


def decode_message(message_b64: str) -> dict:
    raw = base64.b64decode(message_b64)
    u32 = lambda o: int.from_bytes(raw[o:o + 4], "big")
    src, dst = u32(4), u32(8)
    body = raw[116:]
    return {
        "version": u32(0),
        "source_domain": src,
        "source_chain": DOMAINS.get(src, str(src)),
        "destination_domain": dst,
        "nonce": int.from_bytes(raw[12:20], "big"),
        "burn_token": render_address(body[4:36], src),
        "mint_recipient": render_address(body[36:68], dst),
        "amount": int.from_bytes(body[68:100], "big"),
        "message_sender": render_address(body[100:132], src),
    }


def decode_orbiter_memo(memo: dict) -> dict | None:
    """Noble Orbiter forwarding memo (IBC -> Noble -> CCTP) as seen in ICS-20 packets."""
    fwd = (memo or {}).get("orbiter", {}).get("forwarding", {})
    attrs = fwd.get("attributes", {})
    if fwd.get("protocol_id") != "PROTOCOL_CCTP":
        return None
    dom = int(attrs["destination_domain"])
    return {"destination_chain": DOMAINS.get(dom, str(dom)),
            "mint_recipient": render_address(base64.b64decode(attrs["mint_recipient"]), dom)}


def decode_noble_tx(txhash: str) -> list[dict]:
    from .net import Cosmos
    tx = Cosmos("noble").tx(txhash)
    out = []
    for m in tx["tx"]["body"]["messages"]:
        t = m["@type"]
        if t.endswith("MsgDepositForBurn") or t.endswith("MsgDepositForBurnWithCaller"):
            out.append({"type": "outbound burn", **decode_deposit_for_burn(m)})
        elif t.endswith("MsgReceiveMessage"):
            out.append({"type": "inbound mint", **decode_message(m["message"])})
    return out


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "tx":
        for row in decode_noble_tx(sys.argv[2]):
            for k, v in row.items():
                print(f"{k:20} {v}")
            print()
    else:
        print(__doc__)
