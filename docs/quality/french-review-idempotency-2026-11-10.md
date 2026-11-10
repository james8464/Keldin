# Repeated optional review saves

The optional review recorder gives identical review content the same record ID.
Previously, a second save generated a new timestamp, so the writer rejected its
own unchanged content as a conflicting record. A synthetic reproduction confirmed
the refusal while preserving the first file. This was a usability issue, not
evidence that a teacher reviewed a paper or that any paper passed qualification.

The writer now accepts an existing JSON object only when its keys and all values
other than `created_at` match the requested record. Canonical JSON comparison
preserves distinctions between booleans, integers and floating-point values.
An accepted retry returns the existing path without rewriting its bytes or date.
Changed identity, reviewer, scores, decision, notes, schema or additional fields
still refuse. Malformed records and symlinks, including dangling symlinks, refuse.
Approval requirements, credentials and manifest binding are unchanged.

The initial repeat-save regression failed once with 17 controls passing. A
separate dangling-symlink regression failed twice with 17 controls passing.
After the repair, 22 focused tests passed. These overlapping runs are not added
together. All fixtures are explicitly synthetic and use owned temporary files.
Root reviewed the complete narrow source/test delta against the earlier complete
file reads. No concurrent-writer or crash-durability guarantee is claimed.

Combined release tests, packaged acceptance and protected checks remain separate.
The optional review feature does not restore a mandatory teacher-review release
requirement that the user waived.
