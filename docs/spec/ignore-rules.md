# Workspace ignore rules (v1)

- **Status:** Normative for `System/ignore`.
- Governing decisions: ADR-0002 (files-first and derived caches), ADR-0004
  (privacy at egress and the credential floor).

`System/ignore` lets the user tell the workspace machinery to leave selected
workspace-relative paths alone. It is useful for a scratch area, a sensitive
folder, or a third-party dump that should remain in the workspace without
being read by the Library. Ask your assistant to edit this file when your
needs change.

Ignoring applies to Library ingest and extraction, the local Library search
index, recall, and record checks. A matched Library source is not opened or
extracted. A later refresh removes a newly matched source from the local index
and recall evidence. Record checks skip matched records, while reporting their
count so the exclusion is visible.

## Safety boundaries

**Ignore rules never affect the egress gate or the credential floor.** Content
explicitly sent outside the workspace is always scanned at egress, even when
its path matches `System/ignore`. Durable-write credential redaction always
applies. Ignore rules are not an approval to send, publish, share, or retain a
credential.

Every existing receipt-producing command records accurate skip counts and rule
provenance in its receipt; receipts do not list ignored paths or file contents.
Library search has no receipt event in the closed v1 receipt schema, so it
reports the same count and provenance in command output instead. JSON search
keeps stdout machine-readable and writes this report to stderr.

## File and supported syntax

`System/ignore` has one pattern per line. Blank lines and lines beginning with
`#` are comments. Patterns are workspace-relative and use `/` as their path
separator.

This is a small, documented subset of gitignore-style syntax, not full
gitignore compatibility:

- `*` matches zero or more characters within one path component.
- `?` matches one character within one path component.
- `**` matches across directory components.
- A pattern without `/` matches a filename or directory name at any depth.
- A trailing `/` matches that directory and everything below it.
- A leading `/` is accepted as an explicit workspace-root anchor.

Negation (`!`), escapes (`\\`), and character classes (`[...]`) are not
supported. `apparatus check` reports each unsupported line in plain language;
it does not silently reinterpret it. A present ignore file that is unreadable,
not UTF-8 text, unsafe (including a symbolic link or reparse point), or contains
unsupported syntax is invalid. Ignore-aware content operations stop before
reading candidate content until the file is repaired; `apparatus check`
reports the actionable problem.

The following built-in defaults always apply and cannot be disabled:

- `.DS_Store`
- `Thumbs.db`
- `desktop.ini`
- `.git` and everything below it

Built-in defaults are not user rules. The shipped file comments them for
orientation only.

## Reporting count

A skipped path is counted at the boundary where an operation declines it. An
ignored file counts once. An ignored directory counts once and is pruned before
traversal, so its descendants are neither opened nor separately counted. Each
report separates built-in and user-rule counts and names whether provenance was
the built-in defaults alone or the built-ins plus `System/ignore`.
