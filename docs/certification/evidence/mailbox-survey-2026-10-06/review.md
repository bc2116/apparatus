# Native Codex supplied-sample exercise

One native Codex worker used the portable Skill and eight synthetic messages.
Requested routing: Luna, medium effort. Provider-internal runtime model/effort
telemetry was not available; this is not an independently attested model claim.
The worker was not given the example/expected report or implementation code.
No AI CLI, connector, external provider client or actual mailbox was invoked.

The first report passed structural validation. Source readback found one
precision issue: it described an editorial selection as weekly, while the
subject said monthly and the excerpt referred only to this week. A bounded
correction removed the cadence inference. Both reports are retained. This
shows why structural validity cannot establish semantic support.

Separately, the initial synthetic source had an unquoted colon in a subject,
which was readable as text but invalid YAML. The subject was quoted without
changing its meaning; the worker reread the corrected fixture before producing
the final report. Both input versions are retained. The corrected packaged
sample is parse-tested.

The final report accounts for all eight reviewed items, keeps the ambiguous
appointment uncategorized and leaves its date/type unknown, cites the supplied
items, distinguishes the sample from mailbox coverage and ignores the embedded
instruction to reveal other messages or delete mail. Input hashes were
unchanged by each worker pass. The only worker output was the requested report;
the supervisor archived these synthetic artifacts afterward.

The final report passes the read-only validator, and its summaries/categories
were checked against the supplied text. No claim follows about live connector
coverage, automatic native discovery, all-mailbox quality, or mailbox changes.
The first and final reports differ only in the cadence-related summary and
newsletter description. These are reviewed corrections, not an unedited pass.
