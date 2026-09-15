# Submission - ContributionCourt

**Evidence-based rewards for meaningful community work.**

A standalone GenLayer Intelligent Contract that evaluates DAO and community
contributions against a campaign specification fixed before any submission, and
pays the reward the specification sets from a funded GEN pool. Validators agree
on what the work is; code decides what it earns.

**Repository** - https://github.com/Olawalter/ContributorCourt

**StudioNet address** - `0x0f47E6A49845c983fa9B61E441928F3435E9Adde`

**Explorer** - https://explorer-studio.genlayer.com/address/0x0f47E6A49845c983fa9B61E441928F3435E9Adde

**Deployment transaction** - `0x43bb908c8d56e1a52561cb6191757dfb74a57511a7398109a930431356be2d89`

**Deployed source** - commit `b76700c`, https://github.com/Olawalter/ContributorCourt/blob/b76700cdaea19f71cdd44f1bacace0dd20bcc77f/contracts/contribution_court.py (byte-identical on chain)

## Why GenLayer is required

Whether an article explains the topic a campaign asked for, whether a translation
preserves meaning, whether documentation covers a specification, and whether a
work copies a source are judgments, not facts a deterministic contract can
check. A single operator's model would make that operator the authority over
who is paid. ContributionCourt makes the reading a consensus of validators who
each fetch the hash-bound bytes themselves, and pays on the agreed result.

## What the contract does

- Campaigns: an immutable, hashed specification - task, weighted criteria, reward
  bands, originality policy, reference sources, dates, bond - and a GEN pool.
- Submissions: the work and its cited sources committed by url + sha256, a bond,
  the highest reward reserved from the pool at filing.
- Evaluation: code decides unreadable or changed work, text addressed to the
  evaluator, hidden characters, byte copies, a missing authorship mark, declared
  late or premature publication, and missing cited sources; the panel reads
  relevance, substance, originality, self-dating and each criterion, every
  positive finding quoting the work; code derives the status, score, band,
  reward and bond.
- One appeal per submission, by the contributor or the owner, with up to two new
  hash-bound sources; the appealed record is kept.
- Permissionless finalization, stall exit and pull-payment withdrawal.

## Test results

| Check | Result |
|---|---|
| `python -m pytest tests/direct -q` | 194 passed |
| `genvm-lint check contracts/contribution_court.py --json` | lint ok, validation ok, 26 methods (15 view, 11 write); one I200 notice that a newer runner exists |
| `ruff check .` | clean |
| `python scripts/generate_fixtures.py --check` | fixtures match (20 files) |
| `python scripts/mutation_check.py --jobs 3` | 68 guards on the pre-diagnostic contract: 66 killed; tests were added for the 2 survivors, and those 2 plus the 2 mutations added for the copy rule were re-run on the final contract: all killed (`deploy/mutation_sweep.txt`, `deploy/mutation_recheck.txt`) |
| `python scripts/deploy_studionet.py --verify` | byte-identical, 26 schema methods |
| `python -m pytest tests/integration -q` | 6 of 7 passed in one run with the live-outcome check failing on transport; that check passed on its own re-run; further runs hit StudioNet's 500-requests-an-hour limit (1 opt-in live write skipped) |

## Live evidence

The live run of record on `0x0f47E6A49845c983fa9B61E441928F3435E9Adde`: 71 transactions from 2026-09-15T18:15:57Z to 2026-09-15T20:00:18Z (`deploy/live_run_transcript.json`, `deploy/live_run.log` and the two resume logs). Three campaigns - an explainer article, a Spanish translation, a documentation bounty - plus a fourth for the stall exit.

| Case | Expected | Observed | Decided by | Held |
|---|---|---|---|---|
| CC01 | APPROVED / MEETS_CRITERIA / GOLD | APPROVED / MEETS_CRITERIA / GOLD | PANEL | yes |
| CC02 | DUPLICATE_OR_DERIVATIVE / COPIED / NONE | DUPLICATE_OR_DERIVATIVE / COPIED / NONE | PANEL | yes |
| CC03 | REJECTED / LOW_EFFORT / NONE | REJECTED / LOW_EFFORT / NONE | PANEL | yes |
| CC04 | OUT_OF_SCOPE / OFF_TOPIC / NONE | OUT_OF_SCOPE / OFF_TOPIC / NONE | PANEL | yes |
| CC05 | REJECTED / MANIPULATION / NONE | REJECTED / MANIPULATION / NONE | CODE | yes |
| CC06 | INSUFFICIENT_EVIDENCE / HIDDEN_TEXT / NONE | INSUFFICIENT_EVIDENCE / HIDDEN_TEXT / NONE | CODE | yes |
| CC07 | LATE_SUBMISSION / DATED_AFTER_DEADLINE / NONE | LATE_SUBMISSION / DATED_AFTER_DEADLINE / NONE | PANEL | yes |
| CC08 | INSUFFICIENT_EVIDENCE / AUTHOR_MARK_MISSING / NONE | INSUFFICIENT_EVIDENCE / AUTHOR_MARK_MISSING / NONE | CODE | yes |
| CC09 | DUPLICATE_OR_DERIVATIVE / DERIVATIVE_NOT_ALLOWED / NONE | DUPLICATE_OR_DERIVATIVE / DERIVATIVE_NOT_ALLOWED / NONE | PANEL | yes |
| CC10 | APPROVED / MEETS_CRITERIA / FULL | APPROVED / MEETS_CRITERIA / FULL | PANEL | yes |
| CC11 | DUPLICATE_OR_DERIVATIVE / REFERENCE_COPY / NONE | DUPLICATE_OR_DERIVATIVE / REFERENCE_COPY / NONE | CODE | yes |
| CC12 | APPROVED / MEETS_CRITERIA / DOC | APPROVED / MEETS_CRITERIA / DOC | PANEL | yes |
| CC13 | INSUFFICIENT_EVIDENCE / SUPPORTING_SOURCES_SHORT / NONE | INSUFFICIENT_EVIDENCE / SUPPORTING_SOURCES_SHORT / NONE | CODE | yes |
| CC13:appeal | APPROVED / MEETS_CRITERIA / DOC | APPROVED / MEETS_CRITERIA / DOC | PANEL | yes |
| CC14 | APPROVED / MEETS_CRITERIA / SILVER | APPROVED / MEETS_CRITERIA / GOLD | PANEL | **no** |
| CC14:appeal | DUPLICATE_OR_DERIVATIVE / COPIED / NONE | DUPLICATE_OR_DERIVATIVE / COPIED / NONE | PANEL | yes |

