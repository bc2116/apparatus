# Apparatus Mailbox Survey

This separately packaged module provides a portable Skill and a read-only
validator and summary for requested, evidence-based mailbox category reports. It can use an
explicitly supplied sample when an authorized native mailbox reader is
unavailable. It does not connect to a mailbox, acquire credentials, call a
model, or change mail.

The package contains the Skill and report-format reference, plus synthetic
sample and report examples. Installing the Python package makes those resources
available to the package; it does not deploy the Skill into a work area. The
core package and the deployed Skill are separate. The module is not covered by
core managed recovery, and automatic discovery by an AI app has not been
verified. The assistant can read the deployed Skill explicitly.

## Validate or summarize a report

Report validation and summaries do not require Apparatus Core. From this development workspace run:

```sh
uv run --package apparatus-mailbox-survey python -m apparatus_mailbox_survey validate REPORT.yaml
uv run --package apparatus-mailbox-survey python -m apparatus_mailbox_survey summary REPORT.yaml
```

`summary` reads an existing report and prints its declared scope and coverage,
inventory, category example counts, uncategorized count and coverage gaps.
Categories can overlap; their counts are reviewed examples, not mailbox-wide
totals. Unknown totals remain unknown. The summary reflects report claims and
does not verify evidence, authority or actual coverage.

Invalid reports produce validation findings without a partial summary. The
command leaves the report unchanged, excludes individual message details and
proposed actions, and shows at most 20 categories and 20 gaps. Long display
strings stop at 240 characters with a truncation marker; omitted entries are
counted. Control characters are escaped. Review the original report when more
detail is needed.

After the module is separately released and available from the configured
package index, install the lifecycle extra to use its deployment commands:

```sh
pip install 'apparatus-mailbox-survey[lifecycle]'
```

This is an installation instruction for a future released package; it does not
claim that version 0.1.4 is currently published. The `lifecycle` extra supplies
the compatible Apparatus Core dependency required for deployment. Without it,
standalone report validation and summaries remain available, while `status`, `install`, and
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

Successful lifecycle output also includes `release_matches` for each fixed
asset and `complete_release_matches` for their intersection. Matching requires
both exact byte length and SHA-256. The packaged historical manifest records
accepted source versions 0.1.0 through 0.1.3 and their source commits; current
0.1.4 matches come from this package's validated resources. Identical files may
match several versions. A complete match requires both files to match the same
version. Missing or unrecognized files have no matches.

These are content matches, not proof of origin, authenticity, package presence,
or a durable installed-version record. `version` identifies the executing
package. Older recognized content remains `modified` when it differs from the
current package, so it still blocks install and repair. Status reads existing
captured bytes and leaves files unchanged; this release does not update them.
An invalid packaged manifest stops lifecycle commands before any creation.

If installation fails after creation starts, it may leave partial files and
directories. Inspect with `status`; use `repair` when the remaining assets match
the package. Review and preserve conflicting edits or incomplete bytes before
retrying. Do not use the Skill until status reports `current`. Failed
installation preserves partial state rather than deleting it; publication of
the two files is not atomic and no rollback is promised.

This is a create-only installation slice, not the full module lifecycle. It has
no deployed-version record and does not update or remove deployed files. The
sample and example report are package resources and are not copied into the
work area. Module files remain outside core-managed snapshots and recovery.

The report schema and limits are described in
`src/apparatus_mailbox_survey/resources/skills/apparatus-mailbox-survey/references/report-format.md`.
Validation checks structure and internal consistency only; it cannot establish
factual support, authorization, evidence quality, or actual mailbox coverage.
