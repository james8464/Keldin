# Print-safe answer-frame warnings

The Accounting and Business notice used to end about 0.6 mm from the right
edge of an A4 sheet. The printed Computer Science warning and the rotated
Edexcel Economics labels also crossed the 5 mm print inset. Those labels
tell candidates where not to write. They should not depend on borderless
printing.

Accounting and Business now wrap their notice in the same shared gutter.
Printed Computer Science centres the existing warning between the answer
frame and the safe right edge; the on-screen branch is unchanged. Edexcel
Economics moves the left hatch and keeps the existing right hatch in place.
The full-size labels fit within each hatch and clear the writing frame.
No answer frame, question text, mark allocation or pagination is changed.

The PDF geometry tests reproduced all five unsafe cases before the changes.
The previous right-rail test now checks the original hatch dimensions, label
size, number of labels and print-safe placement rather than the unsafe label
anchor. Five Accounting/Business and seven Computer Science/Economics
previews were regenerated at the protected baseline's exact seeds. Their
554 pages retained the same page boxes and word sequence, with all raster
differences confined to the affected question-paper gutters. In the combined
21-route, 49-PDF set, the extracted word boxes on all 1,032 pages meet the
5 mm inset. A fresh run of the combined source reproduced every one of those
page rasters at the same seeds. Representative pages were also inspected visually.
This scan concerns text on deterministic previews, not decorative crop marks,
every printer's physical margins, a model qualification or board approval.

## Source review scope

- `Backend/Core/exam_pages.py`: read the current file through EOF, including
  shared page variants, canvas state, footers, barcodes and the new warning.
- AQA Computer Science renderer: the [prior composite review](implementation-audit-reconciliation-2026-11-10.md)
  matches the unchanged base file. This review covers the complete new import
  and header delta, both delivery branches, and the printed preview matrix.
  It is not a fresh whole-file review of the renderer.
- Accounting, Business and Edexcel Economics: scoped review of the current
  gutter callers and their rendering tests, not a new whole-file attestation.
