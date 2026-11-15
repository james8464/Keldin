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
