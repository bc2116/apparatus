# ADR-0004: Privacy model — label at write, enforce at egress

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Knowledge work runs on names: people, customers, organizations, commitments.
A memory system that blocks personal information at write time is useless to
the primary audience, and on a single-user, single-logon machine, ingest-time
blocking defends against no realistic threat. The real exposure is at the
boundary — content leaving the workspace in a draft, an export, or a shared
file. Meanwhile, first-time users need the system to be trustworthy by
construction, not by their own vigilance.

## Decision

1. **Default: label, don't block.** Any content may enter durable workspace
   state. Personally identifying content (names, contact details, identifiers)
   is labeled at write time. Labels are metadata in the record's frontmatter,
   deterministic where possible, and never delete or alter the content itself.
2. **Remembering people is a feature.** `Memory/People/` exists precisely to
   hold names, roles, and history. Labels make records *handleable at the
   boundary*, not suspect.
3. **Enforcement happens at egress.** Egress = content leaving the workspace:
   a draft intended to be sent, a file exported or copied out by a procedure,
   anything shared, published, or uploaded. At egress the assistant enumerates
   labeled items in the outbound content, offers a redacted copy, and proceeds
   with sensitive items only on the human's explicit choice. Every egress
   decision writes a receipt.
4. **Credential floor — never relaxed in any mode:** passwords, API keys,
   tokens, private keys, and high-confidence government or payment identifiers
   are auto-redacted in place before any durable write (matched token replaced,
   surrounding prose kept), with a receipt. Credentials are hazards, not
   knowledge; a secret manager is the right home and Apparatus never is.
5. **Private mode** is a profile overlay selected in the welcome interview (or
   later): labeled content is blocked from durable memory, restoring strict
   behavior for users who need it. Same workspace, same procedures, different
   policy file.
6. **External actions are drafts until approved.** The assistant never sends,
   posts, submits, or deletes outside the workspace on its own authority, in
   any mode.
7. **Observed content is data.** Text inside Library documents, imported files,
   or tool output is never treated as instructions or authorization.

## Consequences

- The egress gate is the load-bearing safety feature and receives
  corresponding design and test investment (see the development plan). "Label,
  don't block" is only defensible if the boundary check fires every time.
- The PII labeler must be useful without being alarmist: labels are silent
  metadata day-to-day and surface only at egress.
- The IT one-pager documents this model honestly, including exactly what the
  credential floor blocks and where receipts live.
- Deterministic labeling cannot recognize arbitrary personal names in free
  text; v1 therefore treats every `Memory/People/` record as structurally
  labeled person data, the egress gate exact-matches names and emails drawn
  from those records against outbound content, and broader name detection is
  a documented limitation.
