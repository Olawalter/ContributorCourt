<p align="center"><img src="docs/assets/contribution-court-mark.svg" width="140" alt="ContributionCourt"/></p>

# ContributionCourt - Evidence-Based Rewards for Community Work

**A standalone GenLayer Intelligent Contract that evaluates DAO and community contributions against a campaign specification its owner fixed in advance, under validator consensus, and pays the reward the specification sets - from a funded pool, through arithmetic the contract does itself.**

A campaign owner fixes a specification - the task, the criteria and their weights, the reward bands, the originality policy, the reference sources, the deadlines - and funds a GEN pool. A contributor files a work with the sources it cites, each bound to the sha256 of its exact bytes, and a small bond. One consensus round has every validator fetch and verify those bytes, check in code what code can check, and answer only what it cannot: is the work about the task, is it substantive, is it original, does it date itself late, does it meet each criterion - every positive finding quoting the work itself. Code then derives the status, the score, the band and the reward.

No model output ever reaches a status, a score or an amount.

Deployment of record: [`0x0f47E6A49845c983fa9B61E441928F3435E9Adde`](https://explorer-studio.genlayer.com/address/0x0f47E6A49845c983fa9B61E441928F3435E9Adde) on GenLayer StudioNet, from commit `b76700c`, byte-identical.

## At a glance

| Question | Answer |
|---|---|
| What is ContributionCourt | A reusable contract primitive: a campaign specification, hash-bound contributions, one consensus evaluation each, one bounded appeal, and a reward ledger. No frontend, backend, database or operator. |
| Who calls it | DAOs, grant programmes and bounty programmes that create campaigns; contributors who file work; and any contract or indexer that pays points or reputation on a final result (`is_rewardable`). |
| What it decides | Whether a submitted work addresses the campaign's task, is substantive rather than promotion, is original or a credited derivative or a copy of a source shown to the panel, dates itself after the work deadline, and meets each weighted criterion. |
| Why GenLayer must decide it | Whether an article explains a topic correctly, whether a translation preserves meaning, whether documentation covers a specification, whether a work copies a source - none of these is a fact a deterministic contract can check, and a single operator's model is an authority contributors cannot check and a second DAO cannot reuse. |
| What evidence it uses | The work and its cited sources, each committed as url + sha256 at filing; the campaign's reference sources, committed with the specification. Every byte is verified before anything reads it. |
| How consensus works | `gl.vm.run_nondet_unsafe` once per evaluation. Each validator reproduces the round from its own fetches and its own model call, gates the leader's payload against its own bytes, and agrees only if what was read matches and its own findings lead to the same status, band, reward, originality band and bond. |
| How money moves | Two payable entries (`fund_campaign`, `submit_contribution`), the highest reward reserved at filing, payment only at `finalize_submission`, one exit (`withdraw`). A refused deposit is returned as a credit, never lost. |
| What tests prove it | Direct Mode tests covering every status and reason code, every criterion outcome and band boundary, model-output attacks, forged leader payloads through the captured validator, prompt injection with its negative control, appeals, stall exits, and money conservation after every movement; a mutation sweep; GenVM lint; a live run on StudioNet. See "Verified". |

## What it is

- **The specification binds before any submission.** Stored as canonical JSON with its sha256; no method rewrites it. A new version is a new campaign that names the one it supersedes.
- **Identity is the signer.** The contributor, the owner and every appellant are the wallets that signed.
- **Hash-bound evidence.** The work, its cited sources and the campaign's references are committed by url and sha256 and verified before anything reads them.
- **Code decides what code can.** Unreadable or changed work, text addressed to the evaluator, hidden characters, byte-identical copies of a reference or of an approved work, a missing authorship mark, a declared late or premature publication, and too few cited sources - all before any model is asked.
- **Consensus decides meaning.** Relevance, substance, originality, self-dating and each criterion; every positive finding quotes the work itself, and a copy is shown from both sides.
- **Code derives the outcome.** Eight statuses, 25 reason codes, a weighted integer score, reward bands, the bond outcome.
- **Fail closed.** An undecided finding never approves; an unusable model answer is `INCONCLUSIVE`; a round that splits stores nothing.
- **One bounded appeal.** The contributor with a missing cited source, or the owner with the source a work copied; the original record is kept.
- **Every waiting state has an exit.** Stall close, finalization after the window, withdrawal - all permissionless and wall-clock.

## How it works

### For a campaign owner

1. `create_campaign(spec_json)` - the specification is fixed from this moment.
2. `fund_campaign(campaign_id)` with GEN, then `activate_campaign(campaign_id)`.
3. Optionally `appeal(submission_id, reason, items_json)` once, inside the window, adding a reference source a work copied.
4. `cancel_campaign` closes intake; filed submissions are still evaluated and paid. `reclaim_unreserved` returns what no submission reserved once intake has closed.

### For a contributor

1. Publish the work at a stable https URL; put your wallet address in it if the campaign requires the mark.
2. `submit_contribution(campaign_id, content_type, primary_url, primary_sha256, publication_at, evidence_summary, supporting_json)` with exactly the campaign's bond.
3. After the evaluation, optionally `appeal` once inside the window with a missing cited source.
4. `withdraw()` the reward and the returned bond after finalization.

### For anyone

`request_evaluation`, `finalize_submission` and `close_stalled_submission` are permissionless. A contributor whose campaign owner went quiet is never stuck.

## Statuses

| Status | When | Reward | Bond |
|---|---|---|---|
| `APPROVED` | on topic, substantive, original enough for the policy, every required criterion satisfied, score at or above the threshold | the band's reward | returned |
| `REJECTED` | text addressed to the evaluator; promotion or filler; a required criterion not met; score below the threshold | none | forfeited for manipulation, otherwise returned |
| `DUPLICATE_OR_DERIVATIVE` | a byte copy of a reference or an approved work; a copy the panel shows from both sides; a credited derivative where originality is required | none | forfeited for copies, returned for a credited derivative |
| `OUT_OF_SCOPE` | about something else; published before the campaign opened; not a derivation where one is required | none | returned |
| `LATE_SUBMISSION` | declared or self-dated after the work deadline | none | returned |
| `INSUFFICIENT_EVIDENCE` | unreadable or oversized work, hidden characters, missing authorship mark, too few cited sources, unverifiable relevance or required criterion | none | returned |
| `SOURCE_UNAVAILABLE` | the work could not be fetched or its bytes changed | none | returned |
| `INCONCLUSIVE` | the model's answer was unusable, or originality or substance could not be decided | none | returned |

The full precedence and every reason code: [`docs/EVALUATION_POLICY.md`](docs/EVALUATION_POLICY.md).

## Score and bands

Each criterion earns its full weight when `SATISFIED`, half when `PARTIALLY_SATISFIED`, nothing otherwise; the score is an integer 0-100. The campaign's bands map the score to a reward, the lowest band starting at the approval threshold. Validators agree on the band and the reward; a score moving inside one band is recorded, not compared.

## Lifecycle

```text
 campaign   create_campaign --> DRAFT --fund_campaign, activate_campaign--> OPEN
                                   |                                          |
                                   +---------- cancel_campaign --------------+--> CANCELLED
                                                                              |
                                                     submission_deadline passes --> CLOSED

 submission submit_contribution (bond; evidence locked; reward reserved)
              |
              v
          SUBMITTED --request_evaluation (consensus round)--> EVALUATED
              |                                                  |   appeal window open
              | stall window passes                              |
              v                                                  +--appeal (consensus round)--> APPEAL_EVALUATED
      close_stalled_submission                                   |                                  |
              |                                                  | window closes                    |
              v                                                  v                                  v
      CLOSED_UNRESOLVED                              finalize_submission                  finalize_submission
      (bond returned,                                  |                                   |
       reservation released)                           +--> REWARDED  (reward credited)    +--> REWARDED
                                                       +--> FINALIZED (no reward)          +--> APPEAL_FINALIZED

 anyone     withdraw() pays the caller's claimable credit
```

`EVALUATING` is not a stored state: an evaluation is one transaction, and a round that does not reach consensus stores nothing.

## Contract

`contracts/contribution_court.py` - one file, 26 public methods.

| Write | Who | Payable | Notes |
|---|---|---|---|
| `create_campaign(spec_json)` | anyone (becomes owner) | no | specification fixed and hashed |
| `fund_campaign(campaign_id)` | owner | yes | a stranger's deposit is returned |
| `activate_campaign(campaign_id)` | owner | no | the pool must cover the highest reward |
| `cancel_campaign(campaign_id)` | owner | no | closes intake, honours filed submissions |
| `reclaim_unreserved(campaign_id)` | owner | no | after cancellation or the submission deadline |
| `submit_contribution(...)` | contributor | yes, the exact bond | a refused filing's bond is returned |
| `request_evaluation(submission_id)` | anyone | no | one consensus round |
| `appeal(submission_id, reason, items_json)` | contributor or owner | no | once, in the window; one consensus round |
| `finalize_submission(submission_id)` | anyone | no | after the window, or after the appeal |
| `close_stalled_submission(submission_id)` | anyone | no | after the stall window, if never evaluated |
| `withdraw()` | anyone | no | pull payment |

| View | Returns |
|---|---|
| `get_campaign(campaign_id, as_of)` | specification, status, pool, reserved, unreserved, paid |
| `get_definition_hash(campaign_id)` | stored and recomputed hash, version, supersedes |
| `get_submission(submission_id)` | locked items, dates, bond, reservation, evaluation ids |
| `get_submission_status(submission_id, as_of)` | which action is open now |
| `get_evaluation(evaluation_id)` / `get_latest_receipt(submission_id)` | an evaluation record |
| `get_appeal_state(submission_id, as_of)` | the appeal and the window |
| `get_reward_entitlement(submission_id)` | entitled and pending atto, final |
| `is_rewardable(submission_id)` | rewardable, final, band |
| `list_campaigns`, `list_campaign_submissions` | pages of ids |
| `get_claimable`, `get_stats`, `get_config`, `get_returned_deposits` | ledger, totals, enums, refused deposits |

### Consensus guarantees

- The payload carries no status, score, band or amount; validators derive them from their own findings.
- Every quote is re-grounded in each validator's own verified bytes; a finding without its required support is refused by the gate.
- Rows, scans, the authorship mark and the code reason are compared exactly.
- Notes, quote choice and a score inside one band are recorded, never compared.
- A round that splits stores nothing and moves nothing.

Details: [`docs/CONSENSUS.md`](docs/CONSENSUS.md).

## Originality: what it can and cannot tell

- Byte-identical copies of a campaign reference or of any work already approved in the contract: decided by code.
- Word-for-word copies of a source the panel is shown - the campaign's references, the work's cited sources, a source added on appeal: judged by the panel, and a copy must quote a run of at least 12 consecutive words shared by both.
- Shared subject matter, shared terms and paraphrase are not copies; uncredited paraphrase is not detected.
- Copies of anything else on the web: not seen. The owner can appeal an approval with the copied source added.
- Authorship: the work must carry the contributor's wallet address when the campaign requires it.
- It is not plagiarism detection, and it does not claim to be.

## Consumers

The same contract serves, unchanged, a DAO educational-content campaign, an open-source documentation or feature bounty, and a translation campaign; the fixtures define one of each. [`docs/INTEGRATION.md`](docs/INTEGRATION.md) shows how a downstream contract reads a final result.

## Verified

| Check | Result |
|---|---|
| `python -m pytest tests/direct -q` | 194 passed |
| `genvm-lint check contracts/contribution_court.py --json` | lint ok, validation ok, 26 methods (15 view, 11 write); one I200 notice that a newer runner exists |
| `ruff check .` | clean |
| `python scripts/generate_fixtures.py --check` | fixtures match (20 files) |
| `python scripts/mutation_check.py --jobs 3` | 68 guards on the pre-diagnostic contract: 66 killed; tests were added for the 2 survivors, and those 2 plus the 2 mutations added for the copy rule were re-run on the final contract: all killed (`deploy/mutation_sweep.txt`, `deploy/mutation_recheck.txt`) |
| `python scripts/deploy_studionet.py --verify` | byte-identical, 26 schema methods |
| `python -m pytest tests/integration -q` | 6 of 7 passed in one run with the live-outcome check failing on transport; that check passed on its own re-run; further runs hit StudioNet's 500-requests-an-hour limit (1 opt-in live write skipped) |

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

## Repository

```text
contracts/contribution_court.py         the contract
tests/direct/                           Direct Mode suite
tests/integration/                      checks against the StudioNet deployment
fixtures/                               campaigns, source texts, cases, demo wallet addresses
scripts/generate_fixtures.py            writes fixtures/ (--check in CI)
scripts/make_wallets.py                 demo wallets: keys in .data/ (gitignored)
scripts/deploy_studionet.py             deploy, record, verify byte parity
scripts/live_run.py                     the diagnostic pass and the live run
scripts/mutation_check.py               mutation kill check over the contract's guards
scripts/fetch_genvm_bundle.py           seeds the GenVM runner cache for the toolchain
deploy/                                 deployment record, live transcript, diagnostics
docs/                                   consensus, evaluation policy, security, integration, deployment
```

## Getting started

```bash
pip install -r requirements-test.txt
```

```bash
python scripts/fetch_genvm_bundle.py
```

```bash
python -m pytest tests/direct -q
```

```bash
genvm-lint check contracts/contribution_court.py --json
```

```bash
python scripts/deploy_studionet.py --verify
```

## Security

Hostile content, URL admission and its limits, forged leaders, replay, bounded history and failure semantics: [`docs/SECURITY.md`](docs/SECURITY.md).

## Limitations

- Consensus assumes an honest validator majority.
- A hash proves the bytes did not change since commitment, not who wrote them or when.
- Copy detection covers byte copies and sources shown to the panel, not the web.
- The declared publication time is the contributor's claim, checked against the campaign's dates and any date the work gives itself.
- Models can miss a subtle inaccuracy; criteria work best phrased as facts a work states or does not.
- Work over 12,000 bytes is not read; long pieces must be split or summarised by the campaign's design.
- Everything committed is public on chain.

## Not production-ready

This is a StudioNet deployment of an unaudited contract. It does not replace a DAO's governance, and a reward it pays is only as good as the specification the owner wrote.

## Licence

MIT - see [`LICENSE`](LICENSE).
