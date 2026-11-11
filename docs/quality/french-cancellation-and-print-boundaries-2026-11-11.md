# French cancellation and printed-code source review

This review covers the complete files listed below and the adjacent callers
needed to check their boundaries. It does not qualify generated papers.

| File | SHA-256 |
| --- | --- |
| `Backend/Core/france/llm_runtime.py` | `760cb451e6f6e43f23122f0943e6452fef8edd59bf4569b333b78d9a4867854a` |
| `Backend/Core/france/code_fences.py` | `6181ca1f761ed3efa1b999dcf7179755a15731f4008e0eb702304df9d46dd405` |
| `Backend/Core/france/code_layout.py` | `8147195558b3f58b3a611b547cea46b010b8dfab14c2c3c48e6d7489930b2ddb` |

The runtime checks provider, seed and reference inputs before snapshotting the
references, implementation and model. It starts cancellation handling before
these reads, restores the previous handler on exit, and never reports a
successful publication when cancelled. A signal after the final rename can
leave a complete bundle, which is reported separately from a cancellation
before publication. The runtime validates package identity, rechecks source
identity before publication, and removes only its own staging directory.
Snapshots do not lock files against external changes, and hosted model
revisions are not available to pin.

Fence parsing walks physical LF and CRLF lines and slices from the original
text. Strict callers refuse missing closing lines. Unsupported languages do
not become Python or SQL listings. Layout uses the selected font to measure
each physical line and rejects known unprintable separators without rewriting
code. The V36 authoring gate rejects tabs and applies the appropriate question
or content width, and the renderer checks width again before layout.

The regression reproduced missing cancellation handling during model
snapshotting. A child process receiving a real SIGTERM now exits with status
130, emits one cancellation event and creates no output directory. All 2,891
French and NSI regression tests passed on source commit `081ad8209f7a`.
These are automated checks, not live model or visual paper qualification.
