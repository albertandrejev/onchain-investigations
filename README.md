# Crypto investigations portfolio

[![verify](https://github.com/OWNER/REPO/actions/workflows/verify.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/verify.yml)

On-chain incident investigations written up as case studies, plus the Python
toolkit that recomputes every number in them from raw chain data rather than
from block-explorer screenshots. You can clone the repository, run one command
and check the claims yourself.

## In 60 seconds (for recruiters and hiring managers)

I am Albert Andrejev, an on-chain investigator and AML analyst. I come from validator operations in the Cosmos ecosystem and work across IBC, CosmWasm, Circle CCTP, Solana and Ethereum.

This repository shows how I work:

- I trace funds across chains and bridges, from the attacker's first gas payment to exchange deposit addresses, and name the points where funds can be frozen or KYC data requested. Case 01 covers six chains and three bridge types.
- I keep proof levels apart. Each case separates proven facts from strong, moderate and suspicion-level statements, records the false leads and how they were resolved, and never treats infrastructure as an owner.
- My numbers can be checked. 69 automated checks tie each figure in the write-ups to a transaction hash and recompute it from raw node responses. They have no dependencies and run offline.
- My risk scores can be defended. Every point comes from a named rule with a written reason.

Start with [Case 01](cases/case-01-unauthorized-mint-juno.md) (tracing and server forensics for a client), then [Case 02](cases/case-02-neutron-governance-attack.md) (a $6.2M governance attack, public investigation), then run `python verify.py`.

## Cases

| Case | What happened | My role | Chains | Checks |
|---|---|---|---|---|
| [Case 01: Unauthorized token mint](cases/case-01-unauthorized-mint-juno.md) | Attacker with access to two project servers drains the project's IBC relayer wallet to fund the operation, mints 30,000 tokens with a compromised minter key, sells half, bridges to Solana via CCTP and cashes out through exchange deposit addresses. | Lead investigator: on-chain tracing, server-log correlation, evidence package for law enforcement. | Juno, Osmosis, Neutron, Noble, Secret, Solana | 32 |
| [Case 02: Neutron governance takeover](cases/case-02-neutron-governance-attack.md) | $20k of NTRN bought 11 minutes before a vote closed passes a proposal that hands 11 DeFi contracts to the attacker; $6.24M drained, 64 % secured by halts and an IBC rate limiter. | Community investigator: found the last-minute delegation and the malicious proposal; quorum analysis, exit-route tracing, re-verification. | Neutron, Cosmos Hub, Noble, Secret, dYdX, THORChain, Ethereum | 37 |

Off-chain identifiers from the client engagement (IP addresses, key fingerprints, people, companies) are not in this repository. On-chain data is public and given in full.

## Quick start

Requires Python 3.10+. Standard library only, no `pip install`.

```bash
python verify.py
```

That runs, offline, from the committed raw-data snapshot:

1. an integrity check of `data/cache/` against `data/cache/MANIFEST.sha256`;
2. the unit tests (BIP-173 vectors, CCTP decoding, risk-model invariants);
3. the 32 + 37 case checks, each printing the value stated in the write-up next to the value recomputed from chain data;
4. the risk scoring for both incident graphs.

Outputs, committed so they can be read on GitHub:

- `reports/verification-case01.md`, `reports/verification-case02.md`: every claim with expected value, recomputed value, PASS/FAIL, and an evidence index of full tx hashes and addresses.
- `reports/risk-case01.md`, `reports/risk-case02.md`: address risk scores with per-rule reasons.

### Re-fetching from public nodes

```bash
python verify.py --refresh    # fetch everything again into data/cache.refresh and run the checks against it
python verify.py --promote    # adopt that snapshot as data/cache and rewrite the manifest
```

The committed snapshot is never deleted by `--refresh`, so a pruned or offline public node cannot destroy the data the write-ups were verified against. Checks that compare against *current* state (balances, nonces) are expected to change when the attacker moves funds; that is the point of re-running them.

## Tools

| Module | What it does | CLI example |
|---|---|---|
| `tools/bech32.py` | BIP-173 bech32 decode/encode; same-key clustering across Cosmos chains (identical 20-byte payload = same keyholder). Contracts and module accounts (32-byte) are excluded. | `python -m tools.bech32 cluster juno1pqardc39d558mr58nx5m2wgmy448pv94ehdea0 noble1pqardc39d558mr58nx5m2wgmy448pv948xm2za` |
| `tools/cctp.py` | Circle CCTP decoder: outbound `MsgDepositForBurn` (destination chain + recipient in native format), inbound `MsgReceiveMessage` (`messageSender`, i.e. who burned on the source chain), Noble Orbiter memos. | `python -m tools.cctp tx A54418B0F16DABE449A199AE7083AF2A0DD363FAC7E706912863ED5F7F733A6E` |
| `tools/net.py` | Cosmos REST client with endpoint fallback (known archive nodes, then the cosmos.directory registry), historical queries via `x-cosmos-block-height`, Tendermint RPC, Solana and Ethereum JSON-RPC. Every raw response is cached by request, so results are reproducible. | used by the checks |
| `tools/solana_util.py` | SPL token balance deltas per transaction, signature paging, token-account owners. | used by the checks |
| `tools/manifest.py` | SHA-256 manifest of the raw-data cache; snapshot timestamp. | `python -m tools.manifest verify` |
| `checks/case01.py`, `checks/case02.py` | **Amount reconciliation and claim checks**: inflows = outflows + fees to the micro-unit, quorum / tally arithmetic at a historical height, sweep timing of deposit addresses, halt windows from block timestamps, etc. | `python -m checks.case01` |
| `risk/model.py`, `risk/score.py` | **Risk scoring**: transparent rules (seed, same-key, direct/propagated exposure, single-use intermediary, privacy-layer funding, structuring, dormant accumulation, governance late-stake typology). Entity classes for services (exposure + freeze/KYC action) and infrastructure (never scored). Resolutions (victims, false leads) are recorded explicitly. | `python -m risk.score case02` |
| `tests/` | Unit tests: BIP-173 vectors, cross-chain conversion, CCTP decoding, risk-model invariants. | `python -m unittest discover -s tests -t .` |

## Design principles

- **Numbers come from raw data.** Explorers are used to look, never as the source of a figure.
- **Infrastructure is not an owner.** IBC adapters, CCTP module accounts, THORChain vaults and AMM pools are classified before any edge is drawn. Case 01 shows how treating an adapter as a "funding hub" produces false links.
- **Proof tiers.** Each case separates proven, strong, moderate and suspicion-level statements, and records resolved false leads.
- **Pinned evidence.** The raw responses the checks read are committed and hashed; the reports state the snapshot time. Anyone can re-fetch and diff.
- **Privacy.** Off-chain identifiers from the server forensics are not here. Raw cached transactions contain on-chain memos exactly as they appear on chain.

## Layout

```
cases/       case write-ups (Markdown, Mermaid diagrams)
tools/       reusable decoders and data clients
checks/      per-case claim verification
risk/        risk-scoring model + CLI
graphs/      incident graphs (nodes, edges with cited txs) used for scoring
reports/     generated verification and risk reports
data/cache/  raw API responses + MANIFEST.sha256 (reproducible offline runs)
tests/       unit tests
verify.py    one-command runner
```

## License

Code: MIT. Write-ups and reports: CC BY 4.0. See `LICENSE` and `LICENSE-CONTENT.md`.
