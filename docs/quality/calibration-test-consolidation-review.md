# Shared checks for retained calibration reports

The five report test modules used the same release flags and repeated the
registry lookup. A single parameterized module now checks each linked report
against its producer's declared output. The list of expected cases must
match the registry, so a new linked report cannot silently escape testing.

The module keeps each family-specific source count and forbidden-text check.
It still checks twenty distinct generated papers per route, the original
subject-specific measures, and the absence of empirical difficulty claims.
It now also requires every declared paper to appear in its report. A missing
paper or an empty structural-check map can no longer pass by vacuity.

The five original modules passed twenty tests. The replacement ran sixteen
cases across the same five reports. Review covered the complete old and new
test files and the relevant registry records. No calibration data, runtime
generation, release gates or published evidence were changed. These tests do
not measure actual learner difficulty or establish official equivalence.
