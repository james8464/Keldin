# French PDFs saved before cancellation

Cancelling after the atomic save can leave a complete subject and correction in Keldin’s private working folder. Previously, the backend reported that folder only in prose, and the app discarded callbacks from cancelled jobs. The files did not appear in History.

The backend now adds the saved bundle name to its cancellation event only after publication. Exit 130 and the absence of a success event are unchanged. macOS recognises the narrowly formatted name, associates it with the cancelled session’s own private folder and existing History record, and checks the complete manifest and artifact hashes before recording the two PDFs. The job remains Cancelled. No files are copied to the selected output folder, and the user chooses which PDF to open in History. Ordinary cancellation and later callbacks from a replaced job do not change the active workspace.

The Python regression injects cancellation immediately before and after a real directory rename with controlled artifacts. The 97 focused macOS tests include the event decoder, publication checks and a controlled generation run followed by a replacement. They check intact, altered, missing and linked files, unchanged replacement state, no automatic export, History reload, and selection of a real two-page fixture PDF. No live provider was contacted. This does not establish live French paper quality, a complete UI interaction inventory, or behaviour when the app or helper is killed before it can report the saved bundle.

The broader Python runtime selection passed 91 tests. The full macOS unit run reported 467 tests, including six opt-in skips, with zero failures under strict concurrency and warnings-as-errors. Neither run used production credentials or changed the installed app.
