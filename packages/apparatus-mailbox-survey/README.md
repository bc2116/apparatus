# Apparatus Mailbox Survey

This separately packaged module provides a portable Skill and a read-only
validator for requested, evidence-based mailbox category reports. It can use an
explicitly supplied sample when an authorized native mailbox reader is
unavailable. It does not connect to a mailbox, acquire credentials, call a
model, or change mail.

The package contains the Skill and report-format reference, plus synthetic
sample and report examples. Installing the Python package makes those resources
available to the package; it does not deploy the Skill into a work area. The
core package and the deployed Skill are separate. The module is not covered by
core managed recovery, and automatic discovery by an AI app has not been
verified. The assistant can read the deployed Skill explicitly.

## Validate a report

Validation does not require Apparatus Core. From this development workspace run:

```sh
uv run --package apparatus-mailbox-survey python -m apparatus_mailbox_survey validate REPORT.yaml
```

After the module is separately released and available from the configured
package index, install the lifecycle extra to use its deployment commands:

```sh
pip install 'apparatus-mailbox-survey[lifecycle]'
```

This is an installation instruction for a future released package; it does not
claim that version 0.1.1 is currently published. The `lifecycle` extra supplies
the compatible Apparatus Core dependency required for deployment. Without it,
standalone report validation remains available, while `status`, `install`, and
`repair` report the missing lifecycle dependency.

## Inspect and deploy the Skill

Use the explicitly enrolled work-area root with the module commands:

```sh
python -m apparatus_mailbox_survey status WORKAREA
python -m apparatus_mailbox_survey install WORKAREA
python -m apparatus_mailbox_survey repair WORKAREA
```

`status` reads the fixed Skill and reference paths and reports whether each is
missing, current, or modified, along with the aggregate state. `install` and
`repair` create only missing packaged files. Exact current files are preserved;
modified, foreign, malformed, linked, or unsafe occupants stop the operation
before publication. These commands never overwrite or remove existing files.
Use the enrolled work-area root, not a bound project directory. Resolve reported
conflicts by reviewing and preserving user changes before retrying.

This is a create-only installation slice, not the full module lifecycle. It has
no deployed-version record and does not update or remove deployed files. The
sample and example report are package resources and are not copied into the
work area. Module files remain outside core-managed snapshots and recovery.

The report schema and limits are described in
`src/apparatus_mailbox_survey/resources/skills/apparatus-mailbox-survey/references/report-format.md`.
Validation checks structure and internal consistency only; it cannot establish
factual support, authorization, evidence quality, or actual mailbox coverage.
