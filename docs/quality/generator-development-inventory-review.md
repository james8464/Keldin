# Generator setup: one source for family paths

Before this change, adding a generator meant updating the registry, the
pytest config, the root fixture, CI and the build bootstrap independently.
The fixture also resolved and reassembled the same paths for every test.
The build already reads the advertised family list for runtime packaging.

Development now reads the advertised roots from the same registry. This
reader uses only the standard library so it can run before dependencies
exist. It excludes hidden families, deduplicates shared roots, and rejects
missing projects and paths outside the checkout. Pytest uses the resolved
roots to decide what to collect under Resources and sets the working
directory for family tests. It builds the subprocess import path once per
test session. The dependency installers still use their separate build and
test requirements files; no production inference or rendering code changed.

The new regression ran pytest against a temporary registry that advertised
an unknown family. Before the fix only the root test ran. After the fix both
ran; the family test also imports its module in a child process. A missing
family test directory now gives a setup error. An unadvertised test raises if
imported and was not collected. The build and test commands both passed the
expected installer arguments to a local stand-in for pip without networking.

Four tests tied to the hand-maintained path lists or fixture internals
were replaced with those behavioural checks and invalid-path cases. The
collection comparison found no changes outside the replaced test module.
The migration test now checks that each advertised family receives exactly
one report instead of fixing the count at seven.

Scoped review covered all of the development reader, pytest configuration
and bootstrap, plus the complete root fixture and test changes. The CI
install step is the only change to the workflow; job names, runner types,
permissions and required checks are unchanged. This work neither qualifies
a paper nor establishes a speed improvement for generation.
