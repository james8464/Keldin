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
artifact receipts. It is not a full repository review. Next, validate the
extension path with a small configured family and advance the published
live-paper evidence separately from the software checks.

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
