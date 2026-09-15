# Deployment

Only facts a receipt, a read or a command output shows. Every value below is in
`deploy/deployment.json`, written by `scripts/deploy_studionet.py`.

## Deployment of record

| Item | Value |
|---|---|
| Network | GenLayer StudioNet, chain id 61999 |
| RPC | `https://studio.genlayer.com/api` |
| Contract | `0x0f47E6A49845c983fa9B61E441928F3435E9Adde` |
| Explorer | https://explorer-studio.genlayer.com/address/0x0f47E6A49845c983fa9B61E441928F3435E9Adde |
| Deployment transaction | `0x43bb908c8d56e1a52561cb6191757dfb74a57511a7398109a930431356be2d89` |
| Deployed at | 2026-09-15T18:15:36Z |
| Receipt | status FINALIZED, leader execution SUCCESS, votes AGREE, IDLE, AGREE, AGREE, IDLE |
| Source commit | `b76700cdaea19f71cdd44f1bacace0dd20bcc77f` |
| Source blob | `689b45cbd08cf27c9a4a1b4f418275c9c6a407ca` |
| Source sha256 | `0a5d1018196ab943a135f2b49b8844a09a2f859af3a3480d84a31d16e310ac16` |
| Deployed source sha256 (`gen_getContractCode`) | `0a5d1018196ab943a135f2b49b8844a09a2f859af3a3480d84a31d16e310ac16` - byte-identical |
| Deployer (public address) | `0x68656Dc05F266c8cE2AE6f1F8715c24732b2596b` |
| Runner | `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6` |

The deployer key is in `.data/deployer.json`, gitignored and never printed.

## Post-deployment read checks

| Check | Result |
|---|---|
| `python scripts/deploy_studionet.py --verify` | deployed and repository sha256 equal; byte-identical; 26 schema methods |
| `python -m pytest tests/integration -q` (after the live run) | covers source parity, schema, views, balance equals accounting, every live outcome and record digest, every specification hash, settled submissions final with their entitlements. 6 of 7 passed in one run with the live-outcome check failing on transport; that check passed on its own re-run; further runs hit StudioNet's 500-requests-an-hour limit (1 opt-in live write skipped) |

## Toolchain

| Tool | Version |
|---|---|
| Python | 3.12.2 |
| genlayer-py | 0.16.3 |
| genlayer-test (Direct Mode) | 0.29.2 |
| genvm-linter | 0.11.0, GenVM bundle v0.3.0-rc7 |

`genvm-lint check contracts/contribution_court.py --json`: lint ok (3 checks),
validation ok, 26 methods (15 view, 11 write). One warning, I200: a newer
py-genlayer runner (`1zr6nqk5...`) is available. The contract stays on the
runner this author has deployed and run live on StudioNet; the newer runner was
not tested here.

The GenLayer documentation server was unreachable from this environment during
the build ("No transport found for sessionId"), so API facts were taken from the
installed SDK, the linter's validation and live StudioNet behaviour.

## How the deployment was made

1. The contract was committed; the script refuses a modified, non-ASCII or CR-bearing file.
2. `python scripts/deploy_studionet.py` signed the deployment, waited for FINALIZED, required leader execution SUCCESS, read the source back with `gen_getContractCode` and compared sha256.
3. The record was written only after those checks.

## Disposable diagnostic deployment

| Address | Source commit | Purpose | Record |
|---|---|---|---|
| `0xB1fAa2bf3e1807fE1AB86fbe186452033c5a6566` | `4a88111` | the diagnostic pass: every catalogue case evaluated once, per-node readings recorded | `deploy/diagnostics/deployment_0xb1faa2bf.json`, `deploy/diagnostics/cases_0xb1faa2bf.json` |

It is never the deployment of record. What it showed, and what changed in
response, is in [`CONSENSUS.md`](CONSENSUS.md).

## Live run

| Item | Value |
|---|---|
| Transcript | `deploy/live_run_transcript.json` |
| Transactions | 71 |
| Window | 2026-09-15T18:15:57Z to 2026-09-15T20:00:18Z |
| Fixtures served from | `https://raw.githubusercontent.com/Olawalter/ContributorCourt/b76700cdaea19f71cdd44f1bacace0dd20bcc77f/fixtures/` |
| Outcomes held | 15 of 16 |
| Ledger at the end | chain balance 530000000000000000 atto = accounted 530000000000000000 atto |

Results and the plain statement of what did not hold: [`../README.md`](../README.md#verified).

## Clean-clone check

A fresh `git clone` of `720dccf` from GitHub, with nothing carried over from the
working tree, on 2026-09-15:

| Command | Result |
|---|---|
| `ruff check .` | clean |
| `python scripts/generate_fixtures.py --check` | fixtures match (20 files) |
| `python -m pytest tests/direct -q` | 194 passed |
| `python scripts/preflight.py` | 7 checks, 0 failed |
| `genvm-lint check contracts/contribution_court.py --json` | ok, 26 methods |

CI (`.github/workflows/ci.yml`: ruff, fixtures, Direct Mode, genvm-lint) passed on `720dccf`.
