"""Case 01 — unauthorized PHMN mint (Juno) — every number re-derived from chain data.

Run:  python cases/01-unauthorized-mint-juno/checks.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))                       # repository root, for `tools` / `risk`
os.environ.setdefault("CIP_CACHE", str(HERE / "data" / "cache"))  # this case's raw-data snapshot

import base64
import datetime as dt
import json
from decimal import Decimal

from tools import bech32, cctp
from tools.net import Cosmos, events
from tools import solana_util as sol
from tools.claims import Report, micro, D

JUNO, NEUTRON, NOBLE, SECRET = Cosmos("juno"), Cosmos("neutron"), Cosmos("noble"), Cosmos("secretnetwork")

PHMN = "juno1rws84uz7969aaa7pej303udhlkt3j9ca0l3egpcae98jwak9quzq8szn2l"
MINTER = "juno100umj2mnu0u6ujf37c9a3xfy9gl53hu9ekxyyw"
ATT = {
    "juno": "juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0",
    "osmosis": "osmo1pqardc39d558mr58nx5m2wgmy448pv9487ajvp",
    "neutron": "neutron1pqardc39d558mr58nx5m2wgmy448pv94t68qq5",
    "noble": "noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za",
}
RELAYER = "secret1h3grxcfts9uc8lvu9vclhahus2npk24pg0jz5k"
INTERMEDIARY = "secret1j2n0znmwyy95jc8auvdr7ydk05ff97sgd8t7rn"
SOL_OWNER_1 = "39CAqAK85xu24YbTw7LbqnphG1QqReL4PHkcmTX3v1HC"
SOL_TOKEN_1 = "AhT5WaWAAoMF48nPssaSFEoygCfsq1N2qq7BTUJqEer"
# Sweep hot wallets labelled KuCoin on Solscan (public labels, checked 31 Oct 2026; not re-derivable from chain data)
KUCOIN_HOT = {
    "BmFdpraQhkiDQE6SnfG5omcA1VwzqfXrwtNYBwWTymy6",  # "KuCoin Hot Wallet (BmFdp)"
    "AzNEZxmBdy5mX3sjJanZ8FFDxJwiH9mm2SksgtBkUWwe",  # tag "Kucoin Exchange"
}

TX = {
    "relayer_drain": "344DDD42B2C83977AFB746E1EF5CF296C1E002A7FF702093937F6618EC09E016",
    "noble_first_funding": "CD1DAADE20784BC0913A06FFD8163A3A6C9F7A7199FD0CFEA368D1C5D62EC102",
    "noble_test_cctp": "9BFBA27347715A122FF338E8CB29680F9B8F2EF5AA6A746B5307ADC7AE73DCAF",
    "noble_cctp_from_solana": "A54418B0F16DABE449A199AE7083AF2A0DD363FAC7E706912863ED5F7F733A6E",
    "noble_gas_osmosis": "60352F7BA326ABDF58629BD6C782C14D43B3356E881754808A7EAC2D95974A09",
    "noble_gas_neutron": "D18773D5DF464D2E4FAB78F8C4426435BEF0D441682A6D49C3CD8285A616C78B",
    "noble_gas_juno": "53D324AEC8ED19FE0FE0959A63C9BC4F93E1F7678E0D484AA2581CE98975AB31",
    "juno_mint": "91470D322C8C8ABE427C6E0A397880C6A61424832799F3994363A555B4C15E98",
    "juno_gas_to_minter": "C261BF88CD9A5ECEA0CD1E8999011436BF73FC6D5D7553A518EC0A72EDF3AB52",
    "juno_transfer_to_attacker": "5AA8C1274E2FC823DCD4DACDC8B951220929D5BA338BFAB57E731CAEBAB737FA",
    "neutron_sell_1": "D270A45737B051635702BA90350B22852E096DFBCDAE7120E8D10E2CDF697B20",
    "neutron_sell_2": "26C965D3627E94BB16EF26FC295E6966E6C68249028B1A2292B42DE30E3C47E2",
    "neutron_sell_3": "D04E8134D5B5DA9332544253448A340819D9B4F3A0DA8EACF8F069C31A927697",
    "neutron_return": "8629FD25187DC9B8964B1AC189EE0656A5A1C0CA3C0523EFEC0B06375F87EC19",
    "juno_return_receive": "EE99148C1D9B1853F04D560154A8D29435A9D8DFD6BA6068F31609D7DF252022",
    "osmosis_cctp_out": "0591E90876DF697008C1D68D08534DE2A7991DD4C817CE508953C8C42B73327C",
    "neutron_usdc_cctp_out": "31889BE94AB0B27E56BEF8BD5828B3C026362A9CAEBDC749D8BD926B470F4062",
}
SOL_SIG = {
    "solana_receive_proceeds": "4DrTnoj7apx7ZEwtsWX3p9jGhej5bUb7Bt7b88Ehi9XQgiBgZ3MuREp3QYptHsM1zmpSSxPq27oyAWqfUywPNuHr",
}


def _ts(tx):
    return tx["tx_response"]["timestamp"]


def c_same_key(r: Report):
    groups = bech32.cluster(list(ATT.values()))
    r.claim("C1-01", "Juno/Osmosis/Neutron/Noble attacker addresses share one 20-byte key", 1, len(groups),
            evidence=list(ATT.values()))
    r.claim("C1-01b", "Secret intermediary is a different key (coin type 529 ≠ 118, no inference)", False,
            bech32.payload_hex(INTERMEDIARY) == next(iter(groups)), evidence=[INTERMEDIARY])
    for k, v in ATT.items():
        r.ev(f"attacker {k}", v)


def c_relayer(r: Report):
    t = SECRET.tx(TX["relayer_drain"])
    m = t["tx"]["body"]["messages"][0]
    seq = int(t["tx"]["auth_info"]["signer_infos"][0]["sequence"])
    r.claim("C1-02", "Relayer wallet sends 56.102115 SCRT to a fresh address", D("56.102115"),
            micro(m["amount"][0]["amount"]), evidence=[TX["relayer_drain"], RELAYER, INTERMEDIARY])
    r.claim("C1-02b", "Relayer had signed 29,149 txs before (hot relayer key)", 29149, seq)
    r.note("C1-02c", "Drain time (UTC)", _ts(t))
    acct = SECRET.get(f"/cosmos/auth/v1beta1/accounts/{RELAYER}", valid=lambda x: "account" in x)
    r.note("C1-02d", "Relayer account sequence at fetch time (no tx signed after the drain if 29150)",
           acct["account"]["sequence"])
    r.ev("relayer drain tx (Secret)", TX["relayer_drain"])
    r.ev("project relayer wallet (Secret)", RELAYER)
    r.ev("single-use intermediary (Secret)", INTERMEDIARY)

    out = SECRET.search(f"message.sender='{INTERMEDIARY}'")
    inn = SECRET.search(f"transfer.recipient='{INTERMEDIARY}'")
    r.claim("C1-03", "Intermediary: exactly one inflow and one outflow", (1, 1),
            (len(out["tx_responses"]), len(inn["tx_responses"])), evidence=[INTERMEDIARY])
    o = out["tx_responses"][0]
    om = out["txs"][0]["body"]["messages"][0]
    memo = json.loads(om["memo"])
    final = memo["wasm"]["msg"]["swap_and_action"]["post_swap_action"]["ibc_transfer"]["ibc_info"]["receiver"]
    r.claim("C1-03b", "Outflow swaps SCRT on Osmosis with post-swap receiver = attacker Noble", ATT["noble"], final,
            evidence=[o["txhash"]])
    r.claim("C1-03c", "Outflow amount (SCRT)", D("56.097608"), micro(om["token"]["amount"]))
    gap = dt.datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")) - dt.datetime.fromisoformat(_ts(t).replace("Z", "+00:00"))
    r.claim("C1-03d", "Seconds between inflow and outflow", 106, int(gap.total_seconds()))
    r.ev("intermediary -> Osmosis swap (Secret)", o["txhash"])


def _transfers_from(tx, sender):
    tot = Decimal(0)
    for _, a in events(tx["tx_response"], "transfer"):
        if a.get("sender") == sender and a.get("amount", "").endswith("uusdc"):
            tot += micro(a["amount"][:-5])
    return tot


def c_noble(r: Report):
    f = NOBLE.tx(TX["noble_first_funding"])
    got = sum(micro(a["amount"][:-5]) for _, a in events(f["tx_response"], "transfer")
              if a.get("recipient") == ATT["noble"] and a["amount"].endswith("uusdc"))
    r.claim("C1-04", "First funding of attacker Noble address (USDC)", D("3.286220"), got,
            evidence=[TX["noble_first_funding"]])
    t = NOBLE.tx(TX["noble_test_cctp"])
    burn = cctp.decode_deposit_for_burn(t["tx"]["body"]["messages"][0])
    r.claim("C1-05", "Test CCTP burn goes to Solana token account AhT5…", SOL_TOKEN_1, burn["mint_recipient"],
            evidence=[TX["noble_test_cctp"]])
    spent = _transfers_from(t, ATT["noble"])
    r.claim("C1-05b", "Reconciliation: 3.115769 burn + 0.150451 route fee + 0.020000 tx fee = first funding",
            got, spent)
    msg = NOBLE.tx(TX["noble_cctp_from_solana"])["tx"]["body"]["messages"][0]
    d = cctp.decode_message(msg["message"])
    r.claim("C1-06", "Inbound CCTP: messageSender (who burned on Solana) = 39CA…", SOL_OWNER_1, d["message_sender"],
            evidence=[TX["noble_cctp_from_solana"]])
    r.claim("C1-06b", "Inbound CCTP mint recipient = attacker Noble", ATT["noble"], d["mint_recipient"])
    gas = sum(_transfers_from(NOBLE.tx(TX[k]), ATT["noble"]) for k in ("noble_gas_osmosis", "noble_gas_neutron", "noble_gas_juno"))
    r.claim("C1-07", "Reconciliation: three gas routes incl. fees = CCTP inflow 0.587924", micro(d["amount"]), gas,
            evidence=[TX["noble_gas_osmosis"], TX["noble_gas_neutron"], TX["noble_gas_juno"]])
    for k in ("noble_first_funding", "noble_test_cctp", "noble_cctp_from_solana", "noble_gas_osmosis",
              "noble_gas_neutron", "noble_gas_juno"):
        r.ev(k.replace("_", " ") + " (Noble)", TX[k])


def c_solana_prep(r: Report):
    sigs = sol.all_signatures(SOL_TOKEN_1)
    first = sigs[-1]
    r.note("C1-08", "First activity of token account AhT5… (account creation)",
           dt.datetime.fromtimestamp(first["blockTime"], dt.timezone.utc).isoformat(), evidence=[first["signature"]])
    burn = None
    for s in reversed(sigs):
        t = sol.tx(s["signature"])
        progs = {i.get("programId") for i in t["transaction"]["message"]["instructions"]}
        if "CCTPiPYPc6AsJuwueEnWgSgucamXDZwBd53dQ11YiKX3" in progs:
            burn = s["signature"]
            break
    deltas = sol.token_deltas(burn)
    mine = [x for x in deltas if x["account"] == SOL_TOKEN_1][0]["delta"]
    r.claim("C1-08b", "Solana wallet 39CA… itself burns 0.607924 USDC via CCTP (= 0.587924 + 0.02 fee)",
            D("-0.607924"), mine, evidence=[burn])
    r.claim("C1-08c", "Fee payer / signer of that burn", SOL_OWNER_1, sol.fee_payer(burn))
    r.ev("Solana burn back to Noble (signed by 39CA…)", burn)
    r.ev("Solana owner wallet (proceeds #1)", SOL_OWNER_1)
    r.ev("Solana USDC token account (proceeds #1)", SOL_TOKEN_1)


def c_theft(r: Report):
    m = JUNO.tx(TX["juno_mint"])
    w = [a for _, a in events(m["tx_response"], "wasm") if a.get("action") == "mint"][0]
    r.claim("C1-09", "Unauthorized mint of 30,000 PHMN by the minter to itself", D(30000), micro(w["amount"]),
            evidence=[TX["juno_mint"]])
    r.claim("C1-09b", "Mint signer = PHMN minter address", MINTER, m["tx"]["body"]["messages"][0]["sender"])
    r.note("C1-09c", "Mint time", _ts(m))
    t = JUNO.tx(TX["juno_transfer_to_attacker"])
    w = [a for _, a in events(t["tx_response"], "wasm") if a.get("action") == "transfer"][0]
    r.claim("C1-10", "Minter transfers 30,000 PHMN to attacker", (D(30000), ATT["juno"]), (micro(w["amount"]), w["to"]),
            evidence=[TX["juno_transfer_to_attacker"]])
    r.claim("C1-10b", "Transfer memo is the project's own stakedrop tool template", True,
            "StakeDrop from" in t["tx"]["body"]["memo"])
    s = JUNO.search(f"message.sender='{ATT['juno']}'")
    sends = []
    for tt, rr in zip(s["txs"], s["tx_responses"]):
        msg = tt["body"]["messages"][0]
        if "send" in (msg.get("msg") or {}):
            sends.append((rr["txhash"], micro(msg["msg"]["send"]["amount"]), rr["timestamp"]))
    r.claim("C1-11", "Attacker sends 12,000 / 12,000 / 3,000 PHMN out of Juno over IBC",
            [D(12000), D(12000), D(3000)], [x[1] for x in sends], evidence=[x[0] for x in sends])
    for h, a, ts in sends:
        r.ev(f"Juno IBC send {a} PHMN @ {ts}", h)
    sold = Decimal(0)
    for k in ("neutron_sell_1", "neutron_sell_2", "neutron_sell_3"):
        tx = NEUTRON.tx(TX[k])
        sold += sum(micro(a["return_amount"]) for _, a in events(tx["tx_response"], "wasm") if a.get("action") == "swap")
        r.ev(f"{k.replace('_', ' ')} (Neutron)", TX[k])
    r.claim("C1-12", "Neutron sales 1,000 + 1,000 + 900 PHMN return (USDC)", D("3546.992876"), sold,
            evidence=[TX["neutron_sell_1"], TX["neutron_sell_2"], TX["neutron_sell_3"]])
    ret = NEUTRON.tx(TX["neutron_return"])
    r.claim("C1-13", "Unsold PHMN returned Neutron -> Juno", D(12100),
            micro(ret["tx"]["body"]["messages"][0]["token"]["amount"]), evidence=[TX["neutron_return"], TX["juno_return_receive"]])
    r.claim("C1-13b", "Return time (resolves 10:04:40 vs 10:12 discrepancy)", "2026-06-10T10:04:40Z", _ts(ret))
    q = base64.b64encode(json.dumps({"balance": {"address": ATT["juno"]}}).encode()).decode()
    bal = JUNO.get(f"/cosmwasm/wasm/v1/contract/{PHMN}/smart/{q}", valid=lambda x: "data" in x)
    r.claim("C1-14", "Attacker Juno still holds 30,000 − 12,000 − 15,000 + 12,100 = 15,100 PHMN",
            D(15100), micro(bal["data"]["balance"]), evidence=[ATT["juno"], PHMN])
    for k in ("juno_mint", "juno_gas_to_minter", "juno_transfer_to_attacker", "neutron_return", "juno_return_receive"):
        r.ev(k.replace("_", " "), TX[k])
    r.ev("PHMN cw20 contract (Juno)", PHMN)
    r.ev("PHMN minter address (Juno)", MINTER)


def _receiver(deltas):
    """The token account credited in a transfer (first positive delta)."""
    return next(y for y in deltas if y["delta"] > 0)


def _outflows(token_account: str, min_usdc: int = 100) -> list[dict]:
    """Chronological USDC outflows of at least ``min_usdc`` from a token account."""
    outs = []
    for s in reversed(sol.all_signatures(token_account)):
        deltas = sol.token_deltas(s["signature"])
        mine = [y for y in deltas if y["account"] == token_account and y["delta"] <= -min_usdc]
        if mine:
            rec = _receiver(deltas)
            outs.append({"sig": s["signature"], "amount": -mine[0]["delta"], "to_account": rec["account"],
                         "to_owner": rec["owner"], "time": sol.block_time(s["signature"])})
    return outs


def _sweep(o: dict):
    """First onward transfer of (at least) the deposited amount after the deposit:
    (destination owner, minutes after deposit, signature), or None."""
    deposited = int(o["time"].timestamp())
    for s in reversed(sol.signatures(o["to_account"], 30)):
        if s["blockTime"] <= deposited:
            continue
        deltas = sol.token_deltas(s["signature"])
        if any(y["account"] == o["to_account"] and y["delta"] <= -o["amount"] + 1 for y in deltas):
            return _receiver(deltas)["owner"], (s["blockTime"] - deposited) / 60, s["signature"]
    return None


def c_solana_proceeds(r: Report):
    d = sol.token_deltas(SOL_SIG["solana_receive_proceeds"])
    got = [x for x in d if x["account"] == SOL_TOKEN_1][0]["delta"]
    r.claim("C1-15", "Osmosis proceeds arrive on Solana via CCTP (USDC)", D("8953.646449"), got,
            evidence=[TX["osmosis_cctp_out"], SOL_SIG["solana_receive_proceeds"]])
    r.ev("Osmosis -> Noble -> Solana CCTP (Osmosis)", TX["osmosis_cctp_out"])
    r.ev("Solana receive of proceeds", SOL_SIG["solana_receive_proceeds"])
    # cash-out
    outs = _outflows(SOL_TOKEN_1)
    r.claim("C1-16", "Cash-out from AhT5… in ~1,000 USDC chunks (count)", 9, len(outs),
            evidence=[o["sig"] for o in outs])
    r.claim("C1-16b", "Cash-out total (USDC)", D(8952), sum(o["amount"] for o in outs))
    sweep_targets, sweeps = {}, []
    for i, o in enumerate(outs):
        r.ev(f"cash-out #{i+1} {o['amount']} USDC {o['time']:%Y-%m-%d %H:%M}", o["sig"])
        r.ev(f"cash-out #{i+1} receiving token account (owner {o['to_owner']})", o["to_account"])
        sweeps.append(sw := _sweep(o))
        if sw:
            dest, mins, sig = sw
            sweep_targets.setdefault(dest, []).append(round(mins, 1))
            r.ev(f"cash-out #{i+1} moved on to {dest} after {mins:.1f} min", sig)
    fast = {k: v for k, v in sweep_targets.items() if all(m <= 5 for m in v)}
    r.claim("C1-17", "Receiving accounts swept to a common hot wallet within 5 minutes (count of 9)", 8,
            sum(len(v) for v in fast.values()))
    r.claim("C1-17b", "Distinct fast-sweep hot wallets (deposit-address pattern)", 3, len(fast))
    r.note("C1-17c", "Sweep hot wallets -> minutes after deposit", json.dumps(sweep_targets))
    r.claim("C1-17d", "Main-proceeds USDC swept into KuCoin-labelled hot wallets (Solscan labels)", D(5952),
            sum(o["amount"] for o, sw in zip(outs, sweeps) if sw and sw[0] in KUCOIN_HOT and sw[1] <= 5))
    # Neutron proceeds, second Solana wallet
    t = NEUTRON.tx(TX["neutron_usdc_cctp_out"])
    m = t["tx"]["body"]["messages"][0]
    dec = cctp.decode_orbiter_memo(json.loads(m["memo"]))
    owner2 = sol.token_account_owner(dec["mint_recipient"])
    r.claim("C1-18", "Neutron proceeds 3,546.992876 USDC bridged on 22 Jun via Noble Orbiter CCTP",
            D("3546.992876"), micro(m["token"]["amount"]), evidence=[TX["neutron_usdc_cctp_out"]])
    r.note("C1-18b", "Destination Solana token account / owner", f"{dec['mint_recipient']} / {owner2}")
    outs2 = _outflows(dec["mint_recipient"])
    r.claim("C1-19", "Wallet #2 cash-out chunks (1,000 / 1,000 / 1,000 / 546 USDC)",
            [D(1000), D(1000), D(1000), D(546)], [o["amount"] for o in outs2], evidence=[o["sig"] for o in outs2])
    r.note("C1-19b", "Wallet #2 cash-out window",
           f"{outs2[0]['time']:%Y-%m-%d %H:%M} → {outs2[-1]['time']:%Y-%m-%d %H:%M} UTC")
    sweeps2 = []
    for o in outs2:
        r.ev(f"wallet #2 cash-out {o['amount']} USDC {o['time']:%Y-%m-%d %H:%M} to owner {o['to_owner']}", o["sig"])
        sweeps2.append(sw := _sweep(o))
        if sw:
            r.ev(f"wallet #2 recipient {o['to_owner']} moved on to {sw[0]} after {sw[1]:.1f} min", sw[2])
    fast2 = [(o, sw) for o, sw in zip(outs2, sweeps2) if sw and sw[1] <= 5]
    r.claim("C1-19c", "Wallet #2 recipients swept within 5 minutes (count of 4)", 3, len(fast2),
            evidence=[sw[2] for _, sw in fast2])
    r.claim("C1-19d", "Their sweep destination = a fast-sweep hot wallet of the main proceeds (C1-17b)",
            ["AzNEZxmBdy5mX3sjJanZ8FFDxJwiH9mm2SksgtBkUWwe"],
            sorted({sw[0] for _, sw in fast2} & set(fast)))
    r.claim("C1-19e", "Wallet #2 USDC swept into KuCoin-labelled hot wallets (Solscan labels)", D(2546),
            sum(o["amount"] for o, sw in fast2 if sw[0] in KUCOIN_HOT))
    slow2 = [(o, sw) for o, sw in zip(outs2, sweeps2) if sw and sw[1] > 5]
    slow1 = [sw[0] for sw in sweeps if sw and sw[1] > 5]
    r.claim("C1-19f", "The unswept wallet #2 recipient forwards to the same collector as main-proceeds recipient #7",
            slow1, [sw[0] for _, sw in slow2], evidence=[sw[2] for _, sw in slow2])
    r.note("C1-19g", "Wallet #2 recipients -> destination, minutes after deposit",
           json.dumps([[o["to_owner"], sw[0], round(sw[1], 1)] if sw else [o["to_owner"], None, None]
                       for o, sw in zip(outs2, sweeps2)]))
    r.ev("Neutron USDC -> Solana CCTP (Neutron)", TX["neutron_usdc_cctp_out"])
    r.ev("Solana token account (proceeds #2)", dec["mint_recipient"])
    r.ev("Solana owner wallet (proceeds #2)", owner2)


def main():
    r = Report(HERE, "Case 01 — Unauthorized PHMN mint")
    for fn in (c_same_key, c_relayer, c_noble, c_solana_prep, c_theft, c_solana_proceeds):
        r.run(fn)
    return r.write()


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
