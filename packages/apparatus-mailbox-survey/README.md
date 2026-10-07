# Apparatus Mailbox Survey

This separately packaged prototype provides a portable Skill and a read-only
validator for a requested, evidence-based mailbox category report. It can work
from an explicitly supplied sample when an authorized native mailbox reader is
unavailable. It does not connect to a mailbox, acquire credentials, call a
model, install itself into a work area, or change mail.

The Skill and examples are package resources under
`src/apparatus_mailbox_survey/resources/`. The sample is wholly synthetic.
Read `resources/skills/apparatus-mailbox-survey/SKILL.md` for the workflow and
`resources/skills/apparatus-mailbox-survey/references/report-format.md` for the report contract, privacy boundaries, and
validation instructions.

After installing this package, validate a report with:

```sh
python -m apparatus_mailbox_survey validate REPORT
```

Validation checks structure and internal consistency only. It cannot establish
that a report is factually supported, complete beyond its declared scope,
authorized, or useful. The command reads the report and never repairs or writes
to it.
