# PDF action cancellation review

Opening the document picker invalidates a pending PDF action. A failing
read could still present an alert after that invalidation, although the
same action would no longer print or export on success.

The failure path now checks the same picker revision as the success
path before showing an action alert. The selected document still reports
its access problem inline. An explicit access recovery error is not
silenced by this change.

A gated native test reproduces the late permission failure. It failed
before the fix because an alert was populated, then passed with the
inline permission status intact. The full macOS suite recorded 486
passes, six skips and no failures. Existing scope and lease checks
remain unchanged.

This is a scoped review of the cancellation delta against the
[document picker review](document-picker-print-review-2026-11-15.md)
and [PDF loading baseline](pdf-loading-isolation-review.md). It does
not resolve the separate intermittent Quick Look panel refusal, or
qualify live paper output or public distribution.

## Quick Look while Keldin is inactive

A signed sandbox app with a readable preview reproduced a generic Quick Look
error when invoked in the background. Keldin made the PDF view its first
responder, but the app never became active and macOS did not assign a panel
controller. An isolated single activation request did not change that result.

Quick Look now checks activity before revalidating the PDF and again before
staging a preview. A background request does not force activation, change
panel ownership, or queue a preview to open later. The already loaded PDF
remains available in Documents, with English and French guidance to bring
Keldin forward and try again. If focus is absent after validation, only the
new preview lease is released. The existing active and pending leases and the
selected-document and picker checks are unchanged.

The new request-time test failed before the guard: the command reread the
PDF and reached the presenter after focus returned. The exact revised macOS
suite ran 494 tests with six opt-in skips and no failures. It also checks
the lease and French message. An independent read-only review cleared both
focus checks. This is a scoped source delta against the earlier review.
It does not resolve the distinct intermittent foreground refusal, change
how macOS handles a shortcut still directed to Export, or qualify live
generation or public distribution.
