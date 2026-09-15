# Security

Assets, actors, what the contract defends against, and what it does not.
Symbols refer to `contracts/contribution_court.py`.

## Assets

| Asset | Protection |
|---|---|
| campaign pools | only the owner funds a pool; each submission reserves the highest band's reward at filing; rewards are paid only at finalization from agreed records; the owner reclaims only what is unreserved, and only once intake has closed |
| submission bonds | held until finalization or the stall exit; forfeited only for manipulation or copying |
| claimable credits | a pull-payment ledger cleared before the transfer (`withdraw`) |
| the specification | canonical JSON and its sha256, never rewritten (`get_definition_hash` recomputes it) |
| evaluation records | stored once per round, never edited; an appeal adds a record that names the one it appeals |

At every moment the contract's balance equals pools plus held bonds plus
claimable credits (`get_stats` `held_atto`); the Direct Mode suite asserts it after
every money movement and the live run checks it against the chain balance.

## Actors

- **Campaign owner** - writes the specification and the reference sources, funds
  the pool, may cancel intake, may appeal with an added reference source.
- **Contributor** - files a work with its cited sources and a bond, may appeal with
  an added cited source. Every recorded contributor is the transaction signer.
- **Anyone** - may request an evaluation, finalize after the window, close a
  stalled submission.
- **Validators** - fetch the evidence and run the model; an honest majority is
  assumed.

## Hostile content and prompt injection

Every fetched byte is data.

- The prompt frames every item, the specification, the contributor's summary and
  every label as material to read and claims by whoever wrote them, never
  instructions (`PANEL_HEADER`). The data blob is canonical JSON, so no party can
  close a string and write structure of its own into the prompt.
- Text addressed to the evaluator ("note to the evaluator", "approve this
  submission", `EVALUATOR_MARKERS`) in the work or a cited source is decided by code
  as `MANIPULATION` before any model is asked, and forfeits the bond. The same
  text in a reference source withholds that source from the panel.
- Text a party writes into the contract (specification, summary, labels, appeal
  reason) is refused if it addresses the evaluator or hides characters
  (`_text_error`).
- Characters that hide or reorder text (zero-width, bidirectional controls,
  `HIDDEN_CHARACTERS`) make a work `INSUFFICIENT_EVIDENCE`, bond returned. The
  zero-width joiner is excluded because emoji sequences use it.
- A work that quotes an injection phrase as its subject ("ignore your previous
  instructions") is not manipulation: only phrases addressed to whoever evaluates
  the work are. The honest baseline case carries such a phrase as its negative
  control.

What this does not do: detect every phrasing that tries to steer a model. The
marker list catches direct address; the prompt and the support rules - a finding
in the contributor's favour must quote the work, and every quote is re-checked
by each validator against its own bytes - limit what an indirect attempt can
achieve.

## URL validation and its limits

`_url_parts` admits only https URLs with a DNS host, no credentials, no port but
443, no IP literal of any form, no localhost or internal names (`.local`,
`.internal`, `.home.arpa`, `.lan`), no fragments, backslashes, encoded
separators, dot-segments or empty segments, written in canonical form.

This is admission hygiene, not SSRF protection. A DNS name can resolve to a
private address, and redirects are followed by the runtime. Validators'
egress controls in GenVM are the real boundary; the contract cannot see where a
name resolves.

## Source truncation and binding

Every item is bound by sha256 when it is committed and verified against the raw
bytes before anything reads them. An item over 12,000 bytes (`FETCH_BYTES_CAP`)
is recorded `TOO_LARGE` and never truncated: judging a prefix would mean judging
bytes the contributor did not commit as the work. The cap bounds prompt size.

A hash proves the bytes did not change since the commitment. It does not prove
who wrote them or when.

## Source independence and authorship

- **Authorship.** The work must contain its contributor's wallet address when the
  campaign requires the mark (`require_author_mark`). Someone filing another
  person's article cannot insert their own address into bytes hosted by that
  person; if they rehost a copy with their address in it, the copy's bytes
  differ and the panel judges it against whatever sources it is shown.
- **Duplicates.** Byte-identical copies are caught against the campaign's
  reference sources and against every work already approved anywhere in the
  contract (`approved_digests`). A rejected filing registers nothing, so filing
  someone's work badly does not make their later filing a duplicate. An appeal
  that overturns an approval releases the digest.
- **Semantic copies** are judged only against the items shown to the panel: the
  campaign's references, the work's cited sources, and a source added on appeal.
  This is not plagiarism detection across the web.
- **Publication time** is the contributor's declaration, checked in code against
  the campaign's dates and by the panel against any date the work gives itself.
  A work that states no date cannot be dated beyond the declaration.

## Forged leader results

A validator refuses a leader payload that fails the structural gate or reads
differently from its own round. The suite forges, among others: required topics
claimed covered, originality claimed for a copy, an unavailable work claimed
read, a hidden marker, invented evidence ids and quotes, missing findings,
unknown enums, strings for booleans, floats for integers, and a changed
subject id, round or clock.

## Malformed model output

Never an approval. An unusable answer is `INCONCLUSIVE`; an unknown or unsupported
state is undecided, and every undecided subject resolves to a non-paying status.

## Replay protection

- A submission is evaluated once (`request_evaluation` requires `SUBMITTED`) and
  appealed once (`appeal` requires `EVALUATED`).
- A payload is bound to its evaluation id, round, definition hash, evidence
  commitment and transaction time; a payload from another round fails the gate.
- Finalization, the stall exit and withdrawal each run once.
- The same work cannot be filed twice to one campaign, and an approved work filed
  to another campaign is an exact duplicate.

## Immutable specifications

No method edits a campaign's specification, criteria, bands, references or dates
after `create_campaign`. The records of every evaluation carry the
`definition_hash` they were judged under.

## Bounded history

Criteria (6), bands (4), references (3), cited sources (3), appeal items (2),
submissions per wallet (10) and per campaign (200), rounds per submission (2),
returned-deposit records, list pages (50), fetched bytes per item (12,000), and
every text field.

## Failure semantics

Fail closed. A failed round stores nothing. An unreadable work pays nothing and
returns the bond. An undecided finding never approves. A value sent with a
refused payable call is returned as a credit rather than lost. Every waiting
state has a permissionless wall-clock exit: an unevaluated submission closes
after the stall window, an evaluated one finalizes after the appeal window, an
appealed one finalizes at once.

## Limitations

- An honest validator majority is assumed.
- The panel reads what models read; a subtle inaccuracy or a clever paraphrase
  can pass. Criteria that need domain expertise should be phrased as observable
  facts the work either states or does not.
- Copy detection covers byte-identical copies and copies of sources shown to the
  panel, not the web at large.
- Authorship rests on the wallet address in the work; a campaign that does not
  require the mark accepts the first approved filing of a work.
- Everything committed is public on chain, including the work's URL and the
  contributor's summary.
- The authorship mark and the dates in a work are text the author controls.
- This is a StudioNet deployment, not an audited production system.
