# Computer Science Paper 1: make the report requirements explicit

## Finding and repair

The current Paper 1 seed 270100 asks candidates to complete `print_report`.
Question 12.1 awards a point for traversing the records exactly once, but the
question did not state this constraint. The point for leaving the records
unchanged and the requirements to show totals and include empty categories
were also not explicit in the task.

The question now states these existing requirements. It retains the adjusted
totals, alphabetical tie break and best-record identifier. The mark points,
tariffs, reference Python, skeleton and data are unchanged. The existing
operation classifier now correctly records the implementation task as
`program` rather than `analyse`; its rules and estimated time are unchanged.

## Evidence and scope

Four scenario controls reproduced the missing single-pass instruction before
the change. The same controls pass afterwards. The related blueprint,
reference solution, marking policy, on-screen flow and publication-policy
group passed 128 tests. An independent baseline comparison of 33 seeds
(0–31 and 270100) found only the 12.1 prompt and derived operation change;
the rest of each blueprint and the supplied program context matched.

Two actual offline source previews of Paper 1, seed 270100, produced valid
packages with the same seven output roles and verified manifest hashes.
Of 69 pages, 65 full-page 100-dpi rasters and extracted texts match. The
question paper remains ten pages; Q12 now starts together on page 10 instead
of starting at the bottom of page 9. The only other changed pages are the
electronic answer document page 38 and the reference solution page 17.
All four changed pages were inspected in full. The complete question and
code are visible, and the answer field remains below the prompt. The same
39 widget names, types, flags and values are present. Only `question_12_1`
moves down 39 points to fit the longer instruction; its lower edge and all
other field rectangles are unchanged. Program and data files match byte
for byte. No model was called and no learner timing or official equivalence
is inferred. The first all-widget-geometry comparison failed on the intended
movement; it is not counted as an unchanged geometry result.

The [prior complete generator review](renderer-eof-audit-and-release-follow-ups.md)
applies to the exact baseline source SHA-256
`ff87cf798a8fe066fe085c47ff15d690acdca166401d51138f66935e29e2c391`.
The complete reviewed production delta replaces one task string with four
adjacent literals. The current 1,781-line source SHA-256 is
`2472085411552446e00fc685a26e502ac3f8f4b8f8df36ff06952e3c4a97bc8d`.
This is complete baseline plus delta evidence, not a fresh whole-file review.
The expanded test is scoped to the affected assertions, not an attestation
for the rest of the test module. Protected, packaged and native release
checks remain separate.
