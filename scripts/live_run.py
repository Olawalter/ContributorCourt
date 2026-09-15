#!/usr/bin/env python3
"""Run ContributionCourt on GenLayer StudioNet with real transactions.

    python scripts/live_run.py <address> --raw-base <url> --phase cases
    python scripts/live_run.py <address> --raw-base <url> --phase full

--raw-base is a commit-pinned https://raw.githubusercontent.com/.../fixtures/
URL, so every validator fetches exactly the committed bytes.

cases: the diagnostic pass. Three campaigns are created and funded, every
       catalogue case is filed and evaluated once, and each evaluation's
       per-node stdout ([DISAGREE], [MINE], [DOWNGRADE]) is recorded, so a
       split names its cause. Written to deploy/diagnostics/.
full:  the live run of record. The same cases, plus both appeals (the owner
       with the source a work copied, the contributor with the source it was
       missing), refusals sent as real transactions, finalization of every
       evaluated submission after its window, a stall exit, a cancellation
       and reclaim, every withdrawal checked against the wallet's balance,
       and the contract's balance checked against what it says it holds.
       Written to deploy/live_run_transcript.json.

Code-decided outcomes are asserted: the run stops if one differs. Panel-
decided outcomes are recorded with held=true/false and never stop the run.
Every transaction hash is saved before its receipt is awaited, so an
interrupted run resumes without resending anything. Keys come from
.data/demo_wallets.json (gitignored) and are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import studionet_transport  # noqa: E402,F401 - retries RPC transport failures
from genlayer_py import create_account, create_client  # noqa: E402
from genlayer_py.chains import studionet  # noqa: E402
from genlayer_py.types import TransactionStatus  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
KEYS = ROOT / ".data" / "demo_wallets.json"
RPC = "https://studio.genlayer.com/api"
WAIT = dict(interval=5000, retries=360)
GEN = 10 ** 18
MILLI = 10 ** 15
APPEAL_WINDOW = 900
LONG_STALL = 4 * 3600
SHORT_STALL = 120
T: dict = {}
OUT = ROOT / "deploy" / "live_run_transcript.json"

CATALOGUE = json.loads((FIXTURES / "catalogue.json").read_text(encoding="utf-8"))
CASES = {c["case_id"]: c for c in CATALOGUE["cases"]}
HASHES = CATALOGUE["hashes"]
CODE_REASONS = ("PRIMARY_UNAVAILABLE", "PRIMARY_CHANGED", "PRIMARY_UNREADABLE", "MANIPULATION",
                "HIDDEN_TEXT", "REFERENCE_COPY", "EXACT_DUPLICATE", "AUTHOR_MARK_MISSING",
                "PUBLISHED_AFTER_DEADLINE", "PUBLISHED_BEFORE_OPENING",
                "SUPPORTING_SOURCES_SHORT")


def log(*parts):
    print(*parts, flush=True)


def save():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(T, indent=2, sort_keys=True, default=str) + "\n",
                   encoding="utf-8", newline="\n")


def die(message: str):
    log("FATAL:", message)
    T["fatal"] = message
    save()
    raise SystemExit(1)


def check(condition, message: str):
    if not condition:
        die(message)


def retry(action, attempts=8, pause=20):
    last = None
    for attempt in range(attempts):
        try:
            return action()
        except Exception as err:          # noqa: BLE001 - transport errors vary
            last = err
            log(f"    transient ({attempt + 1}/{attempts}): {str(err)[:120]}")
            time.sleep(pause)
    raise last


def now_iso(offset: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + offset))


def epoch(iso: str) -> int:
    import calendar
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))


def wait_until(iso: str, why: str, margin: int = 30):
    remaining = epoch(iso) + margin - int(time.time())
    if remaining > 0:
        log(f"  waiting {remaining}s {why}")
        time.sleep(remaining)


def rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(RPC, data=body, headers={
        "Content-Type": "application/json", "User-Agent": "contribution-court-live-run"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def node_lines(tx: str) -> list:
    """Each node's model, vote and stdout tail for one transaction."""
    try:
        result = retry(lambda: rpc("eth_getTransactionByHash", [tx]))["result"]
    except Exception:                     # noqa: BLE001
        return []
    cd = result.get("consensus_data") or {}
    out = []
    for n in (cd.get("leader_receipt") or [])[:1] + (cd.get("validators") or []):
        nc = n.get("node_config") or {}
        out.append({"mode": n.get("mode"), "model": (nc.get("primary_model") or {}).get("model"),
                    "vote": (cd.get("votes") or {}).get(nc.get("address")),
                    "stdout": ((n.get("genvm_result") or {}).get("stdout") or "")[-900:]})
    return out


