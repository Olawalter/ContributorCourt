#!/usr/bin/env python3
"""Create the demo wallets once: private keys in .data/demo_wallets.json
(gitignored, never printed), public addresses in fixtures/wallets.json.

The fixture works carry their contributor's wallet address as the
authorship mark, so the addresses must exist before the fixtures are
generated, and the live run must sign with exactly these keys.

    python scripts/make_wallets.py            # refuses to overwrite
"""

import json
import pathlib
import sys

from genlayer_py import create_account

ROOT = pathlib.Path(__file__).resolve().parents[1]
KEYS = ROOT / ".data" / "demo_wallets.json"
ADDRESSES = ROOT / "fixtures" / "wallets.json"
NAMES = ("owner", "alice", "bob", "carol", "dave", "stranger")


def main():
    if KEYS.exists() or ADDRESSES.exists():
        sys.exit("wallets already exist; delete both files deliberately to recreate them")
    KEYS.parent.mkdir(exist_ok=True)
    ADDRESSES.parent.mkdir(exist_ok=True)
    keys = {}
    addresses = {}
    for name in NAMES:
        account = create_account()
        keys[name] = account.key.hex()
        addresses[name] = account.address.lower()
    KEYS.write_text(json.dumps(keys, indent=1), encoding="utf-8")
    ADDRESSES.write_text(json.dumps(addresses, indent=1) + "\n", encoding="utf-8")
    print("wrote", len(NAMES), "wallets; addresses in", ADDRESSES.relative_to(ROOT))


if __name__ == "__main__":
    main()