15 of 16 outcomes held. The one that did not: CC14's first round was expected SILVER and read GOLD - the panel found criterion C3 fully met where the fixture expected it partly met, for a score of 85, the GOLD boundary. Its status was right, and the owner's appeal then showed it was a copy.

| What | Result |
|---|---|
| Owner appeal with the copied source ([tx](https://explorer-studio.genlayer.com/tx/0xdcf1b2f5a6b637a4f9cc465f66f8591f64f85462eb66d128030c905c43bbc5e5)) | an `APPROVED` copy became `DUPLICATE_OR_DERIVATIVE` / `COPIED`; bond forfeited to the pool |
| Contributor appeal with the missing run log ([tx](https://explorer-studio.genlayer.com/tx/0x90157a3737265635b047bd656761ce36524b778f250a82762742ef16c29c06bd)) | `INSUFFICIENT_EVIDENCE` became `APPROVED`, DOC band |
| Finalization | 14 submissions settled; 4 rewarded (CC01, CC10, CC12, CC13); bonds forfeited for CC02, CC05, CC11, CC14 |
| Stall exit ([tx](https://explorer-studio.genlayer.com/tx/0xfca1a180a942f8a8ef5e90fe73acb3d8a04e8bf82e11281a6cbd35de0eb9eb3a)) | an unevaluated submission closed `CLOSED_UNRESOLVED` by a stranger after its window; the early close was refused |
| Cancellation and reclaim ([cancel](https://explorer-studio.genlayer.com/tx/0x52f862346a0aa96d18cc0caf0cbe3fef13a8a6b23416e3090001ff58387fa0eb), [reclaim](https://explorer-studio.genlayer.com/tx/0x1b4d23e6b436ab9063ec3538b7658736c4c258dd1eb277894404d9513d7ee428)) | intake closed; the unreserved pool returned to the owner |
| Refusals | 7 sent as real transactions, every one refused with its sentence: a stranger's appeal, a second appeal, a second evaluation, a stranger activating a campaign, reclaiming an open pool, the owner filing to its own campaign (bond returned), and closing a submission before its stall window |
| Withdrawals | alice 0.100 GEN, carol 0.035 GEN, dave 0.050 GEN, owner 0.065 GEN; each wallet rose by exactly its amount |
| Ledger | the contract's chain balance, 530000000000000000 atto, equals the pools, bonds and credits it accounts for |

Stated plainly: the run was resumed twice after script faults, never contract faults. The refusal meant to show an early finalization was sent after CC01's 900-second window had already closed, so the contract finalized CC01 correctly; that step is kept in the transcript under its true name, and the early-finalize refusal is covered by the Direct Mode suite only. On the first resume the script re-read CC13's latest record (its appeal) against the first round's expectation and stopped; the recorded first round was restored from the chain and every recorded outcome was re-read and matched, digest included.

## Limitations

Consensus assumes an honest validator majority. A hash proves bytes did not
change since commitment, not who wrote them or when. Copy detection covers byte
copies and sources shown to the panel, not the web; the owner can appeal an
approval with a copied source added. Declared publication times are claims,
checked against the campaign's dates and any date the work gives itself.
Everything committed is public on chain. Unaudited; StudioNet is a test network.

## Reviewer fast path

```bash
python -m pytest tests/direct -q
```

```bash
python scripts/deploy_studionet.py --verify
```

Then read `docs/EVALUATION_POLICY.md` (how a work becomes a reward),
`docs/CONSENSUS.md` (what validators compare) and `docs/SECURITY.md`. The contract
is one file, `contracts/contribution_court.py`.

## Portal description

ContributionCourt evaluates DAO and community contributions on GenLayer against a campaign specification fixed and hashed before anyone files. An owner sets the task, weighted criteria, reward bands, originality policy, reference sources and dates, and funds a GEN pool. A contributor files a work and its cited sources, each bound by sha256, with a small bond. Code decides unreadable or changed work, text aimed at the evaluator, hidden characters, byte copies, a missing authorship mark and dates; validators judge relevance, substance, originality, self-dating and each criterion, every positive finding quoting the work. Code derives the status, score, band and reward; one appeal and permissionless exits follow. Live on StudioNet at 0x0f47E6A49845c983fa9B61E441928F3435E9Adde: 15 of 16 outcomes held, both appeals worked, and every payout matched the wallets.

(866 characters.)