def leader_result(receipt) -> str:
    leader = receipt["consensus_data"]["leader_receipt"]
    entry = leader[0] if isinstance(leader, list) else leader
    return str(entry["execution_result"])


def votes(receipt) -> list:
    last_round = receipt.get("last_round") or {}
    named = last_round.get("validator_votes_name")
    if named:
        return [str(v) for v in named]
    mapping = (receipt.get("consensus_data") or {}).get("votes") or {}
    return [str(v).upper() for v in mapping.values()]


def accepted(receipt) -> bool:
    cast = [v.upper() for v in votes(receipt)]
    return sum(v.startswith("AGREE") for v in cast) > sum(v.startswith("DISAGREE") for v in cast)


def verify_fixtures(raw: str):
    """Every location a live round reads must serve exactly the local bytes."""
    for rel, digest in sorted(HASHES.items()):
        try:
            with urllib.request.urlopen(raw + rel, timeout=30) as response:
                body = response.read()
        except urllib.error.HTTPError as err:
            die(f"{raw + rel} is not reachable: {err}")
        check(hashlib.sha256(body).hexdigest() == digest,
              f"{raw + rel} does not serve the committed bytes")
    log(f"  verified {len(HASHES)} source locations against local bytes")


class Actor:
    def __init__(self, address: str, name: str, key: str):
        self.name = name
        self.address = address
        self.account = create_account(key)
        self.client = create_client(chain=studionet, account=self.account)
        self.wallet = self.account.address.lower()

    def read(self, fn: str, args: list):
        return retry(lambda: self.client.read_contract(address=self.address, function_name=fn,
                                                       args=args))

    def balance(self) -> int:
        return int(retry(lambda: self.client.get_balance(self.account.address)))

    def funded(self, at_least: int):
        balance = self.balance()
        if balance >= at_least:
            return
        log(f"  funding {self.name} from the faucet (balance {balance})")
        retry(lambda: self.client.fund_account(self.account.address, GEN))
        for _ in range(40):
            if self.balance() > balance:
                return
            time.sleep(5)
        die("the faucet did not fund " + self.name)

    def write(self, step: str, fn: str, args: list, expect: str = "SUCCESS", value: int = 0,
              attempts: int = 3) -> dict:
        """One transaction, recorded under a step name and never resent. A
        round the panel could not agree on is asked again: nothing it did
        applied, and the next round draws a different panel."""
        done = T.setdefault("steps", {})
        if step in done:
            return done[step]
        pending = T.setdefault("pending", {})
        record = {}
        for attempt in range(attempts):
            if step in pending:
                tx = pending[step]
                log(f"  {self.name}.{fn} resuming {tx}")
            else:
                if value:
                    self.funded(value * 2)
                tx = retry(lambda: self.client.write_contract(
                    address=self.address, function_name=fn, args=args, value=value,
                    consensus_max_rotations=3))
                tx = tx if isinstance(tx, str) else tx.hex()
                pending[step] = tx
                save()
                log(f"  {self.name}.{fn} tx {tx}")
            receipt = retry(lambda: self.client.wait_for_transaction_receipt(
                transaction_hash=tx, status=TransactionStatus.FINALIZED, **WAIT))
            result = leader_result(receipt)
            record = {"step": step, "actor": self.name, "method": fn, "tx": tx,
                      "status": str(receipt.get("status_name") or receipt.get("status")),
                      "leader_execution": result, "votes": votes(receipt),
                      "accepted": accepted(receipt)}
            leader = receipt["consensus_data"]["leader_receipt"]
            payload = (leader[0].get("result") or {}).get("payload") \
                if isinstance(leader, list) else None
            if payload is not None:
                record["returned"] = str(payload)[:300]
            if value:
                record["value_atto"] = str(value)
            log(f"    {record['status']} leader {result} votes {record['votes']}")
            del pending[step]
            save()
            if expect != "SUCCESS" or result != "SUCCESS" or record["accepted"]:
                break
            T.setdefault("rejected_rounds", []).append(dict(record, nodes=node_lines(tx)))
            log(f"    the panel did not agree ({attempt + 1}/{attempts}); asking again")
            save()
        done[step] = record
        save()
        check(record["leader_execution"] == expect,
              f"{step}: leader execution {record['leader_execution']}, expected {expect}")
        check(expect != "SUCCESS" or record["accepted"],
              f"{step}: the panel did not agree after {attempts} rounds")
        return record


