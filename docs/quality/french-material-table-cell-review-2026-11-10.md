# French material table cell integrity

## Confirmed fault

The complete-stream PDF comparison removed whitespace between table cells.
The valid source row `1 | 23` and a separately rendered row `12 | 3` therefore
became the same string. The actual current V36 validator accepted both seven-page
synthetic question papers against the original source. Each retained six graphs
and one fenced Python block; no graph, code, identity or PDF gate was patched.
A non-colliding changed-value control correctly refused. Original/altered PDFs,
structured source snapshots and hashes remain in
`tmp/pdfs/nov10-french-table-boundary-v36/`.

The new real-render regression failed in all four subject/correction and
normal/enlarged cases before the repair: **4 failed in 1.38 s**. A first launch of
the earlier diagnostic stopped before rendering on a dirty-checkout guard; that
was not a validator result. Subsequent diagnostic source/test pins were checked
independently of disjoint CS and teacher-review edits.

## Bounded repair

`table_pdf.py` checks actual ruled material grids only between an exercise heading
and its first question. It does not parse correction rubrics as source tables.
Ordered source title/header/row cells bind the fragments. Row/column coordinates
must be monotonic and match the bounded schema dimensions; missing, partial,
collapsed, ambiguous or extra grids refuse. Actual glyph centres and complete
bounding boxes must stay within their assigned cells. Within-cell whitespace
normalization is inherited for wrapping, never applied across cell boundaries.

Collinear rule segments join within the 0.5-point geometry tolerance because
ReportLab splits rules at repeated headers; spans separated beyond that tolerance
remain unjoined. Continuations require the
same columns on the next page and an exact source header. Only those validated
header lines are removed from the complete-stream comparison. All other text,
page furniture, code and graph checks remain. The helper returns scoped fragment
provenance; it is not a whole-PDF glyph-forensics or visibility certification.
No renderer, print policy, prompt, answer, credit, package identity or model
configuration changed. V36 v1–v5 compatibility controls pass.

## Verification and limits

Final focused group: **84 passed in 8.11 s**, log
`tmp/nov10-french-table-final-focused.log`, SHA-256
`a45ba5e854317b9854fe3ab6df71576778878c6d9a9137d8a850f76eb58cba18`.
It includes 32 new cases and 52 related cases, not additive overlapping runs.
The new cases contain four actual wrong-PDF regressions, twelve valid-render
shape/print-mode controls, five retained-policy controls, extra-row refusal and
a misleading-label control. Nine additional cases mutate an in-memory view of
real PDF drawing/glyph data: they are helper tests, not nine physically modified
PDF proofs. Intermediate continuation failures and fixture-precondition errors
are separate from the genuine four-case RED and final acceptance.

Ruff check/format, diff checks, and scoped non-strict mypy on the two production
modules pass. No full suite, build, native interaction or inference was run.
The owned witness's two relevant full pages were visually inspected; there is no
new every-page visual or model-quality qualification claim.

Frozen SHA-256:

- Helper (300 lines): `88b99c34d28709fc240ce5093997690be9f0f208508300ea47f5cc04d725803d`
- Validator (325 lines): `57a22ca2d89f00ea1a68dc1cc13edadfaf5fa4df35c03c87b6a02a3ef9f4c964`
- New tests (270 lines): `0dd6646f454f1ab0cff56e3ddc353167f58be53f6e6f96dc398a2a5529ceae32`

The preceding complete EOF audit covered unchanged `pipeline.py` (4,379 lines,
`cf0ea7a4…`) and `whole_case_pdf.py` (273 lines, `23ad9dc9…`). Other imported
catalogues/contracts remain separate audit work. The full audit and reproduction
receipt is `tmp/nov10-french-shared-helper-eof-review.json` in the ROOT worktree;
no tracked ledger status is promoted by this repair note.
