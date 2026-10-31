"""Bech32 (BIP-173) encode/decode and same-key clustering for Cosmos addresses.

Why this matters for investigations
-----------------------------------
A Cosmos SDK account address is ``bech32(prefix, ripemd160(sha256(pubkey)))``.
Chains that share the coin type (118: Cosmos Hub, Osmosis, Juno, Neutron,
Noble, dYdX, Axelar, ...) derive the *same 20-byte payload* from the same key,
so ``juno1pqard...``, ``osmo1pqard...`` and ``noble1pqard...`` are provably
the same keyholder. Chains with a different coin type (e.g. Secret = 529)
derive a different payload from the same mnemonic, so absence of a match there
proves nothing.

32-byte payloads are contracts / module accounts / ICA, not user keys: equal
payloads across chains do not imply common control.

CLI
---
    python -m tools.bech32 decode <address>
    python -m tools.bech32 convert <address> <new-prefix>
    python -m tools.bech32 cluster <address> [<address> ...]
"""
from __future__ import annotations

import sys

CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_GEN = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _polymod(values):
    chk = 1
    for v in values:
        b = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= _GEN[i] if (b >> i) & 1 else 0
    return chk


def _hrp_expand(hrp):
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def convertbits(data, frombits, tobits, pad=True):
    acc = bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid value")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding")
    return ret


def decode(address: str) -> tuple[str, bytes]:
    """Return (hrp, payload bytes). Raises ValueError on a bad checksum."""
    a = address.strip()
    if a.lower() != a and a.upper() != a:
        raise ValueError("mixed case")
    a = a.lower()
    pos = a.rfind("1")
    if pos < 1 or pos + 7 > len(a):
        raise ValueError("bad separator position")
    hrp, data = a[:pos], a[pos + 1:]
    try:
        values = [CHARSET.index(c) for c in data]
    except ValueError:
        raise ValueError("invalid character") from None
    if _polymod(_hrp_expand(hrp) + values) != 1:
        raise ValueError(f"bad checksum: {address}")
    return hrp, bytes(convertbits(values[:-6], 5, 8, pad=False))


def encode(hrp: str, payload: bytes) -> str:
    data = convertbits(payload, 8, 5)
    poly = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ 1
    checksum = [(poly >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(CHARSET[d] for d in data + checksum)


def convert(address: str, new_hrp: str) -> str:
    return encode(new_hrp, decode(address)[1])


def payload_hex(address: str) -> str:
    return decode(address)[1].hex()


def same_key(a: str, b: str) -> bool:
    """True if two addresses carry the same 20-byte account payload."""
    pa, pb = decode(a)[1], decode(b)[1]
    return len(pa) == 20 and pa == pb


def cluster(addresses: list[str]) -> dict[str, list[str]]:
    """Group addresses by payload. Returns {payload_hex: [addresses...]}."""
    groups: dict[str, list[str]] = {}
    for a in addresses:
        groups.setdefault(payload_hex(a), []).append(a)
    return groups


def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, args = argv[1], argv[2:]
    if cmd == "decode":
        for a in args:
            hrp, p = decode(a)
            kind = "account (20 bytes)" if len(p) == 20 else f"contract/module ({len(p)} bytes)"
            print(f"{a}\n  hrp={hrp} payload={p.hex()} -> {kind}")
    elif cmd == "convert":
        print(convert(args[0], args[1]))
    elif cmd == "cluster":
        for k, v in cluster(args).items():
            tag = "SAME KEY" if len(v) > 1 and len(k) == 40 else ""
            print(f"{k} {tag}")
            for a in v:
                print(f"  {a}")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
