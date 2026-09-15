"""Shared scenario data and mock helpers for the Direct Mode suite.

The suite runs the real contract inside the official genlayer-test direct
runner (SDK resolved from the contract's own pinned runner hash). Only the
external boundaries are mocked, and narrowly:

- web fetches: every file under fixtures/ is served at BASE + its relative
  path, byte for byte; any other GET answers 404, so the contract records the
  item UNAVAILABLE;
- the one panel prompt, matched on its header, answered with a JSON object.

Nothing in the contract is patched. Every status, score, band and atto in
this suite is produced by the contract's own code from those inputs.
"""

import calendar
import copy
import hashlib
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = "contracts/contribution_court.py"
MODULE = "_contract_contribution_court"
FIXTURES = ROOT / "fixtures"

BASE = "https://sources.example.org/contribution-court/"
NOW = "2026-09-15T12:00:00Z"
PANEL_PATTERN = r"(?s)ContributionCourt panel"
MILLI = 10 ** 15
POOL = 200 * MILLI
BOND = 5 * MILLI

WALLETS = json.loads((FIXTURES / "wallets.json").read_text(encoding="utf-8"))
CATALOGUE = json.loads((FIXTURES / "catalogue.json").read_text(encoding="utf-8"))
CASES = {c["case_id"]: c for c in CATALOGUE["cases"]}
HASHES = CATALOGUE["hashes"]


def wallet(name: str) -> str:
    return WALLETS[name]


def as_sender(direct_vm, name: str):
    direct_vm.sender = bytes.fromhex(WALLETS[name][2:])


def sha256_hex(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def file_bytes(rel: str) -> bytes:
    return (FIXTURES / rel).read_bytes()


def epoch(iso: str) -> int:
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))


def later(seconds: int, start: str = NOW) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch(start) + seconds))


def warp(direct_vm, timestamp: str):
    """Move the transaction clock. genlayer-test 0.29.2's warp() updates the
    VM's datetime but its message refresh copies only sender/origin into the
    SDK's cached gl.message_raw, so a warp after deploy never reaches contract
    code. Set both; this touches the test clock only."""
    direct_vm.warp(timestamp)
    gl = sys.modules.get("genlayer.gl")
    if gl is not None and getattr(gl, "message_raw", None) is not None:
        gl.message_raw["datetime"] = timestamp


# -- campaigns -------------------------------------------------------------------

def spec(name: str, base: str = BASE, **overrides) -> dict:
    data = copy.deepcopy(CATALOGUE["campaigns"][name])
    for ref in data["reference_sources"]:
        ref["url"] = ref["url"].replace("{BASE}", base)
    data.update(overrides)
    return data


def spec_json(name: str, base: str = BASE, **overrides) -> str:
    return json.dumps(spec(name, base, **overrides))


def open_campaign(contract, direct_vm, name: str = "explainer", pool: int = POOL,
                  owner: str = "owner", **overrides) -> str:
    as_sender(direct_vm, owner)
    campaign_id = contract.create_campaign(spec_json(name, **overrides))
    direct_vm.value = pool
    contract.fund_campaign(campaign_id)
    direct_vm.value = 0
    contract.activate_campaign(campaign_id)
    return campaign_id


def source_entry(rel: str, label: str, base: str = BASE) -> dict:
    return {"url": base + "sources/" + rel, "sha256": HASHES["sources/" + rel], "label": label}


def submit(contract, direct_vm, campaign_id: str, case_id: str, contributor: str = None,
           bond: int = BOND, base: str = BASE, **overrides) -> str:
    case = CASES[case_id]
    args = {"content_type": case["content_type"],
            "primary_url": base + "sources/" + case["work"],
            "primary_sha256": HASHES["sources/" + case["work"]],
            "publication_at": case["publication_at"], "evidence_summary": case["summary"],
            "supporting_json": json.dumps([source_entry(rel, label, base)
                                           for rel, label in case["supporting"]])}
    args.update(overrides)
    as_sender(direct_vm, contributor or case["contributor"])
    direct_vm.value = bond
    result = contract.submit_contribution(campaign_id, args["content_type"],
                                          args["primary_url"], args["primary_sha256"],
                                          args["publication_at"], args["evidence_summary"],
                                          args["supporting_json"])
    direct_vm.value = 0
    return result


# -- mocks ---------------------------------------------------------------------------

def serve_all(direct_vm, base: str = BASE, skip=(), override=None):
    """Serve every fixture file at base + relative path (exact bytes), with
    `override` replacing some bodies."""
    override = override or {}
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(FIXTURES).as_posix()
        if rel in skip:
            continue
        body = override.get(rel, path.read_bytes())
        direct_vm.mock_web("^" + re.escape(base + rel) + "$", {
            "method": "GET", "response": {"status": 200, "headers": {}, "body": body}})


def mock_panel(direct_vm, answer):
    direct_vm.mock_llm(PANEL_PATTERN, answer if isinstance(answer, str) else json.dumps(answer))


def stage(direct_vm, answer=None, base: str = BASE, skip=(), override=None):
    direct_vm.clear_mocks()
    serve_all(direct_vm, base, skip, override)
    if answer is not None:
        mock_panel(direct_vm, answer)


def answer_for(case_id: str, key: str = "answer") -> dict:
    return copy.deepcopy(CASES[case_id][key])


def evaluate(contract, direct_vm, submission_id: str, answer=None, requester: str = "stranger",
             **stage_kwargs) -> dict:
    stage(direct_vm, answer, **stage_kwargs)
    as_sender(direct_vm, requester)
    evaluation_id = contract.request_evaluation(submission_id)
    return contract.get_evaluation(evaluation_id)


def run_case(contract, direct_vm, case_id: str, campaign_id: str = None) -> dict:
    case = CASES[case_id]
    campaign_id = campaign_id or open_campaign(contract, direct_vm, case["campaign"])
    submission_id = submit(contract, direct_vm, campaign_id, case_id)
    return evaluate(contract, direct_vm, submission_id, answer_for(case_id))


def sources_json(pairs, base: str = BASE) -> str:
    return json.dumps([source_entry(rel, label, base) for rel, label in pairs])


def finding(record: dict, subject_id: str) -> dict:
    for f in record["criterion_results"]:
        if f["id"] == subject_id:
            return f
    raise KeyError(subject_id)


def claimable(contract, name: str) -> int:
    return int(contract.get_claimable(wallet(name))["claimable_atto"])


def assert_conserved(contract, deposited: int, withdrawn: int = 0):
    """Everything paid in is a pool, a held bond or a claimable credit, until
    it is withdrawn."""
    stats = contract.get_stats()
    assert int(stats["held_atto"]) == deposited - withdrawn, stats


def captured_payload(direct_vm) -> dict:
    result, _leader_fn, _validator_fn = direct_vm._captured_validators[-1]
    return json.loads(result)


def captured_ctx(direct_vm) -> dict:
    _result, leader_fn, _validator_fn = direct_vm._captured_validators[-1]
    for cell in leader_fn.__closure__ or ():
        value = cell.cell_contents
        if isinstance(value, dict) and "subject_id" in value:
            return value
    raise AssertionError("round context not found")