def actors(address: str) -> dict:
    keys = json.loads(KEYS.read_text(encoding="utf-8"))
    return {name: Actor(address, name, key) for name, key in keys.items()}


def live_spec(name: str, raw: str, **overrides) -> str:
    data = json.loads(json.dumps(CATALOGUE["campaigns"][name]))
    for ref in data["reference_sources"]:
        ref["url"] = ref["url"].replace("{BASE}", raw)
    data.update({"submission_deadline": now_iso(5 * 3600), "appeal_window_seconds": APPEAL_WINDOW,
                 "stall_window_seconds": LONG_STALL})
    data.update(overrides)
    return json.dumps(data)


def source_list(pairs, raw: str) -> str:
    return json.dumps([{"url": raw + "sources/" + rel, "sha256": HASHES["sources/" + rel],
                        "label": label} for rel, label in pairs])


def campaign(ac: dict, key: str, name: str, raw: str, pool: int, **overrides) -> str:
    ids = T.setdefault("campaigns", {})
    owner = ac["owner"]
    if key not in ids:
        before = owner.read("list_campaigns", [0, 50])["total"]
        owner.write("create:" + key, "create_campaign", [live_spec(name, raw, **overrides)])
        page = owner.read("list_campaigns", [0, 50])
        check(page["total"] == before + 1, "create_campaign did not add a campaign")
        ids[key] = page["items"][-1]
        save()
    cid = ids[key]
    owner.write("fund:" + key, "fund_campaign", [cid], value=pool)
    owner.write("activate:" + key, "activate_campaign", [cid])
    return cid


def submit(ac: dict, step: str, cid: str, case_id: str, raw: str, contributor: str = None,
           value: int = None) -> str:
    case = CASES[case_id]
    who = ac[contributor or case["contributor"]]
    spec = json.loads(json.dumps(CATALOGUE["campaigns"][case["campaign"]]))
    bond = int(spec["submission_bond_atto"]) if value is None else value
    args = [cid, case["content_type"], raw + "sources/" + case["work"],
            HASHES["sources/" + case["work"]], case["publication_at"], case["summary"],
            source_list(case["supporting"], raw)]
    record = who.write(step, "submit_contribution", args, value=bond)
    return record.get("returned", "")


def submission_of(ac: dict, cid: str, case_id: str) -> str:
    wallet = ac[CASES[case_id]["contributor"]].wallet
    work = HASHES["sources/" + CASES[case_id]["work"]]
    page = ac["stranger"].read("list_campaign_submissions", [cid, 0, 50])
    for sid in page["items"]:
        sub = ac["stranger"].read("get_submission", [sid])
        if sub["contributor"] == wallet and sub["items"][0]["sha256"] == work:
            return sid
    die(f"no submission found for {case_id}")


def outcome(ac: dict, key: str, sid: str, expected: list, tx: str) -> dict:
    record = ac["stranger"].read("get_latest_receipt", [sid])
    got = [record["status"], record["reason_code"], record["score_band"]]
    code = expected[1] in CODE_REASONS
    held = got == expected
    row = {"submission_id": sid, "evaluation_id": record["evaluation_id"], "tx": tx,
           "expected": expected, "observed": got, "decided_by": "CODE" if code else "PANEL",
           "held": held, "overall_score": record["overall_score"],
           "originality_band": record["originality_band"],
           "criterion_results": [[f["id"], f["state"], f["by"]]
                                 for f in record["criterion_results"]],
           "rows": [[r["evidence_id"], r["status"]] for r in record["rows"]],
           "markers": record["markers"], "hidden": record["hidden"],
           "author_mark": record["author_mark"], "record_digest": record["record_digest"]}
    if not held:
        row["nodes"] = node_lines(tx)
    T.setdefault("outcomes", {})[key] = row
    save()
    log(f"  {key}: {' / '.join(got)} ({row['decided_by']}) held={held}")
    if code and not held:
        die(f"{key}: code-decided outcome {got}, expected {expected}")
    return record


