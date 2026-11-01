# On-chain investigations

[![verify](https://github.com/albertandrejev/onchain-investigations/actions/workflows/verify.yml/badge.svg)](https://github.com/albertandrejev/onchain-investigations/actions/workflows/verify.yml)

On-chain incident investigations written up as case studies, plus the Python
toolkit that recomputes every number in them from raw chain data rather than
from block-explorer screenshots. You can clone the repository, run one command
and check the claims yourself.

## In 60 seconds (for recruiters and hiring managers)

I am Albert Andrejev, an on-chain investigator and AML analyst. I come from validator operations in the Cosmos ecosystem and DeFi protocol development across IBC, CosmWasm, Circle CCTP, Solana and Ethereum.

This repository shows how I work:

- I trace funds across chains and bridges, from the attacker's first gas payment to exchange deposit addresses, and name the points where funds can be frozen or KYC data requested. Case 01 covers six chains and three bridge types; case 03 follows an exploit from Tornado Cash through Tron and THORChain to Bitcoin.
- I keep proof levels apart. Each case separates proven facts from strong, moderate and suspicion-level statements, records the false leads and how they were resolved, and never treats infrastructure as an owner.
- My numbers can be checked. 109 automated checks tie each figure in the write-ups to a transaction hash and recompute it from raw node responses. They have no dependencies and run offline.
- My risk scores can be defended. Every point comes from a named rule with a written reason.

Start with [Case 01](cases/01-unauthorized-mint-juno/) (tracing and server forensics for a client), then [Case 02](cases/02-neutron-governance-attack/) (a $6.2M governance attack, public investigation) and [Case 03](cases/03-chainflip-tron-duplicate-payouts/) (an exploit the victim protocol described without a single address), then run `python verify.py`.

## Cases

| Case | What happened | My role | Chains | Checks |
|---|---|---|---|---|
| [Case 01: Unauthorized token mint](cases/01-unauthorized-mint-juno/) | Attacker with access to two project servers drains the project's IBC relayer wallet to fund the operation, mints 30,000 tokens with a compromised minter key, sells half, bridges to Solana via CCTP and cashes out through KuCoin deposit addresses (Solscan labels). | Lead investigator: on-chain tracing, server-log correlation, evidence package for law enforcement. | Juno, Osmosis, Neutron, Noble, Secret, Solana | 37 |
| [Case 02: Neutron governance takeover](cases/02-neutron-governance-attack/) | $20k of NTRN bought 11 minutes before a vote closed passes a proposal that hands 11 DeFi contracts to the attacker; $6.24M drained, 64 % secured by halts and an IBC rate limiter. | Community investigator: found the last-minute delegation and the malicious proposal; quorum analysis, exit-route tracing, re-verification. | Neutron, Cosmos Hub, Noble, Secret, dYdX, THORChain, Ethereum | 37 |
| [[DRAFT] Case 03: Chainflip on Tron](cases/03-chainflip-tron-duplicate-payouts/) | A registered liquidity provider re-submits Chainflip's signed fetch calls with its own memo; each is refunded on top of the normal withdrawal. 736,442 USDT taken in six doubling rounds, swapped to Bitcoin through THORChain within ten minutes. | Independent investigator: blind trace that reproduces every figure in Chainflip's report and adds what it does not publish: addresses, the mechanism in the payloads, the Tornado-funded operator and the Bitcoin trail. | Tron, Ethereum, THORChain, Bitcoin, Chainflip State Chain | 35 |

Off-chain identifiers from the client engagement (IP addresses, key fingerprints, people, companies) are not in this repository. On-chain data is public and given in full.

## Quick start

Requires Python 3.10+. Standard library only, no `pip install`.

```bash
python verify.py
```

That runs, offline, from the committed raw-data snapshots:

1. the unit tests (BIP-173 vectors, CCTP, Tron and Chainflip decoding, risk-model invariants, write-up lint and diagrams);
2. for each case, an integrity check of its `data/cache/` against `data/cache/MANIFEST.sha256`, then its checks, each printing the value stated in the write-up next to the value recomputed from chain data (37 + 37 + 35);
3. the risk scoring for every incident graph, and the incident-graph diagram drawn from the same scores;
4. the structure lint of every write-up against [docs/REPORT_STYLE.md](docs/REPORT_STYLE.md): sections and their order, the fixed tables, the diagrams, and that every cited check ID exists.

Outputs, committed so they can be read on GitHub, sit in each case folder:

- `reports/verification.md`: every claim with expected value, recomputed value, PASS/FAIL, and an evidence index of full tx hashes and addresses.
- `reports/risk.md`: address risk scores with per-rule reasons.
- `reports/graph.md`: the whole incident graph as a Mermaid diagram, nodes coloured by risk band.

`python verify.py 03` limits any mode to one case.

### Re-fetching from public nodes

```bash
python verify.py --refresh    # fetch everything again into each case's data/cache.refresh and run the checks against it
python verify.py --promote    # adopt those snapshots as data/cache and rewrite the manifests
```

The committed snapshot is never deleted by `--refresh`, so a pruned or offline public node cannot destroy the data the write-ups were verified against. Checks that compare against *current* state (balances, nonces, freeze lists) are expected to change when the attacker moves funds; that is the point of re-running them. For case 03 set `TRONGRID_API_KEY` first: TronGrid rate-limits hard without a key, which is sent only as a header and never written to the cache.

## Tools

| Module | What it does | CLI example |
|---|---|---|
| `tools/bech32.py` | BIP-173 bech32 decode/encode; same-key clustering across Cosmos chains (identical 20-byte payload = same keyholder). Contracts and module accounts (32-byte) are excluded. | `python -m tools.bech32 cluster juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0 noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za` |
| `tools/cctp.py` | Circle CCTP decoder: outbound `MsgDepositForBurn` (destination chain + recipient in native format), inbound `MsgReceiveMessage` (`messageSender`, i.e. who burned on the source chain), Noble Orbiter memos. | `python -m tools.cctp tx A54418B0F16DABE449A199AE7083AF2A0DD363FAC7E706912863ED5F7F733A6E` |
| `tools/net.py` | Cosmos REST client with endpoint fallback (known archive nodes, then the cosmos.directory registry), historical queries via `x-cosmos-block-height`, Tendermint RPC, Solana and Ethereum JSON-RPC. Every raw response is cached by request, so results are reproducible. | used by the checks |
| `tools/solana_util.py` | SPL token balance deltas per transaction, signature paging, token-account owners. | used by the checks |
| `tools/tron.py` | TronGrid client with paging and 429 back-off; base58check codec; TRC-20 history; contract creator; call decoder (signer, contract, selector, memo); Tether `isBlackListed()`; THORNode `tx/status` and mempool.space lookups. | `python -m tools.tron note cefb680d89954ec143ad27b55231e3537bf460efd72eb41657c8c0df372e71b0` |
| `tools/chainflip.py` | Chainflip vault-swap memo decoder (SCALE), Vault `allBatch` signature words, SS58 account ids, cached State Chain RPC. | `python -m tools.chainflip account cFMKZx5J8NkiJ6JxHatodMRumCnzvmVtF62FGWMnWcspg58bs` |
| `tools/manifest.py` | SHA-256 manifest of a raw-data cache; snapshot timestamp. | `python -m tools.manifest verify cases/01-unauthorized-mint-juno/data/cache` |
| `tools/claims.py` | The claim framework the case checks use: expected vs recomputed value, evidence, Markdown report. | used by the checks |
| `tools/diagrams.py` | Writes `reports/graph.md` from `graph.json`: every node and cited edge as Mermaid, coloured by the risk band, same-key addresses boxed together, infrastructure edges dashed. | `python -m tools.diagrams cases/02-neutron-governance-attack` |
| `tools/casedoc.py` | Structure lint for write-ups: required sections in order, case card, address and confidence tables, opening diagrams, links to the reports, cited check IDs. | `python -m tools.casedoc lint` |
| `cases/*/checks.py` | **Amount reconciliation and claim checks** per case: inflows = outflows + fees to the micro-unit, quorum and tally arithmetic at a historical height, sweep timing, memo decoding, signature and nonce checks, etc. | `python cases/03-chainflip-tron-duplicate-payouts/checks.py` |
| `risk/model.py`, `risk/score.py` | **Risk scoring**: transparent rules (seed, same-key, direct/propagated exposure, single-use intermediary, full-value pass-through, privacy-layer funding, structuring, dormant accumulation, governance late-stake typology). Entity classes for services (exposure + freeze/KYC action) and infrastructure (never scored). Resolutions (victims, false leads) are recorded explicitly. | `python -m risk.score cases/02-neutron-governance-attack` |
| `tests/` | Unit tests: BIP-173 vectors, cross-chain conversion, CCTP, Tron and Chainflip decoding, risk-model invariants. | `python -m unittest discover -s tests -t .` |

## Design principles

- **Numbers come from raw data.** Explorers are used to look, never as the source of a figure.
- **Infrastructure is not an owner.** IBC adapters, CCTP module accounts, THORChain vaults, mixer pools and AMM pools are classified before any edge is drawn. Case 01 shows how treating an adapter as a "funding hub" produces false links.
- **Proof tiers.** Each case separates proven, strong, moderate and suspicion-level statements, and records resolved false leads.
- **One shape for every case.** Write-ups follow [docs/CASE_TEMPLATE.md](docs/CASE_TEMPLATE.md) and [docs/REPORT_STYLE.md](docs/REPORT_STYLE.md), and the lint holds them to it. Each opens its chronology with a money-flow diagram and a timeline.
- **Pinned evidence.** The raw responses the checks read are committed and hashed; the reports state the snapshot time. Anyone can re-fetch and diff.
- **Privacy.** Off-chain identifiers from the server forensics are not here. Raw cached transactions contain on-chain memos exactly as they appear on chain.

## Layout

```
cases/
  01-unauthorized-mint-juno/
    README.md          the write-up (GitHub shows it when the folder is opened)
    checks.py          claim verification for this case
    graph.json         incident graph (nodes, edges with cited txs) used for scoring
    reports/           generated verification.md, risk.md and graph.md
    data/cache/        raw API responses + MANIFEST.sha256 (offline, reproducible)
  02-neutron-governance-attack/
  03-chainflip-tron-duplicate-payouts/
docs/        CASE_TEMPLATE.md (start a write-up here), REPORT_STYLE.md (the rules)
tools/       reusable decoders, data clients, claim framework, diagrams, write-up lint
risk/        risk-scoring model + CLI
tests/       unit tests
verify.py    one-command runner
```

A new case is a new folder with the same files, its README copied from `docs/CASE_TEMPLATE.md`; `verify.py`, `risk.score`, `tools.diagrams` and the lint pick it up automatically.

## License

Code: MIT. Write-ups and reports: CC BY 4.0. See `LICENSE` and `LICENSE-CONTENT.md`.
