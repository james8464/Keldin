# Internal file-review reconciliation

Baseline: protected PR #197, commit `ab2d8f0246086d22cd5319f54f2a789ea884d914`.
This record reconciles completed reviews with the file inventory. The same
change set also contains the separately tested trade-barrier credit repair linked
below. That repair changes host-owned marking guidance, not model prompts,
source facts, validation thresholds or mark totals. A reviewed file is not a
certificate of zero bugs.

## Current active-path reviews

The following entries cover complete file reads, complete structured-data
reviews or an explicitly described full-baseline-plus-delta composite. Callers
and tests were read only within the stated boundaries. Read-only inspection
does not replace the separate execution and release gates for the repair.

| File | Scope and disposition |
| --- | --- |
| `.github/ISSUE_TEMPLATE/config.yml` | All five lines, including the renamed repository's responsible-disclosure URL. This checks configuration, not whether GitHub has enabled every destination feature. |
| `macOS/Keldin/Application/AppConfiguration.swift` | All 141 lines. Defaults, storage names, home-path abbreviation, output-folder choices and application links were inspected with bounded startup and bookmark callers. No concrete defect was established. Permission, disk and every-user behaviour are not certified. |
| `Backend/Core/france/llm_pdf.py` | Fresh complete 325-line review of expected prose, figure scoping, code indentation, material-table integration and ordered whole-document comparison. Earlier scoped reads were not treated as complete baseline evidence. This does not qualify model answers or every possible generated PDF. |
| `Resources/catalog.json` | All 102 lines. Native family and paper identities were compared with the complete registry records and actual loading paths. |
| `Resources/generator-registry.json` | Semantic review of all ten families and 32 paper records, every observed key set, and every distinct qualification/check record. This is not a claim of a separate literal 1,349-line read. Seven advertised families expose 21 routes: 18 full papers and three topic banks. Identifiers, provider mapping, output roles, entry functions and all seven declared syllabuses align with the inspected native/backend callers. |
| `Resources/ollama-model-recommendations.json` | All 40 lines. Memory tiers are contiguous and explicitly unqualified for the full paper matrix. The warning distinguishes memory fit from accuracy. This was not a new model-availability or inference test. |
| `Resources/computer-science/aqa/generator/cspapergen/cli.py` | All 205 lines. Rule selection, family-adapter hooks, artifact order, Paper 1 supporting files, progress forwarding and command arguments were inspected. Runtime bootstrap, syllabus defaults and notes caching were read within the relevant boundaries. No new defect was established for the current caller contracts. |
| `Resources/computer-science/aqa/generator/cspapergen/topic_bank.py` | All 573 lines. The three advertised bank routes, topic membership, instance data, answer ownership and mark construction were inspected. Models, objective calibration and syllabus modules were also read; generator, validation, SQL construction and existing tests were scoped rather than universally reread. No concrete valid-input defect was established. |
| `Resources/economics/edexcel-a/generator/pastpapergen/credit_contracts.py` | Complete 704-line baseline plus the complete 16-line repair delta, covering the current 708 lines. The earlier bounded review missed an actual eight-mark trade-barrier knowledge mismatch. The later witness and repair supersede that no-finding conclusion. Other tariffs and source-owned routes have explicit compatibility controls; no universal economic or model-answer proof is claimed. |
| `Resources/economics/edexcel-a/generator/pastpapergen/source_cases.py` | All 299 lines, through consecutive scoped reads. Case selection, wraparound, fallback construction and the complete retained text tables were examined. The latent source-vintage issue below remains recorded. Real-company statements were not all independently fact-checked. |
| `Resources/economics/edexcel-a/generator/pastpapergen/generator.py` | All 3,376 lines. Seed, section, source and canonical binding paths were inspected. Three tiny in-memory built-in-paper probes had valid 100-mark candidate paths. Those structural checks did not independently validate downstream credit semantics, where the separate trade-barrier defect was found. No complete paper-quality claim follows. |
| `Resources/economics/edexcel-a/generator/pastpapergen/extended_scenarios.py` | All 591 lines. Scenario concepts, public facts, detail selection and fallback binding were inspected. This review established the actual seed-0 eight-mark mismatch in the downstream credit selector. The scenario facts themselves remain unchanged. |
| `tests/test_edexcel_trade_barrier_credit.py` | All 137 lines. The actual Paper 2 seed-0 witness, source/input preservation, existing tariff snapshots, authored routes and helper-only negative control were read. The latter is not represented as a currently seeded currency question. |

