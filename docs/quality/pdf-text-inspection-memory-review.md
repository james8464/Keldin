# PDF text inspection without image copies

The default PyMuPDF dictionary extraction includes image data. Three Keldin
text-only consumers discarded it immediately: the standalone font scan, the
print-evidence font scan, and release validation. They now clear only the
image flag. The [PyMuPDF extraction flags](https://pymupdf.readthedocs.io/en/latest/vars.html#text-extraction-flags)
document that this is separate from the flags governing text extraction.

Release validation still checks image placement and resolution via
`get_image_info()` and still verifies that the rendered page contains
visible marks. The raw glyph and content geometry audit is unchanged: it
intentionally includes image boxes. No quality threshold, page size,
validation outcome or output schema was relaxed.

A regression creates a PDF containing text and an inline image. It failed
before the change when the first dictionary materialized an image block.
It now verifies that all three text scans omit image blocks, while fonts,
image coordinates and image resolution are still reported.

In three alternating runs on a synthetic five-page PDF containing
high-resolution images, the median measured time for font scanning plus
release validation was 1.925 s before and 0.201 s after. Median process
peak memory was 188,940,288 B before and 65,323,008 B after. The complete
JSON results matched in all six runs. These measurements apply only to
the synthetic inspection workload, not live paper-generation speed.
