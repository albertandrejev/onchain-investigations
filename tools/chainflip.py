"""Chainflip decoders and State Chain RPC.

* ``vault_swap_note``: decode the SCALE-encoded vault-swap note that Chainflip
  reads from a Tron transaction's ``raw_data.data`` (docs:
  https://docs.chainflip.io/brokers/vault-swaps-api/tron). Only the leading,
  fixed-layout fields are decoded: output asset, destination, CCM flag,
  ``cf_parameters`` version, retry duration and refund address.
* ``all_batch``: split the calldata of a Vault ``allBatch`` call (selector
  ``0x5f8c0f9a``, the call that fetches deposit channels) into its signature
  words: the aggregate-key signature, the key-manager nonce and kTimesG.
* ``ss58``: State Chain account id from a 32-byte public key (prefix 2112, ``cF...``).
* ``rpc``: cached JSON-RPC call to a public State Chain node (``cf_account_info`` etc.).

Asset and address enums follow chainflip-backend ``state-chain/primitives/src/chains/assets.rs``
and ``state-chain/chains/src/address.rs``.

CLI:
    python -m tools.chainflip note <note-hex>
    python -m tools.chainflip ss58 <32-byte-hex>
    python -m tools.chainflip account <cF... account id>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from tools.net import _http, cached

RPC = os.environ.get("CHAINFLIP_RPC", "https://mainnet-rpc.chainflip.io")
SELECTOR_ALL_BATCH = "5f8c0f9a"  # allBatch((uint256,uint256,address),(bytes32,address)[],(address,address)[],(address,address,uint256)[])
ASSETS = {1: "Eth", 2: "Flip", 3: "Usdc", 4: "Dot", 5: "Btc", 6: "ArbEth", 7: "ArbUsdc", 8: "Usdt",
          9: "Sol", 10: "SolUsdc", 11: "HubDot", 12: "HubUsdt", 13: "HubUsdc", 14: "Wbtc", 15: "ArbUsdt",
          16: "SolUsdt", 17: "Trx", 18: "TrxUsdt", 19: "Bnb", 20: "BscUsdt", 21: "Cbbtc"}
ENCODED_ADDRESS = ["Eth", "Dot", "Btc", "Arb", "Sol", "Hub", "Tron", "Bsc"]  # enum variant index -> chain
_ADDR_LEN = {"Eth": 20, "Dot": 32, "Arb": 20, "Sol": 32, "Hub": 32, "Tron": 20, "Bsc": 20}
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _compact(b: bytes, i: int) -> tuple[int, int]:
    """SCALE compact integer at offset i -> (value, new offset). Modes 0-2 only."""
    mode = b[i] & 3
    if mode == 0:
        return b[i] >> 2, i + 1
    if mode == 1:
        return int.from_bytes(b[i:i + 2], "little") >> 2, i + 2
    if mode == 2:
        return int.from_bytes(b[i:i + 4], "little") >> 2, i + 4
    raise ValueError("big-integer compact mode not supported")


def vault_swap_note(note_hex: str, refund_len: int = 20) -> dict:
    """Decode the leading fields of a vault-swap note.

    ``refund_len`` is the source chain's address length (20 for Tron): the refund
    address inside ``cf_parameters`` is a raw source-chain address, not an EncodedAddress.
    """
    b = bytes.fromhex(note_hex.removeprefix("0x"))
    asset = b[0]
    chain = ENCODED_ADDRESS[b[1]]
    if chain == "Btc":
        n, i = _compact(b, 2)
        dest, i = b[i:i + n].hex(), i + n
    else:
        n = _ADDR_LEN[chain]
        dest, i = b[2:2 + n].hex(), 2 + n
    ccm = b[i] != 0
    if ccm:
        raise ValueError("CCM vault swaps are not decoded")
    length, i = _compact(b, i + 1)
    p = b[i:i + length]
    return {"output_asset": ASSETS.get(asset, asset), "output_chain": chain, "destination": dest,
            "ccm": ccm, "cf_parameters_version": p[0],
            "retry_duration": int.from_bytes(p[1:5], "little"),
            "refund_address": p[5:5 + refund_len].hex()}


def all_batch(calldata_hex: str) -> dict:
    """Signature words of a Vault allBatch call (first three ABI words: sig, nonce, kTimesG)."""
    d = calldata_hex.removeprefix("0x")
    if d[:8] != SELECTOR_ALL_BATCH:
        raise ValueError(f"not an allBatch call: selector {d[:8]}")
    w = [d[8 + 64 * k: 8 + 64 * (k + 1)] for k in range(3)]
    return {"sig": w[0], "nonce": int(w[1], 16), "k_times_g": w[2][24:]}


def ss58(pubkey_hex: str, prefix: int = 2112) -> str:
    """SS58 address of a 32-byte public key (two-byte prefix form, as Chainflip's 2112)."""
    pub = bytes.fromhex(pubkey_hex.removeprefix("0x"))
    pre = bytes([((prefix & 0xFC) >> 2) | 0x40, (prefix >> 8) | ((prefix & 0x03) << 6)])
    body = pre + pub
    full = body + hashlib.blake2b(b"SS58PRE" + body, digest_size=64).digest()[:2]
    n, s = int.from_bytes(full, "big"), ""
    while n:
        n, r = divmod(n, 58)
        s = _B58[r] + s
    return s


def rpc(method: str, params: list):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = cached("chainflip", f"{method}|{json.dumps(params)}",
                  lambda: _http(RPC, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}))
    if "error" in resp:
        raise RuntimeError(f"chainflip {method}: {resp['error']}")
    return resp["result"]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["note"]:
        print(json.dumps(vault_swap_note(a[1]), indent=1))
    elif a[:1] == ["ss58"]:
        print(ss58(a[1]))
    elif a[:1] == ["account"]:
        print(json.dumps(rpc("cf_account_info", [a[1]]), indent=1))
    else:
        print(__doc__)
