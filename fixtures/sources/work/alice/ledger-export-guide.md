# Exporting the ledger

Author wallet: 0xef6e006cd8a68c9cfe88a3640415ab0c79c71921
Published: 2026-09-14

Based on the ledger export feature specification.

`ledger export` writes the ledger's entries to a file.

## Parameters

| Flag | Required | What it does |
|---|---|---|
| `--format json` or `--format csv` | yes | json writes one object per entry; csv writes a header row, then one row per entry |
| `--since YYYY-MM-DD` | no | exports only entries on or after that date; leave it out to export everything |
| `--out path` | yes | the file to write; an existing file is replaced |

## Example

    ledger export --format csv --since 2026-09-01 --out september.csv

The run log in the cited example output shows this command finishing with
exit code 0.

## When it fails

Exit code 2 means a required flag is missing. Exit code 3 means the output
file could not be written, for example because the folder does not exist.
