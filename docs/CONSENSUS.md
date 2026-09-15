# Consensus

What each node does in a round, what validators compare, and how failures are
handled. Symbols refer to `contracts/contribution_court.py`.

## Where consensus is used

Exactly two writes run a consensus round, both through `_run_round`, which calls
`gl.vm.run_nondet_unsafe(leader_fn, validator_fn)`:

- `request_evaluation` - the first evaluation of a submission;
- `appeal` - the one readjudication a submission can have.

Everything else is deterministic: campaigns, funding, submissions, finalization,
stall exits and withdrawals.

## The leader task (`_node_round`)

1. Fetch every locked item with `gl.nondet.web.get` and hash the raw bytes before
   anything reads them (`_fetch_row`). Each item becomes a row: `EXAMINED`,
   `UNAVAILABLE`, `HASH_MISMATCH`, `TOO_LARGE` or `UNPARSEABLE`, with a byte count
   only for verified bytes.
2. Scan verified text in code (`_scan`): text addressed to the evaluator, hidden
   characters, and whether the work carries the contributor's wallet address.
3. Decide in code whatever code can decide (`_code_reason`). If code decided, the
   model is not called and every subject takes its undecided state
   (`panel_state` `SKIPPED`).
4. Otherwise call the model once with `PANEL_HEADER` and the canonical data blob
   (`_panel_blob`), with `response_format="json"`. Reduce the answer to findings
   (`_normalize_finding`): unknown states dropped, quotes re-grounded in the
   node's own bytes, support rules applied. An answer no parser accepts gives
   `panel_state` `INVALID`.
5. Return the payload: rows, scans, the code reason, the panel state and the
   findings. The payload carries no status, score, band or amount.

## The validator task (`_validator_decision`)

1. Run the same `_node_round` independently: its own fetches, its own scans, its
   own model call.
2. Gate the leader's payload with this node's own verified texts
   (`_parse_payload`): exact keys and types, the rows matching the locked items
   in order, a row's byte count bound to its status, scan lists that name only
   readable items, `author_mark` a real boolean, the code reason recomputed from
   the leader's own rows and scans, every finding in the vocabulary with its
   quotes re-grounded in this node's bytes and its support rule met.
3. Compare what was read (`_evidence_difference`): panel state and code reason,
   markers, hidden characters, the authorship mark, and each row's status and
   byte count.
4. Compare the consequence (`_consequence_difference`): each side's payload is
   run through `_derive`, and these must match exactly.

## Consensus-critical fields

| Field | Why it is compared |
|---|---|
| `status` | decides whether anything is paid |
| `reason_code` | decides the bond and what a consumer is told |
| `score_band` | decides the reward |
| `reward_atto` | the amount credited at finalization |
| `originality_band` | decides duplicate and derivative outcomes |
| `evidence_sufficiency` | tells a consumer whether the work could be judged |
| `source_reachability` | tells a consumer what could not be read |
| `bond_outcome` | decides whether the bond is returned or forfeited |
| rows, markers, hidden, author mark, panel state, code reason | what the stored record says was read |

Not compared, and recorded only as the ratifying leader's reading: notes, which
quotes were chosen, and a score that moves inside one band. `overall_score` in a
record is the leader's score; the band it falls in is the agreed value.

## Equivalence rule, in one sentence

Two nodes agree when they read the same bytes, found the same code facts, and
their findings lead to the same status, reason, band, reward, originality band,
sufficiency, reachability and bond.

## Invalid output

| Case | Handling |
|---|---|
| model output is not a JSON object, or has no usable subjects | `PANEL_INVALID`; every subject undecided; status `INCONCLUSIVE` unless code already decided |
| fenced JSON (```json ... ```) | the fence is removed and the object read (`_model_object`) |
| an unknown state, a non-string state, a missing subject | that subject undecided |
| an extra subject | ignored |
| a quote that does not occur in the cited item | dropped; a finding left without required support is undecided |
| a note over 200 characters or with control characters | cleaned to one line within the cap (`_clean_note`) |
| a leader payload with unknown keys, floats for integers, integers for booleans, invented evidence ids, an unknown enum, a missing finding | refused by the gate: the validator disagrees |
| the model call raises | `[TRANSIENT] the model call failed`; a validator agrees only when it also hits a transient failure, and nothing is stored |
| the leader fails with `[LLM_ERROR]` | never ratified (`_vote_on_leader_error`) |
| the ratified payload fails the gate when re-parsed | `[LLM_ERROR]`: nothing is written |

## Source failures

| Failure | Handling |
|---|---|
| the work cannot be fetched | `SOURCE_UNAVAILABLE` / `PRIMARY_UNAVAILABLE`, bond returned |
| the work's bytes changed | `SOURCE_UNAVAILABLE` / `PRIMARY_CHANGED`, bond returned |
| a cited source cannot be read | it counts as not provided; below `min_supporting_sources` the status is `INSUFFICIENT_EVIDENCE` |
| a reference source cannot be read | the panel judges without it; reachability says `REFERENCE_PARTIAL` |
| one node can read an item another cannot | the rows differ: validators disagree, nothing is stored, the round can be asked again |
| in an appeal, the appellant's own item that the appealed round read is gone | the appeal does not run |

## Round structure

- One model call per node per round; one round per write.
- A submission has at most two rounds: its evaluation and its one appeal.
- `consensus_max_rotations` is set by the caller; a round that does not reach a
  majority stores nothing and moves nothing, and the write can be sent again
  while the stall window is open.
- Every refusal a validator makes prints a line to its stdout: `[DISAGREE]` with
  the difference, `[MINE]` with its own status and findings, `[DOWNGRADE]` when a
  finding lost its support. The live run records these per node.

## What the diagnostic pass showed

Every catalogue case was evaluated once on a disposable deployment
(`0xB1fAa2bf3e1807fE1AB86fbe186452033c5a6566`, commit `4a88111`), with each node's
stdout recorded (`deploy/diagnostics/cases_0xb1faa2bf.json`). 11 of 14 held.

| Case | Expected | Observed | What the nodes showed | Change |
|---|---|---|---|---|
| CC01, the honest explainer | `APPROVED` | `DUPLICATE_OR_DERIVATIVE` / `COPIED`, ratified 3-2 | three models called it a copy, quoting passages of the work and the reference that share a subject and short phrases; one validator's copy quote did not ground and was downgraded, another read `ORIGINAL` | a copy now needs a run of at least 12 consecutive words quoted from both sides (`COPY_RUN_WORDS`); the prompt says shared subject matter, terms and paraphrase are not copying |
| CC03, promotion | `REJECTED` / `LOW_EFFORT` | `OUT_OF_SCOPE` / `OFF_TOPIC` | relevance was read as whether the work does the task | relevance now asks only what the work is about |
| CC14, the copied blog | `APPROVED` (first round) | `REJECTED` / `REQUIRED_CRITERION_FAILED` | C1 asks about validators voting; the text never mentioned a vote, so it read as partly met - a fair reading | the fixture blog and its copy now name the vote |

The same pass also showed the reservation rule working on chain: the explainer
pool funded for eight reservations refused the ninth filing and returned its bond.
The live run of record ran on the corrected contract.
