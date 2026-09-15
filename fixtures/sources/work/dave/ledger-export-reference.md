# ledger export reference

Author wallet: 0x6c9de015919764af69580cbc7382a93cb788e36a
Published: 2026-09-14

Based on the ledger export feature specification.

`ledger export` writes the ledger's entries to a file.

- `--format json|csv` (required): json gives one object per entry, csv gives a
  header row and one row per entry.
- `--since YYYY-MM-DD` (optional): only entries on or after the date; without
  it every entry is exported.
- `--out path` (required): the file to write; an existing file is replaced.

Example:

    ledger export --format json --out all-entries.json

Exit codes: 0 success, 2 missing required flag, 3 output file not writable.
