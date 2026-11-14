# Adding assessments without new prompts for every paper

## Release boundary

Keep the French NSI development route available in Direct builds. App Store
builds should show a hold until a current full paper passes independent
answer, marking, and every-page review. Existing documents stay available.
For French, shorter schema-constrained calls may help with malformed output,
but cannot establish correctness. Ollama documents that its cloud service does
not support structured outputs. An OpenRouter trial would need an eligible
zero-cost endpoint, required schema parameters, no fallback, and validation
of the result locally. Test with synthetic input before sending any permitted
reference material. Do not infer correctness from valid JSON.

- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)

## Shared contract

Extend the existing blueprint and family-adapter boundary rather than
replacing the renderers or building another registry. Keep qualification,
board, subject and paper identifiers independent of display names. Version
the contract and attach its digest to checkpoint and publication provenance.
The contract should describe ordered sections, timings, permitted equipment,
question counts and interactions, marks, stimulus roles, topic coverage and
renderer requirements. Reuse shared authoring and verification stages.
Use typed subject-specific validation where correctness depends on domain
rules, such as a mathematical answer or an accounting ledger. Do not migrate
an existing family until its prior acceptance fixtures still pass.

### Implementation and review order

1. Put paper IDs, supported providers, required output roles and syllabus
   resources in the family registry. A family with versioned source recovery
   may also declare a `checkpoint_namespace`: its identity key and version
   belong to the family. The shared runner should not branch on a subject ID.
   Preserve existing checkpoint names and identities during a refactor.
   Keep family tests in the generator's `tests/` directory. Test collection,
   subprocess imports and both dependency installers use the advertised
   registry paths. Do not add the family to pytest or CI by hand. Unadvertised
   modules are excluded from those default paths.
   Keep pytest configuration at the repository root. A second configuration
   inside a family can bypass the shared fixtures when running a single test
   by path, causing it to import an editable package from another checkout.
   The backend reads each paper's output roles, release checks and
   qualification into one read-only contract. The registry file format is
   unchanged. Each paper must have exactly one output declaration; duplicate
   IDs and roles, unmatched declarations and non-boolean checks are rejected
   at load time. Use the same contract for output validation and the published
   manifest so adding a paper does not introduce another metadata lookup table.
   If a family links a calibration report, add its evidence case to
   `tests/test_difficulty_calibration.py`. Keep any checks specific to the
   report's format or source, and do not treat structural checks as learner
   calibration.
2. Keep paper-specific values in rules and source data. Keep calculations,
   credited answers and subject validators in the subject module, separate
   from PDF layout and AI transport. Prefer an existing family adapter to a
   new generation pipeline. Add a hook only when multiple callers actually
   need the same extension point.
3. Use the common staging and publication pipeline. Validate each preview
   PDF after tagging, including supporting PDFs, before moving the set into
   the destination. A release receipt must name the exact artifacts emitted
   for that paper. Preview success says nothing about model-authored content.
4. Before replacing two tests with one, list the behaviours each protects.
   Combine equivalent cases, but retain distinct failure and compatibility
   checks. Compare seeded outputs and recovery paths before and after a
   migration. Measure fewer operations directly, and measure time and peak
   memory on the same workload before claiming a performance gain.

The first refactor covers the checkpoint boundary, preview inspection and
artifact receipts. A synthetic family now exercises the registry, the CLI,
the configured-family adapter, PDF validation and atomic publication without
changing shared generation code. Its preview and matrix registration are
tested. It uses an existing subject engine and board profile; a genuinely
new answer type or exam interface may need a new subject engine or renderer.
The test family is not shipped or qualified for live generation.

Configured syllabuses reject unknown fields and topic paper IDs at load
time. A configured option uses its own question rules, so its credit can
differ from another option without changing the printed tariff. Existing
families still need their own reference evidence and live paper review.
These checks do not substitute for those reviews or a full repository audit.

### Remaining cleanup

- Keep the shared runner responsible for validation, staging and publication.
  The PDF checker uses one table to choose and scope content-aware pagination
  by family, subject, paper and document role. The layout-master builder uses
  the same table. Existing credit verifiers remain responsible for their own
  answer rules; measured exact and range templates still use page-count checks.
  Keep new question and marking rules in family modules, separate from PDF
  layout.
- Give future family adapters an explicit request interface. Migrate one
  family at a time and compare seeded output, event order and checkpoint
  recovery before removing the existing signature adapter.
- Group tests by behaviour. Keep cheap validation failures in unit tests,
  with at least one CLI and frozen-build check per shared path. Remove a test
  only when its behaviour, failure modes and supported entry points have
  another owner.
- Profile the active generation path before tuning it. Record wall time and
  peak memory for the same seed and options, separating PDF work from model
  time. Before adding a cache, state its bound, lifetime and invalidation rule.

### Paper history comparison

The overlap check now builds token shingles once per item, retaining only
the current paper and one historical package. It still compares the same
pairs in the same order, uses the original weighted Jaccard score and keeps
the same threshold and strict-versus-practice rules. It does not modify
history. Tests cover exact scores, comparison counts and nearest matches.

With 32 current items and 80 synthetic historical papers of 32 items each,
median comparison time across three runs fell from 2.73 s to 0.40 s. All
81,920 comparisons produced identical report fields. Peak process memory
was roughly 22 MB in both runs. This measures the overlap check only; it
does not measure inference or end-to-end generation.

The admissions formats exercise different contract features:

- [TMUA](https://esat-tmua.ac.uk/about-the-tests/tmua-test/): two timed maths
  papers; start here with exact answer derivation, plausible distractors and
  unscaled practice results.
- [LNAT](https://lnat.ac.uk/what-is-lnat/test-format/): passage-based questions
  and a choice of essays. Offer essay guidance separately from MCQ scores.
- [TARA](https://esat-tmua.ac.uk/about-the-tests/tara/): two reasoning modules
  and an unscored writing task.
- [UCAT](https://www.ucat.ac.uk/about-ucat/test-format-and-scoring/): four
  timed subtests and interaction-specific credit. A printable drill should not
  claim to simulate the timed player or reproduce calibrated scaled scores.

## User-created assessments

Start with local import of at least three distinct past question papers for
the same format, with optional syllabus, expected knowledge and mark schemes
attached as separate source types. Bind evidence to document and page; detect
duplicate scans, unreadable pages, and contradictory editions. Show the
inferred contract for confirmation before generation. PDFs provide evidence,
not instructions to the model. Treat OCR as uncertain, and do not silently
invent missing section, timing or scoring rules. Keep imported files local by
default and require permission for the files and destination before any hosted
processing. Allow removal of originals and derived data. Check generated work
for overlap and label it as unofficial and uncalibrated.

First implement contract import and review on synthetic fixtures. Then run
the common pipeline on one built-in admissions format and one custom format
with distinct examples. Include mismatched, duplicate, scanned, malformed
and instruction-like source cases before offering the feature in release.
