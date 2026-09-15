# Integration

How a DAO, a grant programme, a points distributor or a reputation contract uses
ContributionCourt. The contract is the same for every consumer; only the
campaign specification changes.

## The flow

```text
owner        create_campaign(spec_json)                  -> "CP-000001"   (DRAFT)
owner        fund_campaign(campaign_id)      value=pool                     
owner        activate_campaign(campaign_id)                -> "OPEN"
contributor  submit_contribution(campaign_id, content_type, primary_url,
                primary_sha256, publication_at, evidence_summary,
                supporting_json)            value=bond   -> "SB-000001"   (SUBMITTED)
anyone       request_evaluation(submission_id)             -> "EV-000001"   (EVALUATED)
contributor  appeal(submission_id, reason, items_json)     -> "EV-000002"   (APPEAL_EVALUATED)
  or owner      (optional, once, inside the appeal window)
anyone       finalize_submission(submission_id)            -> "REWARDED" | "FINALIZED" | "APPEAL_FINALIZED"
anyone       close_stalled_submission(submission_id)       -> "CLOSED_UNRESOLVED"  (only if never evaluated)
owner        cancel_campaign(campaign_id)                  -> "CANCELLED"  (closes intake)
owner        reclaim_unreserved(campaign_id)               -> atto reclaimed
anyone       withdraw()                                    -> atto paid to the caller
```

Amounts are atto-GEN. Amounts inside JSON (bands, bonds) are decimal strings;
JSON numbers cannot carry 10^18 safely.

## Reading a result