The installed PR #197 bundle was inspected read-only for the catalogue comparison.
Its native catalogue, native/backend registry copies and all seven exact backend
syllabus paths matched current source bytes. This checks resource identity, not
generation quality or an additional complete bundle/signing qualification.

`Backend/Core/generator_registry.py` and `Backend/Core/model_recommendations.py`
were also read through all 267 and 120 lines respectively. Their existing review
entries are preserved, not counted as new attestations. The same applies to
previously recorded dependent-file reviews.

## Retained intermediate-source finding

Two retained Economics helper strings mention the World Bank's $2.15 poverty
line without an explicit historical observation date. The World Bank replaced
that 2017-PPP threshold in June 2025; see its
[dated primary explanation](https://www.worldbank.org/en/news/factsheet/2025/06/05/june-2025-update-to-global-poverty-lines).

A two-string proposal explicitly dated the scenario to 2024 while retaining
$2.15 and the 2017 price basis. Four focused intermediate-helper checks failed
before that proposal; those checks and the existing question-style module then
passed 65 tests. They did not demonstrate a defect in a final public paper.
Downstream binding replaces these intermediate sources with concrete scenarios.
In a bounded search of seeds 0-31 no final Paper 2 blueprint contained $2.15;
the actual seed 4 development question used an FDI factory/training scenario.
This is evidence of that route, not proof about every possible invocation.

The proposal and tests were retained as ignored audit artifacts, and the source
was restored byte-for-byte before this reconciliation. No user-facing fix,
public-paper qualification or runtime change is claimed for this finding.

## Earlier exact-current reviews reconciled here

These eight rows reconcile earlier reviews; they are not eight new reviews. The original
baselines, complete deltas, negative tests, inspection limits and failed attempts
remain in the linked records and retained audit receipts.

| File | Exact-current review scope |
| --- | --- |
| `Backend/Core/france/pipeline.py` | Complete 4,379-line review of the shared/versioned pipeline. This does not substitute for a full current model-authored paper test. |
| `Backend/Core/france/whole_case_pdf.py` | Complete 273-line review of the whole-case PDF validator and its printed-content comparison gates. |
| `Backend/Core/france/teacher_review.py` | Earlier complete 152-line review plus the full idempotency/symlink delta, covering the current 164 lines. Composite review, not a fresh 164-line read. |
| `Backend/Core/france/table_pdf.py` | Complete 300-line review, including ruled cells, glyph bounds, repeated headers and narrowly scoped material regions. |
| `Resources/computer-science/aqa/generator/cspapergen/render_pdf.py` | Earlier complete 2,266-line review plus the complete source-flow/resource and declared-marking deltas. Composite coverage of the current 1,995 lines, not a fresh whole-file read. |
| `tests/test_french_review.py` | Earlier complete 135-line test review plus all 152 appended lines. Composite coverage of the current 287 lines. |
| `tests/test_french_table_cell_integrity.py` | Complete 270-line review. Physical-PDF negative cases are distinguished from in-memory drawing/glyph mutations. |
| `tests/test_cs_declared_marking_policy.py` | Complete 105-line review. Explicit source-owned levels and point-only schemes have separate preservation controls. |

Supporting tracked records:

- [French material-table review](french-material-table-cell-review-2026-11-10.md)
- [Review-save idempotency](french-review-idempotency-2026-11-10.md)
- [Declared CS marking policy](cs-declared-marking-policy-review-2026-11-10.md)
- [CS source-flow review](cs1-on-screen-source-flow-review-2026-11-07.md)
- [Repository-link follow-up](repository-rename-follow-up-2026-11-10.md)
- [Trade-barrier credit repair](edexcel-trade-barrier-credit-review-2026-11-10.md)

## Source pins

Each ledger attestation binds the relevant source bytes to this record's own
hash. These pins are checked again before publishing the reconciliation.

| File | SHA-256 |
| --- | --- |
| `.github/ISSUE_TEMPLATE/config.yml` | `30255f1accb0a3fcad92a086914858e5f1959bc2ff0c397642258cdee713bc4a` |
| `macOS/Keldin/Application/AppConfiguration.swift` | `75e53a74d0870ac0e69cfaf20bad0706a421c3e832135845437c06bfeee31859` |
| `Resources/catalog.json` | `0c30943ff971a0b05567bb8e9318a8d298939781e6fcd1753b7b257b37f1b756` |
| `Resources/generator-registry.json` | `b86b7171a4ee25658ffa9c70d8920221f27ddd8694b542bb81143f64567b1355` |
| `Resources/ollama-model-recommendations.json` | `4ebce807196c10c2b73396b7f849d2bbb32dcd6738e8cc2b3746952425344b3e` |
| `Resources/computer-science/aqa/generator/cspapergen/cli.py` | `08edd4d5b1c06f11354e3787a3a1b17e8e2b718053496ed37d75b5f6f6b44799` |
| `Resources/computer-science/aqa/generator/cspapergen/topic_bank.py` | `ca34e41de156cd76cec6da1185d6245e3692ff47ff4c9e61d7282e70b2a225ba` |
| `Resources/economics/edexcel-a/generator/pastpapergen/credit_contracts.py` | `0163063c78e0e5f012720f1faf62fe791ddb21dc23ab241b47898096796c74c8` |
| `Resources/economics/edexcel-a/generator/pastpapergen/source_cases.py` | `34b70b8a0c0fde7e04e6118d9c45b76cae63405e9e11f2c7b99737712eca9a2f` |
| `Resources/economics/edexcel-a/generator/pastpapergen/generator.py` | `430fc254810f02694dd3946c53e1484fb01c60cf17c28f51f282d31806b868e2` |
| `Resources/economics/edexcel-a/generator/pastpapergen/extended_scenarios.py` | `010800bfb766073079eb44982e5dcab0a58683a4f32b0c9c250ab934162c1850` |
| `tests/test_edexcel_trade_barrier_credit.py` | `cd6a1a4bdf8f5dc6951a922289fbcce39272a0caa41fec63a96757179098f7f6` |
| `Backend/Core/france/pipeline.py` | `cf0ea7a4dd6f99e35d6dc938e6fd6052752e1c5d43343d957e147aacffa29a45` |
| `Backend/Core/france/whole_case_pdf.py` | `23ad9dc9e98997428092e281537f2c4d5b5d3d414d657c9ea5780f137e835e3e` |
| `Backend/Core/france/teacher_review.py` | `ea2b6caa72e9c0bcad1062ac3e910dff6c59a0d98f7f0ef9a25f19e841090734` |
| `Backend/Core/france/llm_pdf.py` | `57a22ca2d89f00ea1a68dc1cc13edadfaf5fa4df35c03c87b6a02a3ef9f4c964` |
| `Backend/Core/france/table_pdf.py` | `88b99c34d28709fc240ce5093997690be9f0f208508300ea47f5cc04d725803d` |
| `Resources/computer-science/aqa/generator/cspapergen/render_pdf.py` | `33156cc03706b553adb41406fc7751835fbed8945a6bcebd228499d1bc07fc52` |
| `tests/test_french_review.py` | `633e17bf3894626032b413bdd7393542f2f3b369b6f227be82a450da160b6c7a` |
| `tests/test_french_table_cell_integrity.py` | `0dd6646f454f1ab0cff56e3ddc353167f58be53f6e6f96dc398a2a5529ceae32` |
| `tests/test_cs_declared_marking_policy.py` | `4ea873be3a3f6b60b341adeb38bba73dc74f0b675f727d5f3d23f0a34e3665aa` |

## Remaining acceptance work

This record does not complete the repository-wide audit or the supported
live-paper/provider matrix. The current French full-paper route is still
unqualified. A fresh production admission probe refused the cold Qwen3.5 9B run:
4,702,879,744 bytes of estimated headroom versus 8,741,958,359 required, despite
normal categorical memory pressure. Only metadata GET requests ran; no model
was loaded, no inference ran and no payment was made. Warming a model first to
avoid the cold-load check is not an accepted workaround.

PR #197's passing full tests, signed builds, packaged checks and scoped installed
interaction checks remain separate evidence. Teacher and accessibility tests
were waived, not passed; learner timing remains unmeasured. Per-document rights,
production signing/notarization and Store approval are also not established by
these file reviews. No official equivalence, universal model accuracy or
complete HIG compliance is claimed.
