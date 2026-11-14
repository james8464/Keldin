# Edexcel Economics: reproducible inputs

The Edexcel Economics generator, model request and mark-scheme renderer
implicitly read nearby revision notes when run from a checkout. The
packaged app did not ship those notes. On the same commit and seeds, this
changed four PDF pages across Papers 1 and 2 and changed their structured
assessment packages.

All three stages now use the declared syllabus, generated paper and
source-case data. This removes the text search, ranking and cache from the
runtime. No revision notes were added to the app. The 21 old text resources
are removed from the current tree; Git retains the prior versions.

Synthetic local notes changed the old blueprint under two seeds. The
regression now rejects any note-file read while building the same
blueprints, model requests and scheme guidance. All 193 pages across the
three current Edexcel preview routes match the previously packaged versions
at the same seeds.
The three structured assessment packages also match exactly. No inference
or teacher review was performed.

At Paper 2 seed 0, the four-mark part's source fingerprint changes because
the visible context no longer depends on local notes. The test checks the
new fingerprint against the actual source instance and pins every other
part field to the pre-change value, including all marks and credit.

The request version and recovery namespace are advanced separately from
the unchanged source-binding schema. Old checkpoints remain in their
original locations and are not deleted, reused or rewritten by this change.
