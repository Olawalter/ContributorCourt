# Evaluation policy

How a contribution becomes a status, a score, a band and a reward. Everything
here is code in `contracts/contribution_court.py`; symbols are named so the
text can be checked against it.

## The campaign specification

A campaign owner fixes one specification with `create_campaign`. It is parsed
by `_parse_spec`, stored as canonical JSON with its sha256 (`definition_hash`),
and no method rewrites it. A changed campaign is a new campaign, which may name
the one it `supersedes` (only its own owner's).

| Field | Rule |
|---|---|
| `title`, `description`, `required_task` | bounded text, no control characters, nothing addressed to the evaluator (`_text_error`) |
| `accepted_content_types` | 1 to 5 of `ARTICLE`, `TUTORIAL`, `TRANSLATION`, `DOCUMENTATION`, `CODE_CHANGE` |
| `criteria` | 1 to 6, numbered `C1`, `C2`, ...; each a question, an integer `weight` 1-100 and a boolean `required` |
| `approve_threshold` | integer score 1-100 |
| `reward_bands` | 1 to 4, highest `min_score` first, rewards not rising, the lowest band starting at `approve_threshold`; rewards are atto amounts written as strings |
| `originality_policy` | `ORIGINAL_REQUIRED`, `ATTRIBUTED_DERIVATION_ALLOWED` or `DERIVATION_OF_REFERENCE` |
| `reference_sources` | 0 to 3 hash-bound sources the owner fixes: `{url, sha256, label}` |
| `min_supporting_sources` | 0 to 3 readable sources the contributor must cite |
| `require_author_mark` | the work must carry its contributor's wallet address |
| `allow_prior_work` | whether work published before `opens_at` is in scope |
| `opens_at` <= `work_deadline` <= `submission_deadline` | ISO-8601 UTC; the submission deadline in the future |
| `appeal_window_seconds`, `stall_window_seconds` | 60 s to 60 days, wall-clock |
| `per_wallet_limit` | 1 to 10 submissions per wallet |
| `submission_bond_atto` | at most 10 GEN |
| `cancellation_policy` | `CLOSE_INTAKE_HONOUR_SUBMISSIONS` |
| `spec_version`, `supersedes` | 1-1000; empty or a campaign id |

Unknown or missing keys are refused, not ignored.

## The submission

`submit_contribution` takes the work's URL and sha256, the declared publication
time, a bounded summary, and up to three cited sources, each `{url, sha256,
label}`, with exactly the campaign's bond. `_submission_error` refuses an unopened
or closed campaign, the owner submitting to its own campaign, the wrong bond, an
unaccepted content type, a URL `_url_parts` does not admit, a publication time in
the future, a summary addressed to the evaluator, a cited source repeating the
work, a wallet over its limit, a work already filed to the campaign (by URL or
digest), and a pool that cannot reserve the highest band's reward. A refused
filing that sent value gets the value back as a claimable credit
(`_return_deposit`), because a payable StudioNet transaction that raises still
keeps the value.

The locked evidence is an ordered list: `E1` is the work, then the cited
sources (`SUPPORTING`), then the campaign's reference sources (`REFERENCE`).

## What code decides before any model is asked

`_code_reason`, in precedence order:

| Reason | Status | Condition |
|---|---|---|
| `PRIMARY_UNAVAILABLE` | `SOURCE_UNAVAILABLE` | the work could not be fetched |
| `PRIMARY_CHANGED` | `SOURCE_UNAVAILABLE` | the bytes served no longer hash to the commitment |
| `PRIMARY_UNREADABLE` | `INSUFFICIENT_EVIDENCE` | over 12,000 bytes, not UTF-8, or empty |
| `MANIPULATION` | `REJECTED`, bond forfeited | the work or a cited source addresses the evaluator (`EVALUATOR_MARKERS`) |
| `HIDDEN_TEXT` | `INSUFFICIENT_EVIDENCE` | the work or a cited source carries characters that hide or reorder text (`HIDDEN_CHARACTERS`) |
| `REFERENCE_COPY` | `DUPLICATE_OR_DERIVATIVE`, bond forfeited | the work's bytes are a reference source's bytes |
| `EXACT_DUPLICATE` | `DUPLICATE_OR_DERIVATIVE`, bond forfeited | the work's bytes were already approved for another submission (`approved_digests`) |
| `AUTHOR_MARK_MISSING` | `INSUFFICIENT_EVIDENCE` | the campaign requires the mark and the work does not contain the contributor's address |
| `PUBLISHED_AFTER_DEADLINE` | `LATE_SUBMISSION` | the declared publication is after `work_deadline` |
| `PUBLISHED_BEFORE_OPENING` | `OUT_OF_SCOPE` | before `opens_at`, and prior work is not allowed |
| `SUPPORTING_SOURCES_SHORT` | `INSUFFICIENT_EVIDENCE` | fewer readable cited sources than `min_supporting_sources` |

A reference source that addresses the evaluator is withheld from the panel
(`_eligible`) and not held against the contributor: it is the owner's.

## What the panel is asked

When code has not decided, one model call per node reads the specification and
every readable, eligible item, and answers every subject (`PANEL_HEADER`):

| Subject | States |
|---|---|
| `RELEVANCE` | `SATISFIED`, `PARTIALLY_SATISFIED`, `NOT_SATISFIED`, `UNVERIFIABLE` |
| `SUBSTANTIVE` | same |
| `ORIGINALITY` | `ORIGINAL`, `ATTRIBUTED_DERIVATIVE`, `COPIED`, `UNDETERMINED` |
| `LATE_DATING` | `PRESENT`, `ABSENT`, `UNDETERMINED` |
| each criterion `Cn` | `SATISFIED`, `PARTIALLY_SATISFIED`, `NOT_SATISFIED`, `UNVERIFIABLE` |

### What a finding must quote (`_support_met`)

| Finding | Must quote |
|---|---|
| `SATISFIED` or `PARTIALLY_SATISFIED` on relevance, substance or a criterion | the work itself (`E1`), never only a source it cites |
| `ATTRIBUTED_DERIVATIVE` | the credit, from `E1` |
| `COPIED` | the passage in `E1` and the matching passage in a cited or reference source |
| `LATE_DATING` `PRESENT` | a date from `E1` (the quote must contain a four-digit year) |
| `NOT_SATISFIED`, `UNVERIFIABLE`, `ORIGINAL`, `ABSENT`, `UNDETERMINED` | nothing |

Every quote must occur, word for word, in the item it cites, in that node's own
verified bytes (`_quote_grounded`). A finding whose rule is not met falls back to
its undecided state (`_normalize_finding`), which never approves anything.

The asymmetry is deliberate and has a mirror: a finding in the contributor's
favour rests on the work, a finding against it (a copy) is shown from both
sides, and a finding of absence needs no quote because absence cannot be quoted.
`ORIGINAL` needs no quote for the same reason; a false `ORIGINAL` is caught by
validators reading the same items and deriving a different status.

## The status (`_status_for`)

After the code reasons above:

1. an unusable model answer: `INCONCLUSIVE` / `MODEL_OUTPUT_INVALID`;
2. `LATE_DATING` `PRESENT`: `LATE_SUBMISSION` / `DATED_AFTER_DEADLINE`;
3. `RELEVANCE` `NOT_SATISFIED`: `OUT_OF_SCOPE` / `OFF_TOPIC`; `UNVERIFIABLE`: `INSUFFICIENT_EVIDENCE` / `RELEVANCE_UNVERIFIABLE`;
4. `ORIGINALITY` `COPIED`: `DUPLICATE_OR_DERIVATIVE` / `COPIED` (bond forfeited); `UNDETERMINED`: `INCONCLUSIVE` / `ORIGINALITY_UNDETERMINED`; `ATTRIBUTED_DERIVATIVE` under `ORIGINAL_REQUIRED`: `DUPLICATE_OR_DERIVATIVE` / `DERIVATIVE_NOT_ALLOWED` (bond returned); `ORIGINAL` under `DERIVATION_OF_REFERENCE`: `OUT_OF_SCOPE` / `NOT_A_DERIVATION_OF_REFERENCE`;
5. `SUBSTANTIVE` `NOT_SATISFIED`: `REJECTED` / `LOW_EFFORT`; `UNVERIFIABLE`: `INCONCLUSIVE` / `SUBSTANCE_UNVERIFIABLE`;
6. a required criterion `UNVERIFIABLE`: `INSUFFICIENT_EVIDENCE` / `REQUIRED_CRITERION_UNVERIFIABLE`; a required criterion not fully `SATISFIED`: `REJECTED` / `REQUIRED_CRITERION_FAILED`;
7. score at or above `approve_threshold`: `APPROVED` / `MEETS_CRITERIA`; otherwise `REJECTED` / `BELOW_THRESHOLD`.

## Score and band

`_score`: each criterion earns its full weight when `SATISFIED`, half when
`PARTIALLY_SATISFIED`, nothing otherwise; the score is `earned * 100 // total`,
an integer from 0 to 100. `_band` takes the highest band whose `min_score` the
score reaches. Only `APPROVED` carries a band and a reward; every other status
carries `NONE` and `0`.

Example (the explainer campaign: C1 weight 50 required, C2 30, C3 20, bands GOLD
85 and SILVER 60): C1 and C2 satisfied, C3 partly: `(100 + 60 + 20) * 100 // 200
= 90`, GOLD.

## Low-effort, duplicate and late work

- Promotion, link lists and filler are `SUBSTANTIVE` `NOT_SATISFIED`: rejected, bond returned.
- Byte-identical copies of a reference or an approved work are decided by code, bond forfeited.
- Copies the panel can see against a cited or reference source are `COPIED`, bond forfeited.
- A copy of a source nobody showed the panel cannot be seen by it. The owner can appeal with that source added as a reference (see below).
- Late work is caught twice: by the declared publication time in code, and by the work dating itself after the deadline in the panel.

## The bond and the reward

Bond forfeited (to the campaign pool) for `MANIPULATION`, `REFERENCE_COPY`,
`EXACT_DUPLICATE` and `COPIED` (`FORFEIT_REASONS`); returned otherwise. The
reward is credited only at `finalize_submission`, from the reservation made at
filing; the unused reservation returns to the pool.

## Appeals

One appeal per submission, by the contributor or the owner, inside
`appeal_window_seconds` of the evaluation (`appeal`). The appellant may add up to
two new hash-bound items: the contributor adds cited sources, the owner adds
reference sources. The round re-reads the same locked items plus the new ones,
stores a new record that names the one it appeals (`appeal_of`), and keeps the
original. If the appellant's own item that the appealed round read can no longer
be read, the appeal does not run (`_unread_since`); the other side's missing item
is judged as missing. After an appeal the submission can be finalized at once;
there is no second appeal.

## Inconclusive and stalled outcomes

`INCONCLUSIVE`, `INSUFFICIENT_EVIDENCE` and `SOURCE_UNAVAILABLE` pay no reward and
return the bond. A submission nobody evaluates within `stall_window_seconds` can
be closed by anyone (`close_stalled_submission`): the reservation returns to the
pool and the bond to the contributor. A round that splits stores nothing; the
evaluation can be requested again until the stall window ends.
