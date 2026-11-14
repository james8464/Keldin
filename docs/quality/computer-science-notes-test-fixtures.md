# Computer Science note cache test fixtures

The family suite previously skipped both note tests if a local folder of
third-party PDFs was absent. That made the tests depend on the contents of
the developer's machine and left clean-checkout CI without those cases.

The two tests now create original PDFs under temporary paths. They check
stable discovery order, ignoring non-PDF files and nested directories,
missing sources, exact raw copies, actual extracted text, and cache counts.
The existing lower-level fallback, stale-cache, and cancellation cases
remain. The fixtures neither require nor qualify a third-party notes corpus.
No generation, cache implementation, permissions, dependencies, or
application code changed.
