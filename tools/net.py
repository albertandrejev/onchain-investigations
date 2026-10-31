"""Minimal data clients for Cosmos SDK REST (LCD), Solana JSON-RPC and Ethereum JSON-RPC.

Design goals
------------
* Standard library only.
* Every raw response is cached under ``$CIP_CACHE`` (each case points it at its own
  ``cases/NN-slug/data/cache/``; ad-hoc CLI use goes to ``.cache/``) keyed by *what* was asked
  (chain + path + height), not *where* it was asked. Re-running the checks
  offline reproduces exactly the same numbers; deleting the cache re-fetches
  everything from public nodes.
* Endpoint independence: for Cosmos chains we try a list of known archive
  endpoints first, then every REST endpoint listed for the chain in the
  cosmos.directory chain registry, until one returns a valid answer.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("CIP_CACHE") or ROOT / ".cache")
OFFLINE = os.environ.get("CIP_OFFLINE") == "1"
UA = "onchain-investigations/1.0 (verification scripts)"

# Archive-capable REST endpoints that served historical data during the
# investigation. Registry endpoints are appended automatically as fallback.
PREFERRED_REST = {
    "juno": ["https://juno.api.m.stavr.tech"],
    "neutron": ["https://rest-archive.neutron.solva.solutions:443"],
    "noble": ["https://rest.lavenderfive.com:443/noble"],
    "secretnetwork": ["https://rest.lavenderfive.com:443/secretnetwork"],
    "cosmoshub": [
        "https://api.cosmoshub-4-archive.citizenweb3.com:443",
        "https://rest.lavenderfive.com:443/cosmoshub",
    ],
    "osmosis": ["https://lcd.osmosis.zone"],
    "dydx": ["https://dydx-rest.publicnode.com"],
}
PREFERRED_RPC = {
    "cosmoshub": ["https://rpc.cosmoshub-4-archive.citizenweb3.com:443"],
    "neutron": ["https://rpc-archive.neutron.solva.solutions:443"],
}
SOLANA_RPC = os.environ.get("SOLANA_RPC", "https://api.mainnet-beta.solana.com")
ETH_RPC = os.environ.get("ETH_RPC", "https://ethereum-rpc.publicnode.com")


class FetchError(RuntimeError):
    pass


def _http(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 60):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # Cosmos REST returns JSON bodies for 4xx (e.g. {"code":5,"message":"not found"}).
        body = e.read().decode(errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            raise e from None


def _cache_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha1(key.encode()).hexdigest()[:20]
    return CACHE / namespace / f"{digest}.json"


def cached(namespace: str, key: str, producer):
    """Return cached JSON for (namespace, key) or call producer() and store it."""
    p = _cache_path(namespace, key)
    if p.exists():
        return json.loads(p.read_text())["response"]
    if OFFLINE:
        raise FetchError(f"offline and not cached: {namespace} {key}")
    resp = producer()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"key": key, "fetched_at": int(time.time()), "response": resp}, indent=1))
    return resp


_registry: dict[str, list[str]] = {}


def registry_rest(chain: str) -> list[str]:
    if chain not in _registry:
        try:
            d = _http(f"https://chains.cosmos.directory/{chain}", timeout=30)["chain"]
            _registry[chain] = [a["address"].rstrip("/") for a in d.get("apis", {}).get("rest", [])]
        except Exception:
            _registry[chain] = []
    return _registry[chain]


class Cosmos:
    """REST client for one Cosmos SDK chain with endpoint fallback and caching."""

    def __init__(self, chain: str):
        self.chain = chain

    def _endpoints(self):
        seen = []
        for u in PREFERRED_REST.get(self.chain, []) + registry_rest(self.chain):
            if u not in seen:
                seen.append(u)
        return seen

    def get(self, path: str, height: int | None = None, valid=None):
        """GET a REST path. ``valid(resp)`` decides whether an answer is usable
        (e.g. a pruned node answers 'tx not found' - we then try the next node)."""
        key = f"{self.chain}|{path}|{height or ''}"

        def produce():
            errors = []
            for base in self._endpoints():
                headers = {"x-cosmos-block-height": str(height)} if height else None
                for attempt in range(2):
                    try:
                        resp = _http(base + path, headers=headers)
                        if valid is None or valid(resp):
                            return resp
                        errors.append(f"{base}: invalid answer")
                        break
                    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
                        errors.append(f"{base}: {e}")
                        time.sleep(1 + attempt)
            raise FetchError(f"{self.chain} {path}: no endpoint answered\n  " + "\n  ".join(errors[-6:]))

        return cached(self.chain, key, produce)

    # convenience -----------------------------------------------------------
    def tx(self, txhash: str) -> dict:
        return self.get(f"/cosmos/tx/v1beta1/txs/{txhash.upper()}", valid=lambda r: "tx_response" in r)

    def search(self, query: str, limit: int = 100, order: str = "ORDER_BY_ASC") -> dict:
        path = f"/cosmos/tx/v1beta1/txs?query={quote(query)}&pagination.limit={limit}&order_by={order}"
        return self.get(path, valid=lambda r: "tx_responses" in r)

    def balances(self, address: str, height: int | None = None) -> dict[str, int]:
        r = self.get(f"/cosmos/bank/v1beta1/balances/{address}?pagination.limit=200", height=height,
                     valid=lambda r: "balances" in r)
        return {b["denom"]: int(b["amount"]) for b in r["balances"]}

    def block_time(self, height: int) -> str:
        r = self.get(f"/cosmos/base/tendermint/v1beta1/blocks/{height}", valid=lambda r: "block" in r)
        return r["block"]["header"]["time"]


def tendermint_rpc(chain: str, path: str):
    key = f"{chain}|rpc|{path}"

    def produce():
        for base in PREFERRED_RPC.get(chain, []):
            try:
                r = _http(base + path, timeout=120)
                if "result" in r:
                    return r
            except Exception:
                continue
        raise FetchError(f"{chain} rpc {path}")

    return cached(chain + "-rpc", key, produce)


def _jsonrpc(url: str, ns: str, method: str, params: list):
    key = f"{method}|{json.dumps(params, sort_keys=True)}"

    def produce():
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
        last = None
        for attempt in range(5):
            try:
                r = _http(url, data=body, headers={"Content-Type": "application/json"})
                if r.get("result") is not None:
                    return r["result"]
                last = r.get("error") or r
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
                last = e
            time.sleep(2 + attempt * 2)
        raise FetchError(f"{ns} {method} {json.dumps(params)[:120]} failed after 5 attempts: {last}")

    return cached(ns, key, produce)


def solana(method: str, params: list):
    return _jsonrpc(SOLANA_RPC, "solana", method, params)


def ethereum(method: str, params: list):
    return _jsonrpc(ETH_RPC, "ethereum", method, params)


# helpers ---------------------------------------------------------------------
def events(tx_response: dict, etype: str | None = None):
    """Yield (type, {key: value}) for every event of a tx response."""
    for ev in tx_response.get("events", []):
        if etype is None or ev["type"] == etype:
            yield ev["type"], {a["key"]: a.get("value", "") for a in ev["attributes"]}


def parse_coins(s: str) -> dict[str, int]:
    """'100uatom,5ibc/XYZ' -> {'uatom': 100, 'ibc/XYZ': 5}"""
    out: dict[str, int] = {}
    for part in filter(None, (s or "").split(",")):
        m = re.match(r"^(\d+)(.+)$", part.strip())
        if m:
            out[m.group(2)] = out.get(m.group(2), 0) + int(m.group(1))
    return out
