# Document selector and Print review

The old build could open Print for the previous PDF if Cmd-P arrived while
the document menu was still tracking the selection. A signed sandbox copy
reproduced this in both directions with a 36-page Accounting question
paper and its 12-page mark scheme.

Replacing the menu with a synchronous native picker did not fix the race
on its own. A diagnostic build recorded Print starting and presenting the
old paper during menu tracking. Only after Print was cancelled did AppKit
end tracking and send the new selection action.

The picker now reports tracking for its own native menu. The document
controller disables actions until tracking ends, and ignores any pending
presentation that was started before the menu opened. The selection
binding still clears the previous PDF and verifies the new one before
re-enabling PDF actions. Shortcuts pressed during tracking are ignored,
not queued. The diagnostic logging is absent from the production change.

The full macOS test suite completed with 485 passes, six skips and no
failures. New tests cover the menu's tracking notifications, duplicate
visible titles, commands during tracking, both file switches, dismissal
without a change, and a pending Print read interrupted by the picker.

A personal-development-signed sandbox clone with unchanged sandbox
entitlements passed the original rapid-switch reproduction in both
directions: no old Print dialog appeared, then a fresh Cmd-P showed all
12 or 36 pages for the newly selected PDF. Escape preserved selection
and Print worked afterward. The test cancelled all dialogs without
printing and used offline, unreviewed layout previews in a separate
test container. Quick Look, Export and Reveal were covered by the
controller tests, not this interactive run.

The picker and its tests were read in full. This review of the command
and preview changes builds on the prior full-file review in
[PDF loading isolation](pdf-loading-isolation-review.md). It does not
qualify whole-app behaviour, live model output, or public distribution.
