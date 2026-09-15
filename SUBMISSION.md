# Submission - ContributionCourt

**Evidence-based rewards for meaningful community work.**

A standalone GenLayer Intelligent Contract that evaluates DAO and community
contributions against a campaign specification fixed before any submission, and
pays the reward the specification sets from a funded GEN pool. Validators agree
on what the work is; code decides what it earns.

**Repository** - https://github.com/Olawalter/ContributorCourt

**StudioNet address** - ADDRESS_PENDING

**Explorer** - EXPLORER_PENDING

**Deployment transaction** - DEPLOY_TX_PENDING

**Deployed source** - SOURCE_PENDING

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

RESULTS_PENDING

## Live evidence

LIVE_PENDING

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

PORTAL_PENDING
