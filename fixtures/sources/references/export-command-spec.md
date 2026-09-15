# Feature specification: ledger export

Command: ledger export

The command writes the ledger's entries to a file.

Parameters:
- --format <json|csv>  Output format. Required. json writes one object per
  entry; csv writes a header row and one row per entry.
- --since <YYYY-MM-DD>  Only entries on or after this date. Optional; without
  it every entry is exported.
- --out <path>  File to write. Required. An existing file is replaced.

Exit codes: 0 on success, 2 when a required parameter is missing, 3 when the
output file cannot be written.
