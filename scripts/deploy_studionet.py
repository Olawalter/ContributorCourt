#!/usr/bin/env python3
"""Deploy contracts/contribution_court.py to GenLayer StudioNet and record the
evidence a reviewer needs to check the deployment against this repository.

  python scripts/deploy_studionet.py            # deploy + record
  python scripts/deploy_studionet.py --verify   # re-check the recorded one
  python scripts/deploy_studionet.py --disposable  # a diagnostic deployment,
                                                   # recorded under deploy/diagnostics/

What it does, and refuses to do:
- refuses to deploy unless contracts/contribution_court.py is committed and
  unmodified (the deployment must correspond to an identifiable commit);
- signs with a deployer key kept in .data/deployer.json (gitignored, never
  printed); StudioNet is gasless, so the key holds no funds;
- waits for FINALIZED and asserts the leader's execution result is SUCCESS -
  lifecycle status alone is not execution success;
- reads the deployed source back with gen_getContractCode and compares its
  sha256 with the committed file (source parity);
- writes deploy/deployment.json. It claims only what the receipt shows.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import studionet_transport  # noqa: E402,F401 - retries RPC transport failures
from genlayer_py import create_account, create_client  # noqa: E402
from genlayer_py.chains import studionet  # noqa: E402
from genlayer_py.types import TransactionStatus  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = "contracts/contribution_court.py"
CONTRACT = ROOT / CONTRACT_PATH
KEY_FILE = ROOT / ".data" / "deployer.json"
RECORD = ROOT / "deploy" / "deployment.json"
RPC = "https://studio.genlayer.com/api"
EXPLORER = "https://explorer-studio.genlayer.com"
WAIT = dict(interval=5000, retries=240)


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def rpc(method: str, params: list):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    last = None
    for attempt in range(6):
        try:
            request = urllib.request.Request(
                RPC, data=body, headers={"Content-Type": "application/json",
                                         "User-Agent": "contribution-court-deploy"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode())
        except Exception as err:          # noqa: BLE001 - transport errors vary
            last = err
            time.sleep(10 * (attempt + 1))
    raise last


def deployed_source(address: str) -> bytes:
    """The deployed source bytes. StudioNet answers gen_getContractCode with
    the source (plain text or base64, depending on version); both decode to
    the exact bytes that were deployed."""
    answer = {}
    for _ in range(24):
        answer = rpc("gen_getContractCode", [address])
        result = answer.get("result")
        if isinstance(result, str) and result:
            if result.lstrip().startswith("#"):
                return result.encode("utf-8")
            try:
                return base64.b64decode(result, validate=True)
            except Exception:
                return result.encode("utf-8")
        time.sleep(10)
    raise SystemExit(f"gen_getContractCode returned nothing for {address}: {answer}")


def load_account():
    KEY_FILE.parent.mkdir(exist_ok=True)
    if KEY_FILE.exists():
        key = json.loads(KEY_FILE.read_text())["private_key"]
        return create_account(key)
    account = create_account()
    KEY_FILE.write_text(json.dumps({"private_key": account.key.hex()}))
    return account


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


def status_name(receipt) -> str:
    for key in ("status_name", "status"):
        value = receipt.get(key)
        if value is not None:
            return str(value)
    return ""


def verify(record: dict) -> None:
    source = CONTRACT.read_bytes()
    deployed = deployed_source(record["contract_address"])
    ok = hashlib.sha256(deployed).hexdigest() == hashlib.sha256(source).hexdigest()
    print("deployed source sha256:", hashlib.sha256(deployed).hexdigest())
    print("repository  sha256:   ", hashlib.sha256(source).hexdigest())
    print("byte-identical:", ok)
    schema = rpc("gen_getContractSchema", [record["contract_address"]]).get("result") or {}
    print("schema methods:", len((schema.get("methods") or {})))
    if not ok:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--disposable", action="store_true")
    args = parser.parse_args()
    if args.verify:
        verify(json.loads(RECORD.read_text(encoding="utf-8")))
        return

    raw = CONTRACT.read_bytes()
    if b"\r" in raw:
        raise SystemExit("refusing: the contract carries CR bytes")
    if any(b > 127 for b in raw):
        raise SystemExit("refusing: the contract carries non-ASCII bytes")
    if git("status", "--porcelain", "--", CONTRACT_PATH):
        raise SystemExit("refusing: " + CONTRACT_PATH + " has uncommitted changes")
    commit = git("log", "-1", "--format=%H", "--", CONTRACT_PATH)
    head = git("rev-parse", "HEAD")
    blob = git("rev-parse", "HEAD:" + CONTRACT_PATH)

    account = load_account()
    client = create_client(chain=studionet, account=account)
    signer = str(account.address)
    print("signer:", signer)
    print("source commit:", commit, "blob:", blob)

    tx = client.deploy_contract(code=raw.decode("utf-8"), args=[],
                                consensus_max_rotations=3)
    tx = tx if isinstance(tx, str) else tx.hex()
    print("deploy tx:", tx, flush=True)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx, status=TransactionStatus.FINALIZED, **WAIT)
    result = leader_result(receipt)
    address = ((receipt.get("data") or {}).get("contract_address")
               or receipt.get("recipient") or receipt.get("to_address"))
    print("status:", status_name(receipt), "leader:", result, "votes:", votes(receipt))
    print("contract:", address)
    if result != "SUCCESS" or not address:
        raise SystemExit("deployment did not execute successfully; nothing recorded")

    deployed = deployed_source(address)
    parity = hashlib.sha256(deployed).hexdigest() == hashlib.sha256(raw).hexdigest()
    record = {
        "network": "studionet",
        "chain_id": studionet.id,
        "rpc": RPC,
        "explorer": EXPLORER,
        "contract_address": address,
        "deploy_tx": tx,
        "signer": signer,
        "status": status_name(receipt),
        "leader_execution": result,
        "votes": votes(receipt),
        "source_commit": commit,
        "head_at_deploy": head,
        "source_blob": blob,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "deployed_sha256": hashlib.sha256(deployed).hexdigest(),
        "byte_identical": parity,
        "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "explorer_contract": f"{EXPLORER}/address/{address}",
        "explorer_tx": f"{EXPLORER}/tx/{tx}",
    }
    target = RECORD
    if args.disposable:
        record["purpose"] = "disposable diagnostic deployment; never the deployment of record"
        target = ROOT / "deploy" / "diagnostics" / ("deployment_" + address.lower()[:10] + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print("byte-identical:", parity)
    print("recorded:", target.relative_to(ROOT))
    if not parity:
        sys.exit(1)


if __name__ == "__main__":
    main()
