#!/usr/bin/env python3
"""Release gate: the repository says only what is true of itself.

    python scripts/preflight.py

Checks, each printed PASS or FAIL:
- the contract is ASCII with LF endings and a pinned runner header;
- the fixtures regenerate byte for byte;
- every code symbol a document names in backticks exists in the contract;
- no document carries an unfilled placeholder;
- the README's Direct Mode count is the suite's own count;
- every contract address a document names has a record under deploy/;
- the deployment record names the bytes of the contract in the tree.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "contribution_court.py"
RECORD = ROOT / "deploy" / "deployment.json"
DOCS = [ROOT / "README.md", ROOT / "DECISION.md", ROOT / "SUBMISSION.md"] + \
    sorted((ROOT / "docs").glob("*.md"))
RESULTS = []
# names documents use that belong to the toolchain, the repository or JSON, not the contract
EXTERNAL = {"gen_getContractCode", "gen_getContractSchema", "run_nondet_unsafe",
            "response_format", "consensus_max_rotations", "read_contract", "create_client",
            "CONTRIBUTION_LIVE_WRITES", "raw_base"}
ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, ok))
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok or not detail else "  -> " + detail))


def main():
    raw = CONTRACT.read_bytes()
    source = raw.decode("utf-8")
    check("the contract is ASCII with LF endings and a pinned runner",
          b"\r" not in raw and all(b < 128 for b in raw)
          and re.match(r"# v[0-9.]+\n# \{ \"Depends\": \"py-genlayer:[0-9a-z]{40,}\" \}\n\n",
                       source) is not None)

    fixtures = subprocess.run([sys.executable, "scripts/generate_fixtures.py", "--check"],
                              cwd=ROOT, capture_output=True, text=True)
    check("the fixtures regenerate byte for byte", fixtures.returncode == 0,
          fixtures.stdout + fixtures.stderr)

    stray = []
    for path in DOCS:
        if not path.exists():
            continue
        for token in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\(|`)", path.read_text(
                encoding="utf-8")):
            symbolic = token.startswith("_") or "_" in token
            if not symbolic or token in EXTERNAL:
                continue
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])",
                         source) is None:
                stray.append(path.name + ":" + token)
    check("every code symbol the documents name exists in the contract", not stray,
          ", ".join(sorted(set(stray))))

    pending = [p.name for p in DOCS if p.exists()
               and re.search(r"(?<![A-Za-z0-9])[A-Z0-9_]+_PENDING(?![A-Za-z0-9_])", p.read_text(encoding="utf-8"))]
    check("no document carries an unfilled placeholder", not pending, ", ".join(pending))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    claimed = re.search(r"`python -m pytest tests/direct -q` \| (\d+) passed", readme)
    collected = subprocess.run([sys.executable, "-m", "pytest", "tests/direct", "--collect-only",
                                "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True,
                               text=True)
    found = re.search(r"(\d+) tests? collected", collected.stdout)
    check("the README's Direct Mode count is the suite's own count",
          bool(claimed and found and claimed.group(1) == found.group(1)),
          (claimed.group(1) if claimed else "unstated") + " claimed vs "
          + (found.group(1) if found else "uncollected"))

    known = {a.lower() for a in json.loads((ROOT / "fixtures" / "wallets.json").read_text(
        encoding="utf-8")).values()}
    for record in list((ROOT / "deploy").rglob("*.json")):
        known |= {a.lower() for a in ADDRESS.findall(record.read_text(encoding="utf-8"))}
    stray = [p.name + ":" + a for p in DOCS if p.exists()
             for a in ADDRESS.findall(p.read_text(encoding="utf-8")) if a.lower() not in known]
    check("every address a document names has a record under deploy/", not stray,
          ", ".join(sorted(set(stray))))

    if RECORD.exists():
        record = json.loads(RECORD.read_text(encoding="utf-8"))
        tree = hashlib.sha256(raw).hexdigest()
        check("the deployment record names the contract in the tree",
              record.get("source_sha256") == tree,
              "record " + str(record.get("source_sha256")) + " vs tree " + tree)
    else:
        check("deployment record (not deployed yet)", True)

    failed = [r for r in RESULTS if not r[1]]
    print("\n" + str(len(RESULTS)) + " checks, " + str(len(failed)) + " failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
