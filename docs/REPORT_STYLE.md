# Report style

How a case write-up (`cases/NN-slug/README.md`) is written, so that every case reads the same way no matter who drafts it or when. Start from [CASE_TEMPLATE.md](CASE_TEMPLATE.md).

Rules marked **[lint]** are checked by `python -m tools.casedoc lint`, which `python verify.py` and CI run on every case. A write-up that breaks one fails the build, the same way a wrong number does. The other rules are for the author and the reviewer.

## 1. Structure

- **[lint]** Sections and their order are fixed. Required: TL;DR, Case card, Addresses, My role, How it unfolded, False leads resolved, Containment and recovery, Risk scoring, Confidence assessment, Limitations, Open leads, Lessons learned, Appendix: key references. Optional, in their place in the template: What this analysis adds (after the case card), Objectives, Background, Methodology and tools. No other `##` headings.
- **[lint]** A heading may add a subtitle after the section name, e.g. `## Background: why this was possible` or `## What this analysis adds to Chainflip's report`.
- **[lint]** The title is `# Case NN: <what happened> (<the notable number or mechanism>)`, with NN equal to the folder number.
- **[lint]** A case still being written is marked `# [DRAFT] Case NN: ...`. Its row in the Cases table of the root README is marked the same way, `[[DRAFT] Case NN: ...](cases/NN-slug/)`, and the label is removed from both places together when the case is finished. Checks, reports and every other rule apply to a draft as to a finished case.
- **[lint]** The header note before TL;DR has a Sources (or Anonymization) paragraph and a Reproducibility paragraph that links `reports/verification.md` and `reports/risk.md`.
- **[lint]** Steps in "How it unfolded" are `### 1.`, `### 2.`, … in chronological order. Put the time range in the heading in parentheses: `### 3. The doubling loop (01:56 to 03:10)`.
- A section with nothing to report stays and says so in one sentence, with what was checked. "No false leads: the funding path has a single source, checked in C9-04" is a finding. A missing section is not.
- Each false lead lives in "False leads, resolved", not inside a step. A step may say "see False leads, 1".
- Containment, recovery and the final outcome table live in "Containment and recovery", not in the chronology.

## 2. Fixed tables

- **[lint]** Case card rows, exactly in this order: Dates, Chains, Assets, Loss, Outcome, My role, Checks. The Checks cell starts with the number of passed checks in `reports/verification.md`.
- **[lint]** Addresses is a `| Role | Address |` table. Role says what the address is and, for non-attacker addresses, adds "(victim)", "(infrastructure)" or "(service)". Same-key forms go on one row, separated by ` / `.
- **[lint]** Confidence assessment is a `| Level | Statement |` table with levels in this order: Proven, Strong, Moderate, Suspicion, Not established. Proven is required; leave out a level that has nothing.
- **[lint]** The appendix is an `| Event | Chain | Reference |` table of key hashes. The complete evidence index stays in `reports/verification.md`.
- The Risk scoring section shows an excerpt of `reports/risk.md`: `| Score | Band | Address | Main reasons |`, sorted by score, with infrastructure and resolved rows last.

## 3. Proof levels

Use one vocabulary everywhere: in the confidence table, in prose and in the risk model.

| Level | Means | Typical evidence |
|---|---|---|
| Proven | Follows from chain data alone; a check recomputes it. | Signer, same 20-byte key, decoded memo or `messageSender`, exact reconciliation |
| Strong | Several independent indicators agree; nothing contradicts them. | Public exchange label plus sweep pattern; file artifact plus tx memo |
| Moderate | One indicator or a behavioural pattern without a label. | Same chunking and timing; service-like hot wallet without a label |
| Suspicion | A hypothesis worth recording. Say what would confirm or kill it. | Access overlap; vote that looks bought |
| Not established | What the data cannot show. | Who typed the commands; source behind a privacy layer |

- A fund-flow edge on its own is a lead, not attribution. Write "received 1,000 USDC from the attacker", not "an accomplice".
- **Infrastructure is not an owner.** Bridges, IBC adapters, CCTP module accounts, THORChain vaults, mixer pools, AMM pools and the victim's own deposit channels are classified before any edge is drawn, and are never called a "hub" or a "funder".
- Labels from explorers or commercial tools are cited with their source and the date they were checked: "Solscan public label, checked 31 Oct 2026".

## 4. Numbers, dates, addresses

