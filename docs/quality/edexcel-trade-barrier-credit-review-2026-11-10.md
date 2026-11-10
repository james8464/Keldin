# Edexcel trade-barrier knowledge credit

## Actual defect and narrow repair

The current deterministic Paper 2 blueprint, seed 0, question 6(b), asks
candidates to examine two factors affecting a reduction in trade barriers.
Its source describes reduced tariffs, foreign competition and export access.
The eight-mark scheme nevertheless awarded one AO1 mark for defining currency
appreciation. A count-only check passed because the AO budgets still totalled
eight. This is a task-to-credit mismatch, not a model-response problem.

The existing five-mark route already selected trade-barrier and tariff
definitions for this owned prompt. The repair moves that existing, literal
selection into `_knowledge_pair(topic_id, *, prompt="")` and uses it in both
the below-eight branch and the seven-point eight-mark branch. The one-argument
lookup retains its original generic topic definitions. No new synonyms,
question identifiers, numeric answers or semantic inference were introduced.
The explicitly authored eight-point route is unchanged, as are higher bands.

Selection occurs while the deterministic blueprint is bound, before model
authoring. Later authoring retains the source and marking data rather than
rebinding credit from a paraphrased prompt. This is not a new general-purpose
classifier of arbitrary trade or currency questions.

## Evidence and compatibility

Before the production change, the new focused module produced two genuine
failures and nine passing controls in 0.19 seconds: the actual Paper 2 task
and a direct owned-scenario eight-mark control both exposed the wrong AO1
knowledge. After the repair, all eleven passed in 0.16 seconds. The final
focused run passed 143 tests in 9.21 seconds, with five inherited SWIG
deprecation warnings. It included the new module and the family assessment
contract, source-credit integrity and source-booklet binding modules, using
the checkout's root pytest configuration and verified module origins.

Pre-repair canonical JSON hashes remain exact for the existing five-mark
scheme, direct ten-, twelve-, fifteen- and twenty-five-mark scenario schemes,
an actual four-mark part, and an actual source-authored eight-mark route.
The direct five/eight controls also verify unchanged input objects and AO
budgets. The currency-appreciation negative control exercises the helper
route only; it is not claimed to be a currently seeded currency question.
The four-mark check uses an actual short part, not an unsupported four-mark
extended-response scenario. No production schema, source facts, questions,
prompts, tolerance, mark totals or reference data changed.

## Reviewed scope and limits

The earlier complete 704-line credit-module review at SHA-256
`6f4a5da2d86a981f1771801ea66aa3e65e6397a3bf1ed822d1ac3c2fca297176`
is supplemented by this complete 16-line production delta. The current
708-line module is
`0163063c78e0e5f012720f1faf62fe791ddb21dc23ab241b47898096796c74c8`.
The new 137-line regression module was read through EOF and is
`cd6a1a4bdf8f5dc6951a922289fbcce39272a0caa41fec63a96757179098f7f6`.
This actual witness supersedes the earlier bounded no-finding conclusion
for this route; historical audit evidence is retained rather than rewritten.

These are offline deterministic checks, not live-model qualification, a
complete paper-quality assessment or proof of official-board equivalence.
No full suite, release build, installed-app action or new model call was run
for this repair. Related existing tests may render owned temporary PDFs;
there is no new manual PDF or visual acceptance claim here. Integration,
audit-metadata refresh and fresh release gates remain separate work.

## Public-preview follow-up

The root reviewer then generated baseline and repaired offline previews through
the actual public bridge, using Economics Paper 2, seed 0. Each set contains
36 question-paper pages, four source-booklet pages and 26 mark-scheme pages.
All pages are A4 and contain text. At 100 dpi, 65 of the 66 page rasters are
identical; only mark-scheme page 16 changes. Text scoped from question 6(b) to
6(c) confirms that the unrelated currency definition is replaced by the
trade-barrier and tariff definitions in the actual printed task.

The complete old and new page 16 images were visually inspected at 100 dpi.
No new clipping, overlap or table-alignment problem was observed. The remaining
pages were compared automatically, not freshly inspected for all content.
This is a bounded change review of offline previews, not live-model, official
paper, physical-print or final frozen-CLI qualification. The original failed
scheme and all comparison artifacts remain retained.