def run_cases(ac: dict, raw: str, with_appeals: bool):
    cids = {"explainer": campaign(ac, "explainer", "explainer", raw, 400 * MILLI),
            "translation": campaign(ac, "translation", "translation", raw, 50 * MILLI),
            "docs": campaign(ac, "docs", "docs", raw, 70 * MILLI)}
    for case_id in sorted(CASES):
        case = CASES[case_id]
        cid = cids[case["campaign"]]
        submit(ac, "submit:" + case_id, cid, case_id, raw)
        sid = submission_of(ac, cid, case_id)
        T.setdefault("submissions", {})[case_id] = sid
        step = ac["stranger"].write("evaluate:" + case_id, "request_evaluation", [sid])
        outcome(ac, case_id, sid, case["expected"], step["tx"])
        if with_appeals and case.get("appeal_items"):
            party = ac["owner"] if case.get("appeal_party") == "owner" else ac[case["contributor"]]
            reason = ("The work copies a published source the first round never saw."
                      if party.name == "owner" else
                      "The cited run log backing the example was left out of the filing.")
            step = party.write("appeal:" + case_id, "appeal",
                               [sid, reason, source_list(case["appeal_items"], raw)])
            outcome(ac, case_id + ":appeal", sid, case["appeal_expected"], step["tx"])
    return cids


def refusals(ac: dict, cids: dict, raw: str):
    """Real transactions the contract must refuse, each with its sentence."""
    subs = T["submissions"]
    stranger = ac["stranger"]
    tries = [
        ("refuse:stranger_appeals", stranger, "appeal", [subs["CC01"], "I disagree.", "[]"],
         "only the contributor or the campaign owner can appeal"),
        ("refuse:second_appeal", ac["owner"], "appeal", [subs["CC14"], "Again.", "[]"],
         "only an EVALUATED submission can be appealed, once"),
        ("refuse:early_finalize", stranger, "finalize_submission", [subs["CC01"]],
         "the appeal window is open until"),
        ("refuse:evaluate_twice", stranger, "request_evaluation", [subs["CC01"]],
         "only a SUBMITTED contribution awaits its evaluation"),
        ("refuse:stranger_activates", stranger, "activate_campaign", [cids["docs"]],
         "only the campaign owner activates it"),
        ("refuse:reclaim_open_pool", ac["owner"], "reclaim_unreserved", [cids["explainer"]],
         "an OPEN campaign's pool is reclaimed after its submission deadline"),
    ]
    held = []
    for step, who, fn, args, sentence in tries:
        record = who.write(step, fn, args, expect="ERROR")
        check(sentence in record.get("returned", ""), f"{step}: refusal said {record}")
        held.append(step)
    # payable refusals return the deposit instead of raising
    before = int(stranger.read("get_claimable", [ac["owner"].wallet])["claimable_atto"])
    record = submit(ac, "refuse:owner_submits", cids["explainer"], "CC01", raw,
                    contributor="owner")
    check(record.startswith("'RETURNED: a campaign owner cannot submit") or
          "a campaign owner cannot submit" in record, f"owner submission: {record}")
    after = int(stranger.read("get_claimable", [ac["owner"].wallet])["claimable_atto"])
    check(after - before == 5 * MILLI, "the refused deposit was not credited back")
    held.append("refuse:owner_submits")
    T["refusals"] = held
    save()
    log(f"  {len(held)} refusals held")


