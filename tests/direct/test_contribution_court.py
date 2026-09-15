"""The lifecycle: a campaign fixed and funded, contributions filed with their
bonds, one consensus round each, the appeal window, finalization and the pull
payment - and every case in the catalogue deriving the status it must."""

import json

import pytest

from tests.direct.support import (
    BOND, CASES, MILLI, POOL, answer_for, as_sender, assert_conserved, claimable, evaluate,
    finding, later, open_campaign, run_case, spec_json, stage, submit, warp)


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_every_case_derives_its_status(court, direct_vm, case_id):
    case = CASES[case_id]
    record = run_case(court, direct_vm, case_id)
    status, reason, band = case["expected"]
    assert (record["status"], record["reason_code"], record["score_band"]) == \
        (status, reason, band), record
    assert record["panel_state"] == ("SKIPPED" if case["answer"] is None else "ASSESSED")


def test_an_approved_contribution_is_paid_through_the_ledger(court, direct_vm):
    campaign_id = open_campaign(court, direct_vm)
    view = court.get_campaign(campaign_id, later(1))
    assert view["status"] == "OPEN" and view["pool_atto"] == str(POOL)
    submission_id = submit(court, direct_vm, campaign_id, "CC01")
    assert submission_id == "SB-000001"
    view = court.get_campaign(campaign_id, later(1))
    assert view["reserved_atto"] == str(50 * MILLI)
    assert court.get_submission(submission_id)["status"] == "SUBMITTED"
    assert_conserved(court, POOL + BOND)

    record = evaluate(court, direct_vm, submission_id, answer_for("CC01"))
    assert record["status"] == "APPROVED" and record["score_band"] == "GOLD"
    assert record["overall_score"] == 100 and record["reward_atto"] == str(50 * MILLI)
    assert record["originality_band"] == "ORIGINAL" and record["author_mark"] is True
    assert record["evidence_sufficiency"] == "SUFFICIENT"
    assert record["source_reachability"] == "REACHABLE"
    assert finding(record, "C1")["quotes"][0]["evidence_id"] == "E1"
    assert court.is_rewardable(submission_id) == {
        "found": True, "submission_id": submission_id, "rewardable": True, "final": False,
        "score_band": "GOLD"}
    entitlement = court.get_reward_entitlement(submission_id)
    assert entitlement["pending_atto"] == str(50 * MILLI) and entitlement["entitled_atto"] == "0"

    status = court.get_submission_status(submission_id, later(60))
    assert status["appeal_window_open"] is True and status["can_finalize"] is False
    with direct_vm.expect_revert("the appeal window is open until"):
        court.finalize_submission(submission_id)
    warp(direct_vm, later(3 * 86400 + 1))
    as_sender(direct_vm, "stranger")
    assert court.finalize_submission(submission_id) == "REWARDED"
    assert court.is_rewardable(submission_id)["final"] is True
    assert court.get_reward_entitlement(submission_id)["entitled_atto"] == str(50 * MILLI)
    assert claimable(court, "alice") == 50 * MILLI + BOND
    view = court.get_campaign(campaign_id, later(3 * 86400 + 2))
    assert view["reserved_atto"] == "0" and view["pool_atto"] == str(POOL - 50 * MILLI)
    assert view["paid_atto"] == str(50 * MILLI)
    assert_conserved(court, POOL + BOND)

    as_sender(direct_vm, "alice")
    assert court.withdraw() == str(50 * MILLI + BOND)
    with direct_vm.expect_revert("nothing to withdraw"):
        court.withdraw()
    assert_conserved(court, POOL + BOND, 50 * MILLI + BOND)


def test_the_specification_is_stored_whole_and_hashed(court, direct_vm, mod):
    campaign_id = open_campaign(court, direct_vm)
    view = court.get_definition_hash(campaign_id)
    stored = court.get_campaign(campaign_id, later(1))["specification"]
    assert view["definition_hash"] == view["recomputed_hash"] \
        == mod._sha256_hex(mod._canonical(stored))
    assert stored == json.loads(spec_json("explainer"))
    record = run_case(court, direct_vm, "CC01", campaign_id)
    assert record["definition_hash"] == view["definition_hash"]


def test_a_forfeited_bond_goes_to_the_pool(court, direct_vm):
    campaign_id = open_campaign(court, direct_vm)
    submission_id = submit(court, direct_vm, campaign_id, "CC02")
    record = evaluate(court, direct_vm, submission_id, answer_for("CC02"))
    assert record["bond_outcome"] == "FORFEIT"
    warp(direct_vm, later(3 * 86400 + 1))
    assert court.finalize_submission(submission_id) == "FINALIZED"
    view = court.get_campaign(campaign_id, later(3 * 86400 + 2))
    assert view["pool_atto"] == str(POOL + BOND) and view["reserved_atto"] == "0"
    assert claimable(court, "bob") == 0
    assert_conserved(court, POOL + BOND)


def test_a_returned_bond_goes_back_to_the_contributor(court, direct_vm):
    campaign_id = open_campaign(court, direct_vm)
    submission_id = submit(court, direct_vm, campaign_id, "CC03")
    record = evaluate(court, direct_vm, submission_id, answer_for("CC03"))
    assert record["status"] == "REJECTED" and record["bond_outcome"] == "RETURN"
    warp(direct_vm, later(3 * 86400 + 1))
    court.finalize_submission(submission_id)
    assert claimable(court, "carol") == BOND
    assert court.get_campaign(campaign_id, later(3 * 86400 + 2))["pool_atto"] == str(POOL)


def test_the_translation_campaign_rewards_a_credited_translation(court, direct_vm):
    record = run_case(court, direct_vm, "CC10")
    assert record["originality_band"] == "ATTRIBUTED_DERIVATIVE"
    assert record["reward_atto"] == str(20 * MILLI)


def test_stage_serves_every_fixture(direct_vm, court):
    stage(direct_vm)
