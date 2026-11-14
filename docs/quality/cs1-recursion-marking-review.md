# AQA Computer Science Paper 1: exact recursive-call credit

The packaged offline preview asks for the first two calls made by a recursive
function, but the printed scheme only says that the argument decreases twice.
The structured key already holds both exact arguments. Both forms now use the
same derived values, and the printed scheme gives the exact calls in order.
The candidate prompt, function, two marks and structured key are unchanged.

The defect reproduced on three seeds before the repair. The changed tests check
the prompt, structured key, point count and actual scheme PDF. The related
44 tests also cover candidate pages, electronic response continuation and
reference programs.

For seed 26080108, the old packaged preview contained 10 question pages,
40 response pages with 39 fields, two preliminary pages and 17 scheme pages.
All 69 were viewed in contact sheets. The local AQA 7517/1 June 2025 question
paper and scheme were viewed as comparators. The official sample includes
material repeated for navigation, deliberate blank pages, multiple supported
languages, and longer interdependent tasks. Keldin's shorter PDF and its much
sparser per-part response pages are not evidence of comparable difficulty,
timing or exact format. No blank page or copied official material was added.

The corrected source preview matches 68 of the 69 packaged-baseline pages
in order, raster, geometry and text at 100.8 dpi, with byte-identical program
and practice data. Only mark-scheme page 8 changed; it was inspected
separately. The two point lines show `value(4)` and `value(3)` for the
preview's `n = 5`. No hosted or local model was called. This is a scoped
layout and answer-key repair, not fresh live quality or full print acceptance.
