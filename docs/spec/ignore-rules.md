# Workspace ignore rules (v1)

- **Status:** Normative for `System/ignore`.
- Governing decisions: ADR-0002 (files-first and derived caches), ADR-0006
  (sharing-gate removal, preserving the credential floor).

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

The same rules cover [registered project originals](library-sources.md) before
content reads. Ignoring a source preserves its original and registration while
excluding its cached text from search. Retrieval reports the coverage gap;
an old cached excerpt is not evidence for an ignored source.

## Safety boundaries

**Ignore rules never relax the credential floor.** Managed text-write
redaction still applies. There is no App-specific sharing gate; ignore rules
do not supply authority for external actions or permission to retain a
credential. Instruction-migration checks are independent of Library exclusions.

Checks, Library ingest/search and recall report skip counts and rule provenance
in their results or command output without routine receipts. JSON retrieval keeps
stdout machine-readable and writes its ignore report to stderr. Feature-off
operations print the disabled outcome and leave history unchanged. Meaningful
mutation and redaction receipts retain their existing bounded metadata; historical
routine receipts remain readable and are never deleted by this policy.

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
- Any supported pattern that matches a directory hides that directory and every
  descendant.
- A trailing `/` means directory-only matching, but is not required for
  descendant exclusion once a directory matches.
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

Fresh installs also include editable `System/ignore` rules for `node_modules/`,
`.venv/`, `__pycache__/`, and `.pytest_cache/`. These generated dependencies and
caches need no onboarding selection. Remove a pattern if it holds useful sources.
They are user rules, disabled by `ignore_rules: false`; built-ins still apply.
Init updates exact known stock ignore files while preserving customized bytes.

## Reporting count

A skipped path is counted at the boundary where an operation declines it. An
ignored file counts once. An ignored directory counts once and is pruned before
traversal, so its descendants are neither opened nor separately counted. Each
report separates built-in and user-rule counts and names whether provenance was
the built-in defaults alone or the built-ins plus `System/ignore`.
