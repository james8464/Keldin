# AQA Accounting Paper 1: question and scheme agreement

Compared the offline seed 26080100 preview with the June 2025 AQA
7127/1 question paper and mark scheme held locally. Both question papers
have 36 pages. The practice scheme has 24 pages; the reference has 26.
This was a page and credit review, not a live model run or a calibration
of difficulty.

Question 14.1 now states the year end and gives both debenture periods
explicitly. The earlier debenture was outstanding at the start of the year
and repaid at the end of October. The new one was issued on 1 September.
The case data now owns the rates and durations used by the question and
the workings, rather than leaving candidates to infer a missing date.

Question 15.1 asked candidates to balance capital accounts and bring down
the balances, but the printed scheme previously closed in December and
omitted the totals and brought-down balances. The new table closes on
the retirement date, 31 August, and shows the balances on 1 September.
The PDF checker verifies the dates and every cell using the independent
solver. Retained packages without the table-policy field still use their
historical check.

No mark allocation or computed answer changed. The same-seed page
comparison with the signed baseline found changes only on question
pages 12, 13 and 16, and scheme pages 13 and 18. The appraisal questions
were not qualified by this check.

The 40 scheme-pagination tests now render their fixed-seed baseline once,
then copy the files into a private directory for each test. All assertions
and mutations were kept. One local comparison on the same Mac went from
15.03 to 6.38 seconds. This measures the test module, not paper generation.
