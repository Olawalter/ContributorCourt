# Decision record

Why this contract, why this shape, and why GenLayer.

## The problem

DAO and community campaigns reward work they cannot read at scale. Reviewers
are slow and inconsistent, popularity stands in for merit, copied and
low-effort work gets through, and a rejected contributor rarely learns why.
A smart contract can check a wallet, a timestamp and a hash. It cannot check
whether an article explains the topic it was asked to, whether a translation
preserves meaning, or whether documentation covers a specification.

## Candidates considered

| # | Candidate | Verdict | Reason |
|---|---|---|---|
| 1 | ContributionCourt: a campaign specification, hash-bound contributions, one consensus evaluation, bounded appeal, funded rewards | chosen | the judgment is semantic, the evidence is public and checkable, and a reward moves on the result |
| 2 | An engagement-weighted contribution score (likes, views, reposts) | rejected | the brief forbids popularity rewards, and engagement is trivially manipulated |
| 3 | A reviewer-voting DAO module | rejected | reviewers are the bottleneck the problem describes; no GenLayer judgment involved |
| 4 | A general reputation protocol | rejected | unbounded scope; reputation without a specification has nothing to be checked against |
| 5 | An AI writing-quality oracle returning a score | rejected | a model's number deciding payment is exactly what the brief rules out; nothing binds it to a specification |

## Collision analysis

Against this portfolio of GenLayer builds and the obvious public patterns:

- **Prize-pool allocation courts** rank competing entries against each other; ContributionCourt judges each work alone against a fixed specification, and pays per band, not by rank.
- **Agent-work verification** checks a deliverable against a buyer's order; here there is no counterparty order - the owner's specification is public before anyone files, and anyone may file.
- **Milestone escrow** releases one payee's funds; here one pool serves many independent contributors with reservations at filing.
- **Web-witness notaries** attest that a page said something; here the question is whether the page meets criteria and is original.

The shared parts (hash-bound fetching, quote grounding, consensus on consequence,
pull payments) are deliberate reuse of patterns already proven on StudioNet.

## Why GenLayer is necessary

The decisive questions - is this about the task, is it substantive, is it
copied, does it meet a criterion written in English - have no deterministic
answer. A single operator could run a model, but then the operator is the
authority: contributors cannot check it, a second DAO cannot reuse it, and the
operator decides who is paid. GenLayer makes the reading a consensus of
independent validators, each fetching the bytes itself, and lets the contract
hold and pay the reward on the agreed result.

## The delete-GenLayer test

Remove the consensus round and what remains:

- deadlines, bonds, reservations, byte-identical duplicates, authorship marks and
  injection markers still work;
- nothing can say whether a work addresses the task, is substantive, is original,
  or meets a criterion;
- so every submission would either be paid on filing (anyone files anything) or
  sent to a human reviewer (the original problem).

The contract without GenLayer is a bond escrow with no way to decide who earns
the reward.

## The three-consumer proof

The contract has no consumer-specific code. Three campaigns in `fixtures/` run
through it unchanged:

1. **DAO education** (`explainer`): an article explaining Optimistic Democracy,
   `ORIGINAL_REQUIRED`, weighted criteria, two reward bands.
2. **Documentation bounty** (`docs`): a reference page for a command,
   `ATTRIBUTED_DERIVATION_ALLOWED` against its specification, one cited run log
   required.
3. **Translation** (`translation`): a Spanish translation of a reference page,
   `DERIVATION_OF_REFERENCE`.

The differences are all specification fields: content types, originality
policy, references, required cited sources, criteria and bands.

## Design decisions

- **Code before model.** Everything a deterministic check can settle is settled
  before the model is asked, and a code-decided case never calls it.
- **Consensus on consequence.** Validators compare what was read and what the
  findings lead to - status, reason, band, reward, originality band, bond - not
  wording. Models phrase differently; honest nodes must still agree.
- **Positive findings quote the work.** A finding in the contributor's favour
  must rest on the work's own words; a cited source cannot carry it.
- **Undecided never pays.** Every undecided subject resolves to a status that pays
  nothing and returns the bond.
- **Reserve at filing.** Concurrent approvals cannot over-commit a pool.
- **Authorship by wallet address in the work.** The cheapest proof a contributor
  can give that the hosted bytes are theirs, checkable in code.
- **One appeal, both parties.** The contributor can add a missing cited source;
  the owner can add the source a work copied. Two rounds bound the cost.
- **Real value.** A points-only ledger would be a weak GenLayer fit: a central
  service could keep it. The pool is real GEN held and paid by the contract.

## Major risks

| Risk | Mitigation | Residual |
|---|---|---|
| Models split on a reading | compare consequences only; the diagnostic pass records every node's reading | a split stores nothing and costs time |
| A clever paraphrase of an unlisted source | owner appeal with the source added | not detected unless someone finds the source |
| A contributor games the model with indirect steering | markers decided in code; positive findings must quote the work; validators re-read independently | an indirect attempt that also reads as honest content |
| A page that changes on every load | hash mismatch reads as `SOURCE_UNAVAILABLE`, bond returned | contributors must host stable bytes |
| A specification that rewards the wrong thing | immutable and public before submissions | the owner's responsibility |
| URL targets private infrastructure | admission hygiene in `_url_parts` | runtime egress controls are the real boundary |
