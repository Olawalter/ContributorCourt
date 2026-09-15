#!/usr/bin/env python3
"""Mutation kill check: prove the Direct Mode suite pins each load-bearing
guard, not merely that the code passes today.

For each mutation the repository is copied to a scratch directory with ONE
guard in the contract mechanically broken, and the whole Direct Mode suite
runs against the copy. A mutation is KILLED when the suite fails and SURVIVED
when it passes (an unpinned guard). The run starts with an accept-control:
the unmodified copy must pass, or every kill would be vacuous.

Anchors are code TEXT, never line numbers. An anchor that is not found
exactly once is reported as ANCHOR MISSING - the guard moved or was deleted,
which is its own finding.

Run:  python scripts/mutation_check.py              (full sweep)
      python scripts/mutation_check.py --anchors    (anchor check only)
      python scripts/mutation_check.py --only gate  (names containing "gate";
                                                     separate several with |)
      python scripts/mutation_check.py --jobs 3     (three scratch copies)
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = "contracts/contribution_court.py"
Q = '"'


def off(condition: str) -> tuple:
    """(anchor, replacement) turning one `if` line into `if False:`."""
    head = condition[:len(condition) - len(condition.lstrip())]
    keyword = condition.lstrip().split(" ", 1)[0]
    return (condition + "\n", head + keyword + " False:\n")


def m(name: str, anchor: str, replacement: str = None) -> tuple:
    if replacement is None:
        anchor, replacement = off(anchor)
    return (name, anchor, replacement)


MUTATIONS = [
    # -- evidence --------------------------------------------------------------------
    m("changed bytes are read as the committed work",
      "    if hashlib.sha256(body).hexdigest() != item[\"sha256\"]:"),
    m("an oversized item is read anyway", "    if len(body) > FETCH_BYTES_CAP:"),
    # -- what code decides before any model --------------------------------------------
    m("text addressed to the evaluator is not manipulation",
      "    if any(e in markers for e in contributor_ids):"),
    m("hidden characters are not caught", "    if any(e in hidden for e in contributor_ids):"),
    m("a rehosted reference is not a copy",
      "    if ctx[\"primary_sha256\"] in ctx[\"reference_digests\"]:"),
    m("an approved work filed again is not a duplicate", "    if ctx[\"duplicate_of\"] != \"\":"),
    m("the authorship mark is not required",
      "    if ctx[\"require_author_mark\"] and not author_mark:"),
    m("a declared late publication is on time",
      "    if published > _iso_epoch(ctx[\"work_deadline\"]):"),
    m("prior work is always admitted",
      "    if published < _iso_epoch(ctx[\"opens_at\"]) and not ctx[\"allow_prior_work\"]:"),
    m("allowed prior work is still refused",
      "    if published < _iso_epoch(ctx[\"opens_at\"]) and not ctx[\"allow_prior_work\"]:\n",
      "    if published < _iso_epoch(ctx[\"opens_at\"]):\n"),
    m("too few cited sources are enough",
      "    if len(readable_supporting) < ctx[\"min_supporting_sources\"]:"),
    # -- support rules -----------------------------------------------------------------
    m("two quotes on one subject are a copy",
      "            return any(_shared_run(a[\"text\"], b[\"text\"]) >= COPY_RUN_WORDS\n",
      "            return any(_shared_run(a[\"text\"], b[\"text\"]) >= 1\n"),
    m("a copy needs thirteen shared words", "COPY_RUN_WORDS = 12 ", "COPY_RUN_WORDS = 13 "),
    m("a credited derivative needs no credit quoted",
      "        if state == ATTRIBUTED_DERIVATIVE:\n            return len(from_primary) > 0\n",
      "        if state == ATTRIBUTED_DERIVATIVE:\n            return True\n"),
    m("self-dating needs no date",
      "            return any(_has_year(q[\"text\"]) for q in from_primary)\n",
      "            return len(from_primary) > 0\n"),
    m("a positive finding may quote a cited source instead of the work",
      "    if state in (SATISFIED, PARTIALLY_SATISFIED):\n        return len(from_primary) > 0\n",
      "    if state in (SATISFIED, PARTIALLY_SATISFIED):\n        return len(quotes) > 0\n"),
    # -- the status derivation ------------------------------------------------------------
    m("an unusable model answer is not inconclusive",
      "    if payload[\"panel_state\"] != PANEL_ASSESSED:\n        return (INCONCLUSIVE, "
      "\"MODEL_OUTPUT_INVALID\")\n",
      "    if False:\n        return (INCONCLUSIVE, \"MODEL_OUTPUT_INVALID\")\n"),
    m("a work dating itself late is on time",
      "    if _state_of(payload, SUBJECT_LATE_DATING) == PRESENT:"),
    m("an off-topic work is in scope", "    if relevance == NOT_SATISFIED:"),
    m("unverifiable relevance is enough", "    if relevance == UNVERIFIABLE:"),
    m("a copy is not a duplicate", "    if originality == COPIED:"),
    m("undetermined originality is enough", "    if originality == UNDETERMINED:"),
    m("a derivative is original enough",
      "    if originality == ATTRIBUTED_DERIVATIVE and policy == \"ORIGINAL_REQUIRED\":"),
    m("an original work is a translation",
      "    if originality == ORIGINAL and policy == \"DERIVATION_OF_REFERENCE\":"),
    m("promotion is substantive", "    if substantive == NOT_SATISFIED:"),
    m("unverifiable substance is enough", "    if substantive == UNVERIFIABLE:"),
    m("an unverifiable required criterion is enough",
      "        if c[\"required\"] and _state_of(payload, c[\"id\"]) == UNVERIFIABLE:"),
    m("a partly met required criterion passes",
      "        if c[\"required\"] and _state_of(payload, c[\"id\"]) != SATISFIED:\n",
      "        if c[\"required\"] and _state_of(payload, c[\"id\"]) == NOT_SATISFIED:\n"),
    m("the threshold score itself is rejected",
      "    if _score(ctx, payload) >= ctx[\"approve_threshold\"]:\n",
      "    if _score(ctx, payload) > ctx[\"approve_threshold\"]:\n"),
    m("a band's minimum score is not in the band",
      "        if score >= b[\"min_score\"]:\n", "        if score > b[\"min_score\"]:\n"),
    m("a partly met criterion earns full weight",
      "PARTIALLY_SATISFIED: 1, NOT_SATISFIED: 0",
      "PARTIALLY_SATISFIED: 2, NOT_SATISFIED: 0"),
    m("a copy keeps its bond",
      "FORFEIT_REASONS = (\"MANIPULATION\", \"REFERENCE_COPY\", \"EXACT_DUPLICATE\", \"COPIED\")",
      "FORFEIT_REASONS = (\"MANIPULATION\", \"REFERENCE_COPY\", \"EXACT_DUPLICATE\")"),
    # -- the gate and the equivalence rule --------------------------------------------------
    m("the gate trusts the leader's code reason", "    if p[\"panel_reason\"] != reason:"),
    m("the gate takes an integer for a boolean",
      "    if not isinstance(p[\"author_mark\"], bool):"),
    m("the gate does not re-ground quotes",
      "        if q in seen or not _quote_grounded(q, eligible, texts):\n",
      "        if q in seen:\n"),
    m("the gate does not apply the support rules",
      "    return _support_met(subject_id, f[\"state\"], f[\"quotes\"], roles)\n",
      "    return True\n"),
    m("the authorship mark is not compared",
      "    for key in (\"markers\", \"hidden\", \"author_mark\"):\n",
      "    for key in (\"markers\", \"hidden\"):\n"),
    m("the consequence is not compared",
      "        difference = _consequence_difference(own_outcome, _derive(ctx, parsed))\n",
      "        difference = \"\"\n"),
    m("a model failure is ratified",
      "    if leader_text.startswith(ERROR_LLM):\n        return False\n",
      "    if False:\n        return False\n"),
    m("any error ratifies a transient one",
      "            return own_text.startswith(ERROR_TRANSIENT)\n", "            return True\n"),
    # -- appeals ------------------------------------------------------------------------------
    m("the other side's missing item stops an appeal",
      "    return [e for e in before if item_roles[e] in roles and e not in now]\n",
      "    return [e for e in before if e not in now]\n"),
    m("an appellant may withdraw its own item",
      "    return [e for e in before if item_roles[e] in roles and e not in now]\n",
      "    return []\n"),
    m("a submission can be appealed twice",
      "        if str(sub.status) != SUB_EVALUATED:\n            self._fail(\"only an EVALUATED "
      "submission can be appealed, once\")\n",
      "        if False:\n            self._fail(\"only an EVALUATED submission can be "
      "appealed, once\")\n"),
    m("an appeal after the window is heard",
      "        if _iso_epoch(now) > _iso_epoch(str(sub.appeal_deadline)):"),
    m("a stranger can appeal",
      "            self._fail(\"only the contributor or the campaign owner can appeal\")\n",
      "            party = PARTY_OWNER\n"),
    m("an overturned approval keeps the digest",
      "        elif record[\"status\"] != APPROVED and holder == str(sub.submission_id):"),
    m("an approval registers no digest",
      "        if record[\"status\"] == APPROVED and holder is None:"),
    # -- money and state ----------------------------------------------------------------------
    m("finalization ignores the appeal window",
      "            if _iso_epoch(now) <= _iso_epoch(str(sub.appeal_deadline)):"),
    m("a forfeited bond is returned", "        if record[\"bond_outcome\"] == BOND_FORFEIT:"),
    m("the pool over-reserves", "        if free < _max_reward(spec):"),
    m("the per-wallet limit is not enforced",
      "        if count is not None and int(count) >= spec[\"per_wallet_limit\"]:"),
    m("the same work files twice in a campaign",
      "            if self.campaign_digests.get(campaign_id + \"|\" + key) is not None:"),
    m("the owner can submit to its own campaign", "        if wallet == str(campaign.owner):"),
    m("any value is a bond", "        if value != int(spec[\"submission_bond_atto\"]):"),
    m("a submission closes before the stall window", "        if _iso_epoch(now) <= deadline:"),
    m("an evaluation runs after the stall window",
      "        if _iso_epoch(now) > _iso_epoch(str(sub.submitted_at)) + "
      "spec[\"stall_window_seconds\"]:"),
    m("an evaluation runs twice",
      "        if str(sub.status) != SUB_SUBMITTED:\n            self._fail(\"only a SUBMITTED "
      "contribution awaits its evaluation\")\n",
      "        if False:\n            self._fail(\"only a SUBMITTED contribution awaits its "
      "evaluation\")\n"),
    m("a stranger funds a pool",
      "        if self._sender_hex() != str(campaign.owner):\n            reason = \"only the "
      "campaign owner funds its pool\"\n",
      "        if False:\n            reason = \"only the campaign owner funds its pool\"\n"),
    m("a stranger activates a campaign",
      "        if self._sender_hex() != str(campaign.owner):\n            self._fail(\"only the "
      "campaign owner activates it\")\n",
      "        if False:\n            self._fail(\"only the campaign owner activates it\")\n"),
    m("an open pool is reclaimed",
      "        if status not in (CAMPAIGN_CANCELLED, CAMPAIGN_CLOSED, CAMPAIGN_DRAFT):"),
    m("anyone supersedes a campaign",
      "            if prior is None or str(prior.owner) != owner:\n",
      "            if prior is None:\n"),
    m("withdraw pays twice", "        self.credits[wallet] = u256(0)\n", "        pass\n"),
    # -- input admission ------------------------------------------------------------------------
    m("unknown specification keys are accepted",
      "    if sorted(spec.keys()) != sorted(SPEC_KEYS):"),
    m("a weight need not be an integer", "        if not _int_in(c[\"weight\"], 1, 100):"),
    m("required need not be a boolean", "        if not isinstance(c[\"required\"], bool):"),
    m("the lowest band need not start at the threshold",
      "    if bands[len(bands) - 1][\"min_score\"] != spec[\"approve_threshold\"]:"),
    m("an IP literal is a host", "    if all_numeric or labels[-1].isdigit():"),
    m("a future publication is accepted",
      "        if published is None or published > at:\n", "        if published is None:\n"),
    m("party text may address the evaluator",
      "    if _evaluator_hits(value) or _hidden_hits(value):"),
]


def run_suite(workdir: pathlib.Path) -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/direct", "-q", "-x", "-p", "no:cacheprovider",
         "--no-header"], cwd=workdir, capture_output=True, text=True)
    return completed.returncode == 0


def check_anchors(source: str) -> int:
    missing = 0
    for name, old, _new in MUTATIONS:
        hits = source.count(old)
        if hits != 1:
            print(f"ANCHOR MISSING ({hits} hits): {name}")
            missing += 1
    return missing


def copy_repo(scratch: pathlib.Path, index: int) -> pathlib.Path:
    work = scratch / ("repo%d" % index)
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        ".git", "__pycache__", ".pytest_cache", "deploy", "artifacts", ".data", "docs"))
    return work


def main() -> None:
    source = (ROOT / CONTRACT).read_text(encoding="utf-8")
    missing = check_anchors(source)
    print(f"{len(MUTATIONS)} mutations, {missing} anchor problems")
    if "--anchors" in sys.argv:
        sys.exit(0 if missing == 0 else 1)
    only = ""
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].casefold()
    jobs = 1
    if "--jobs" in sys.argv:
        jobs = max(1, int(sys.argv[sys.argv.index("--jobs") + 1]))
    todo = [x for x in MUTATIONS if source.count(x[1]) == 1
            and (not only or any(part in x[0].casefold() for part in only.split("|")))]
    jobs = min(jobs, max(1, len(todo)))
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="contribution-mut-"))
    copies = [copy_repo(scratch, i) for i in range(jobs)]
    print("accept-control: unmodified copy must pass ...", flush=True)
    if not run_suite(copies[0]):
        print("CONTROL FAILED: the unmodified suite does not pass; aborting")
        shutil.rmtree(scratch, ignore_errors=True)
        sys.exit(1)
    print(f"control green; {len(todo)} mutations over {jobs} job(s)\n", flush=True)
    results = [None] * len(todo)
    cursor = [0]
    done = [0]
    lock = threading.Lock()

    def worker(work: pathlib.Path) -> None:
        target = work / CONTRACT
        while True:
            with lock:
                i = cursor[0]
                if i >= len(todo):
                    return
                cursor[0] = i + 1
            name, old, new = todo[i]
            target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")
            passed = run_suite(work)
            target.write_text(source, encoding="utf-8", newline="\n")
            with lock:
                results[i] = passed
                done[0] += 1
                print(f"  [{done[0]}/{len(todo)}] {'SURVIVED' if passed else 'killed  '}: "
                      f"{name}", flush=True)

    threads = [threading.Thread(target=worker, args=(w,)) for w in copies]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    shutil.rmtree(scratch, ignore_errors=True)
    print()
    killed = survived = 0
    for (name, _old, _new), passed in zip(todo, results):
        print(("SURVIVED: " if passed else "killed:   ") + name)
        survived += 1 if passed else 0
        killed += 0 if passed else 1
    print(f"\nmutations: {killed} killed, {survived} survived, {missing} anchor missing")
    sys.exit(0 if survived == 0 and missing == 0 else 1)


if __name__ == "__main__":
    main()
