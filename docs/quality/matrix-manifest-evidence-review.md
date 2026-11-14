# Qualification manifests on resume

Matrix resume already checked the request identity, event stream and paper
files. It accepted any existing manifest path after those checks, however.
A retained manifest could describe different files, claim an unchecked
review or point outside the job. A later job could also change which claims
the aggregate recorded for an earlier one.

The matrix now builds the expected automation receipt from the verified
paper and request. It checks the stored receipt before reuse and before
reporting an earlier job. A matching receipt is left byte-for-byte intact.
If the receipt no longer matches, the tool writes a separate automation
receipt and uses it for the aggregate without rerunning inference.
Existing review files remain available for independent inspection.
The matrix does not issue, preserve as its own, or promote human review
claims. No paper or model result changes.

Regression tests cover full receipt reuse, an incorrect artifact digest,
an edited visual gate, external and symlink paths, and a later job changing
an earlier receipt. The first three targeted failure cases were reproduced
against the old runner. Existing request, model pin and file checks remain
in place. This is a scoped audit of the receipt flow, not a full tooling
audit or qualification of a generated paper.
