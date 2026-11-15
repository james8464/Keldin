# Hosted consent and local Ollama routing

The privacy changes let users withdraw one provider's consent without
removing their keys, papers, or other approvals. The same pane can
reopen the disclosure for the currently selected unapproved provider.
Review or acceptance in Settings does not start generation. Active
jobs must be cancelled before withdrawal; existing job configuration
is not mutated. Withdrawal does not remove data already sent.

The local Ollama path refuses explicit cloud tags and markers reported
by the model inventory or model details before sending the paper
prompt. This is a check against the selected Ollama server's reported
metadata, not a guarantee about a modified or misreporting server.
Explicit remote CLI behavior and historical French V32 behavior were
not changed. French V36 emits the same typed cloud-route refusal as UK
generation. No hosted model was contacted in this review.

## Reviewed source and proof

The independent review and follow-up covered the integrated candidate
`66f18b2fa130e0c2443c490bce512f5086fc2e30` relative to print head
`969236ca60d0069f13e5aa13c212cbce54ced4e7`. Initial findings on
reapproval, French error presentation and cloud tag parsing were
reproduced, fixed and re-reviewed.

The coverage attestation for `tests/test_ollama_resource_admission.py`
composes the [prior headroom review](local-model-current-headroom-review.md)
and the complete 63-line added delta. It is not a new whole-file read.
Current source has 476 lines, SHA-256
`e5bf85e5691f8dea9c732e3f01eea3d9fcd842b969afd58a3ad071201766e809`.
The new cases exercise cloud names, reported route markers, an ordinary
bare model name and the real bridge command using local synthetic
fixtures. The bridge test checks a typed terminal error and no published
PDF; the transport-double test in the related thinking-policy suite
checks that declared cloud routing never receives the prompt.

The integrated native run passed 480 tests with six opt-in checks
skipped. The first integrated backend run passed 8,766 tests and failed
one review-ledger freshness check for the above source pin. That run is
not a passing full gate. The original development-signed Direct and
Store-mode builds are bound to `66f18b2f`; the Direct helper returned
the expected refusal for synthetic Accounting P2 and French V36
requests, without publishing a paper. This does not qualify any live
paper, production distribution or App Store privacy answers.