| View | Returns |
|---|---|
| `is_rewardable(submission_id)` | `rewardable` (the standing evaluation approved the work), `final` (settled; no appeal can change it), `score_band` |
| `get_reward_entitlement(submission_id)` | `entitled_atto` (credited at finalization), `pending_atto` (the standing record's reward before finalization), `final`, `bond_outcome` |
| `get_submission_status(submission_id, as_of)` | `status`, `evaluation_status`, `reason_code`, `can_request_evaluation`, `appeal_window_open`, `can_finalize`, `can_close_stalled`, `final` |
| `get_latest_receipt(submission_id)` | the standing evaluation record |
| `get_evaluation(evaluation_id)` | any evaluation record, including an appealed one |
| `get_appeal_state(submission_id, as_of)` | `appealed`, the appeal (party, reason, added items, both evaluation ids), `window_open`, `appeals_remaining` |
| `get_submission(submission_id)` | the locked items, dates, bond, reservation, evaluation ids |
| `get_campaign(campaign_id, as_of)` | the specification, status (`CLOSED` is derived after the submission deadline), pool, reserved, unreserved, paid |
| `get_definition_hash(campaign_id)` | the stored hash and one recomputed from the stored definition |
| `list_campaigns(offset, limit)`, `list_campaign_submissions(campaign_id, offset, limit)` | pages of at most 50 ids |
| `get_claimable(wallet)`, `get_stats()`, `get_config()`, `get_returned_deposits(offset, limit)` | the ledger, totals, enums and limits, refused deposits |

A view has no clock. Pass `as_of` as `YYYY-MM-DDTHH:MM:SSZ`; a write refuses if the
caller's clock was wrong.

### The evaluation record

```json
{
  "evaluation_id": "EV-000001", "mode": "EVALUATION", "round": 1,
  "submission_id": "SB-000001", "campaign_id": "CP-000001",
  "contributor": "0x...", "definition_hash": "...", "evidence_commitment": "...",
  "evaluated_at": "2026-09-15T12:00:00Z",
  "items": [{"evidence_id": "E1", "role": "PRIMARY", "url": "...", "sha256": "...", "label": "..."}],
  "rows": [{"evidence_id": "E1", "status": "EXAMINED", "byte_count": 2311}],
  "markers": [], "hidden": [], "author_mark": true, "duplicate_of": "",
  "panel_state": "ASSESSED",
  "criterion_results": [{"id": "C1", "by": "PANEL", "state": "SATISFIED",
                         "quotes": [{"evidence_id": "E1", "text": "..."}], "note": "..."}],
  "status": "APPROVED", "reason_code": "MEETS_CRITERIA",
  "overall_score": 100, "score_band": "GOLD", "reward_atto": "50000000000000000",
  "originality_band": "ORIGINAL", "evidence_sufficiency": "SUFFICIENT",
  "source_reachability": "REACHABLE", "bond_outcome": "RETURN",
  "appeal_of": "", "record_digest": "..."
}
```

`record_digest` is the sha256 of the canonical record without the digest.

## What a consumer should do with each status

| Status | Meaning | Consumer action |
|---|---|---|
| `APPROVED` + `final` | the work met the campaign; the reward is credited | pay points, mint a badge, count it |
| `APPROVED`, not final | an appeal could still change it | wait for `final` |
| `REJECTED` | judged and not rewarded | do not pay; show `reason_code` |
| `DUPLICATE_OR_DERIVATIVE` | a copy, or a derivative the policy does not reward | do not pay |
| `OUT_OF_SCOPE` | about something else, or not what the campaign asked for | do not pay |
| `LATE_SUBMISSION` | published after the work deadline | do not pay |
| `INSUFFICIENT_EVIDENCE` | the work could not be judged on what was provided | do not pay; the contributor may appeal with the missing source |
| `SOURCE_UNAVAILABLE` | the work could not be read, or changed | do not pay; nothing was judged |
| `INCONCLUSIVE` | the panel could not decide | do not pay; nothing was judged against the contributor |

Pay only on `rewardable && final`. Never treat a non-final record as settled.

## Three consumers, one contract

1. **A DAO educational-content campaign.** `accepted_content_types: ["ARTICLE",
   "TUTORIAL"]`, `originality_policy: "ORIGINAL_REQUIRED"`, a reference page the
   articles must not copy, criteria on accuracy and clarity. Fixture campaign
   `explainer`.
2. **An open-source documentation or feature bounty.** `accepted_content_types:
   ["DOCUMENTATION"]` (or `CODE_CHANGE` with a raw diff URL),
   `originality_policy: "ATTRIBUTED_DERIVATION_ALLOWED"`, the feature specification
   as the reference, `min_supporting_sources: 1` so the example must come with its
   run log. Fixture campaign `docs`.
3. **A translation or onboarding campaign.** `accepted_content_types:
   ["TRANSLATION"]`, `originality_policy: "DERIVATION_OF_REFERENCE"`, the page to
   translate as the reference, criteria on preserved meaning and fluency. Fixture
   campaign `translation`.

A reputation contract can read `is_rewardable` and `get_latest_receipt` directly;
a points distributor can index `list_campaign_submissions` and pay from its own
ledger on `final` results without using the GEN pool at all (fund it with the
minimum and set small bands).

## Preparing evidence

- Host each file at a stable https URL and commit its exact sha256. A
  commit-pinned `raw.githubusercontent.com` URL serves identical bytes to every
  validator; a web page that changes on each load (ads, timestamps) will read as
  `HASH_MISMATCH`.
- Keep each file under 12,000 bytes of UTF-8 text.
- When the campaign requires the authorship mark, put the contributor's wallet
  address in the work.

## Reading from Python

```python
from genlayer_py import create_client
from genlayer_py.chains import studionet

client = create_client(chain=studionet)
state = client.read_contract(address=COURT, function_name="is_rewardable",
                             args=["SB-000001"])
if state["rewardable"] and state["final"]:
    receipt = client.read_contract(address=COURT, function_name="get_latest_receipt",
                                   args=["SB-000001"])
    award_points(receipt["contributor"], receipt["score_band"])
```

## Handling appeals and inconclusive outcomes

- Watch `get_submission_status(...).appeal_window_open`. If a result you believe
  is wrong is still open, the contributor or the owner can `appeal` once with up
  to two new hash-bound sources.
- `INCONCLUSIVE`, `INSUFFICIENT_EVIDENCE` and `SOURCE_UNAVAILABLE` return the bond
  and pay nothing. A contributor can appeal an `INSUFFICIENT_EVIDENCE` result with
  the missing source inside the window; otherwise file again in a new campaign.
- A submission never evaluated can be closed by anyone after the stall window;
  its reservation returns to the pool.
