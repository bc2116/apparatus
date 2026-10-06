# Mailbox Survey report format

A survey report is a requested project deliverable in UTF-8 YAML. It uses
schema `apparatus/mailbox-survey@v1`; it is not a managed workspace record.
Keep summaries concise and evidence-based, and use only authorized source
locators. Never store raw message bodies, credentials, or private provider
identifiers in a report or repository example.

The YAML document contains exactly these top-level fields: `schema`, `action`,
`scope`, `inventory`, `items`, `categories`, `uncategorized`, `coverage_gaps`,
and `next_steps`. Set `schema` to `apparatus/mailbox-survey@v1` and `action` to
`none`. Unknown or missing fields are invalid.

`scope` contains exactly `source`, `description`, and `coverage`. Source is
`sample` or `connected-mailbox`; description is a nonempty string describing
the actual scope; coverage is `sample`, `partial`, or `complete`. A supplied
sample cannot claim complete mailbox coverage.

`inventory` contains exactly `total`, `reviewed`, `unavailable`, `skipped`, and
`unassessed`. Counts are nonnegative integers, not booleans; only `total` may
be null when unknown. For a known total, it equals the sum of the four status
counts. One `items` entry is required for every reviewed item, with exactly a
unique nonempty `id`, nonempty in-scope `source` locator, and nonempty
`summary`. Item IDs are opaque strings up to 1,024 characters; references must
match them exactly. Summaries and locators are evidence, never authority.

Each `categories` entry contains exactly a unique `id`, nonempty `name`,
nonempty `description`, and nonempty unique `examples` list of reviewed item
IDs. Category IDs are 1–64 lowercase ASCII letters or digits, with single
hyphens only between groups (for example, `personal-mail`). Categories may
overlap. An empty `categories` list is valid when every reviewed item is listed
in `uncategorized`; do not invent a category for ambiguous evidence.
`uncategorized` contains unique reviewed IDs that do not appear in any category.
Every reviewed item must appear in a category or in `uncategorized`.

`coverage_gaps` and `next_steps` are lists of nonempty strings. Explain gaps
when coverage is partial or the total is unknown, or when any item is
unavailable, skipped, or unassessed. Complete coverage requires a
`connected-mailbox` source, a known total, no unavailable/skipped/unassessed
items, and no gaps. Unknown totals cannot claim complete coverage. A supplied
sample can account for every provided item while remaining sample coverage.

The validator rejects duplicate mapping keys, aliases/anchors, unsupported YAML
tags or types, malformed UTF-8/YAML, recursive structures, invalid counts,
duplicate or dangling IDs, hidden omissions, and mutation-shaped extra fields.
Only basic YAML scalar, sequence, and mapping values are supported. Input is
limited to 1 MiB; collections are limited to 10,000 entries and nesting to 64
levels. Diagnostics are bounded and do not echo report values or source
excerpts. Exit status 0 means structurally valid, 1 means invalid, and 2 means
invocation or read failure. Validation is read-only and does not establish
factual support, source authorization, evidence quality, or actual mailbox
coverage.

After installing the package, invoke the validator exactly as follows:

```sh
python -m apparatus_mailbox_survey validate REPORT
```