- **Time** is always UTC. Write `01:44:27` in tables and `01:44` in prose and diagrams (`01.44` inside a Mermaid `timeline`, see section 5). Name the zone once per section ("(UTC)" in a table header or step heading).
- **Dates:** `12 Sep 2026` the first time in a section, `12 Sep` after that. Ranges: `18-23 June` within a month, `11 Sep 19:44 to 12 Sep 01:25` across days.
- **Amounts:** number, space, ticker: `56.102115 SCRT`. Thousands with commas. Keep full chain precision when the figure is reconciled to the micro-unit; otherwise round and say "about". USD as `$6.24M`, `$20k`, and state the price basis once, in the header note or the case card.
- **Percentages:** `84.7 %`.
- **Every figure that a check recomputes carries its check ID** in parentheses at the end of the sentence or table cell: `(C3-02)`, `(C2-06, C2-06b)`, `(C3-12 to C3-16)`. **[lint]** Every cited ID exists in `reports/verification.md`, and a case cites only its own IDs.
- **Addresses and hashes:** full and in backticks in tables and at their first mention in prose. Later in the same section a short form is fine: `0x9c7a…4697`, `TWSe9…o2BZ`, `noble1pqard…`. Never shorten an address in the Addresses table or a hash in the appendix.
- No numbers from explorer screenshots. If a figure cannot be recomputed (pruned node, off-chain source), say where it comes from.

## 5. Diagrams

GitHub renders Mermaid in Markdown, so diagrams live in the write-up as text and are reviewed like text.

- **[lint]** "How it unfolded" opens with two diagrams, before step 1:
  - a `flowchart LR` of the money flow, curated: 8 to 20 nodes, the path a reader must understand;
  - a `timeline` (or `gantt` when durations matter) of the incident, with one `section` per phase.
- **[lint]** Allowed diagram types: `flowchart`, `sequenceDiagram`, `timeline`, `gantt`, `pie`, `xychart-beta`.
- Optional diagrams, placed in the step or section they explain:
  - `sequenceDiagram` for a protocol mechanism (who signs, who submits, who pays);
  - `gantt` for off-chain sessions against on-chain events;
  - `pie` for an outcome split (contained, recovered, lost);
  - `xychart-beta` for amounts per round or per day.
- **Node labels:** `Role<br/>short…addr`. **Edge labels:** `amount asset`, then the date if the diagram spans several days. Solid arrows move value; dotted arrows (`-.->`) are gas, swaps inside infrastructure and recovered funds.
- Write the sentence "Short labels in the diagrams; full addresses are in the Addresses table." once, above the diagrams, and link [reports/graph.md](reports/graph.md).
- **The full graph is generated.** `reports/graph.md` is written by `python -m tools.diagrams` from `graph.json`, with node colours taken from the risk bands. Never edit it by hand. **[lint]** Risk scoring links it, and it must exist for every case with a `graph.json`.
- **[lint]** Mermaid's `timeline` rejects a colon anywhere in a period or an event, so times there are written with a dot: `12 Sep : 01.44 probe deposit`. Everywhere else times keep the colon.
- Mermaid pitfalls: Do not use `#` or `"` inside a label (`#35;` and `#quot;` if unavoidable). Do not use `;` inside `sequenceDiagram` messages.

## 6. Wording

- English, plain, one fact per sentence. Lead with the finding, then the evidence.
- First person for my own work ("I traced", "my own analysis"), and say plainly what others did.
- No em dashes. Use a colon, a full stop or "to" for ranges.
- Bold only the lead-in of a bullet or paragraph, never a whole sentence.
- TL;DR: one sentence that states date, victim, amount and mechanism, then three to six bullets.
- Lessons learned: one lesson per bullet, addressed to a reader who can act on it ("For protocol teams:", "For investigators:").

## 7. Privacy

- Client cases: off-chain identifiers (IP addresses, SSH key fingerprints, hostnames, names of people and companies) are replaced with labels such as K2. Clients gave consent to publish but are never named; whoever needs to can find them from the hashes.
- No insider attribution in public. A suspect hypothesis is recorded as "handed to the client", with the evidence class it rests on, never with a name.
- On-chain data is public and given in full. Raw cached transactions keep their memos exactly as on chain.

## 8. Before a case is done

```bash
python verify.py NN
```

That runs the case's checks, rewrites `reports/verification.md`, `reports/risk.md` and `reports/graph.md`, and lints the write-up. Then read `git diff -- cases/NN-slug/reports/`: a change there that the text does not explain is a bug in one of them.