def stall_and_cancel(ac: dict, raw: str) -> str:
    cid = campaign(ac, "stall", "explainer", raw, 60 * MILLI,
                   title="Explain Optimistic Democracy (stall demonstration)",
                   stall_window_seconds=SHORT_STALL)
    submit(ac, "submit:stall", cid, "CC09", raw)
    sid = submission_of(ac, cid, "CC09")
    T["stall_submission"] = sid
    ac["stranger"].write("refuse:early_close", "close_stalled_submission", [sid], expect="ERROR")
    sub = ac["stranger"].read("get_submission", [sid])
    wait_until(time.strftime("%Y-%m-%dT%H:%M:%SZ",
                             time.gmtime(epoch(sub["submitted_at"]) + SHORT_STALL)),
               "for the stall window")
    ac["stranger"].write("close_stalled", "close_stalled_submission", [sid])
    check(ac["stranger"].read("get_submission", [sid])["status"] == "CLOSED_UNRESOLVED",
          "the stalled submission did not close")
    ac["owner"].write("cancel:stall", "cancel_campaign", [cid])
    ac["owner"].write("reclaim:stall", "reclaim_unreserved", [cid])
    view = ac["stranger"].read("get_campaign", [cid, now_iso()])
    check(view["status"] == "CANCELLED" and view["pool_atto"] == "0",
          f"cancel and reclaim left {view}")
    return cid


def settle(ac: dict):
    stranger = ac["stranger"]
    last = max(epoch(stranger.read("get_submission", [sid])["appeal_deadline"])
               for sid in T["submissions"].values()
               if stranger.read("get_submission", [sid])["appeal_deadline"])
    wait_until(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last)),
               "for every appeal window to close")
    for case_id, sid in sorted(T["submissions"].items()):
        stranger.write("finalize:" + case_id, "finalize_submission", [sid])
        sub = stranger.read("get_submission", [sid])
        T.setdefault("settled", {})[case_id] = {k: sub[k] for k in (
            "status", "reward_atto", "bond_outcome", "finalized_at")}
        save()


def withdrawals(ac: dict):
    for name, actor in ac.items():
        owed = int(actor.read("get_claimable", [actor.wallet])["claimable_atto"])
        if owed <= 0:
            continue
        before = actor.balance()
        actor.write("withdraw:" + name, "withdraw", [])
        after = before
        for _ in range(24):
            after = actor.balance()
            if after - before >= owed:
                break
            time.sleep(5)
        check(after - before == owed, f"{name} withdrew {owed} but the wallet moved {after - before}")
        T.setdefault("withdrawn", {})[name] = str(owed)
        save()
        log(f"  {name} withdrew {owed} atto; its wallet rose by exactly that")


def ledger(ac: dict, address: str):
    stats = ac["stranger"].read("get_stats", [])
    balance = int(retry(lambda: ac["stranger"].client.get_balance(address)))
    T["ledger"] = {"stats": stats, "contract_balance_atto": str(balance)}
    save()
    check(int(stats["held_atto"]) == balance,
          f"the contract holds {balance} but accounts for {stats['held_atto']}")
    log(f"  contract balance {balance} atto equals what it accounts for")


def main():
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument("address")
    parser.add_argument("--raw-base", required=True)
    parser.add_argument("--phase", choices=("cases", "full"), required=True)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    raw = args.raw_base if args.raw_base.endswith("/") else args.raw_base + "/"
    if args.out:
        OUT = pathlib.Path(args.out)
    elif args.phase == "cases":
        OUT = ROOT / "deploy" / "diagnostics" / ("cases_" + args.address.lower()[:10] + ".json")
    if OUT.exists():
        T.update(json.loads(OUT.read_text(encoding="utf-8")))
    T.update({"address": args.address, "raw_base": raw, "phase": args.phase,
              "network": "studionet"})
    T.setdefault("started_at", now_iso())
    save()
    ac = actors(args.address)
    log("wallets:", ", ".join(f"{n} {a.wallet}" for n, a in ac.items()))
    verify_fixtures(raw)
    for name in ac:
        ac[name].funded(300 * MILLI if name != "owner" else 900 * MILLI)
    cids = run_cases(ac, raw, with_appeals=args.phase == "full")
    if args.phase == "full":
        refusals(ac, cids, raw)
        stall_and_cancel(ac, raw)
        settle(ac)
        withdrawals(ac)
        ledger(ac, args.address)
    outcomes = T.get("outcomes", {})
    T["summary"] = {"held": sorted(k for k, v in outcomes.items() if v["held"]),
                    "not_held": sorted(k for k, v in outcomes.items() if not v["held"])}
    T["finished_at"] = now_iso()
    save()
    log("DONE", json.dumps(T["summary"]))


if __name__ == "__main__":
    main()
