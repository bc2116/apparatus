# Egress Specification (v1)

- **Status:** Normative for content leaving an Apparatus workspace.
- Governing decisions: ADR-0002 (receipts), ADR-0003 (minimum AI-app
  capabilities), and ADR-0004 (privacy model).

## Definition and scope

**Egress is content leaving the workspace.** The egress check runs before any
share-shaped step in one of the three v1 trigger classes below. These are the
only trigger classes in v1.

### 1. Send-intent drafts

Content composed to be sent as an email, message, or form submission triggers
the check at the moment the assistant hands it to the user for sending.

- Handing the user an email draft addressed to a customer.
- Handing the user a completed form response for submission.

### 2. Exports and copies out

A procedure writing or copying workspace content to any path outside the
workspace folder triggers the check before the write or copy.

- Writing a report from `Projects/` to a folder outside the workspace.
- Copying a Library excerpt to the clipboard in a declared procedure step.

A clipboard step is an export when a procedure declares it. Passive clipboard
activity that is not part of a procedure is not observable in v1; tooling for
that case remains a PR-18 question.

### 3. Publish and upload

Content destined for a website, shared drive, ticket system, or any other
external service triggers the check before publication or upload.

- Publishing a finished update to a website.
- Uploading a workspace document to a shared drive.

## Non-triggers

The following actions do not trigger the v1 egress check:

- moving or filing content within the workspace, including filing finished work
  in `Deliverables/`;
- taking a snapshot;
- ingesting a source document into the Library; and
- displaying ordinary content in chat.

Chat display alone is not egress in v1. A reply that hands the user content
composed for sending is still a send-intent draft and therefore does trigger the
check. Whether other chat display should become a trigger remains an open
question for a later version.

## Procedure declarations

Every share-shaped procedure step must start its instruction text with the
literal prefix `[share]`, immediately after the numbered-list marker:

```markdown
4. [share] Hand the email draft to the user for sending.
```

The marker declares that the step requires the egress check; it does not grant
permission to perform the step. A human, the assistant, and later tooling can
find the same declarations by searching for `[share]`. Share-shaped behavior
without this marker is a procedure defect.

## Finding sensitive content

For outbound records, inspect their frontmatter `labels` and enumerate the
labeled items present in the outbound content. Records under `Memory/People/`
are structurally labeled person data even when their frontmatter omits
`labels`.

Drafts in `Projects/` and other free-form outbound files may have no
frontmatter. Scan their outbound content using exactly three deterministic
sources:

1. the credential-floor patterns for passwords, API keys, tokens, private
   keys, and high-confidence government or payment identifiers;
2. the same PII pattern classes used by the write-time labeler: email, phone
   number, address-like, and id-like patterns, with their exact definitions to
   be pinned in PR-12; and
3. exact matches of names and emails drawn from `Memory/People/` records.

Free-text detection of personal names that appear in no `Memory/People/` record
is out of scope for v1. Such names may not be found; this is a documented v1
limitation, not evidence that the content contains no personal information.

The credential floor is never optional. Replace each matched credential token
in place, keep its surrounding prose, and write a `redaction` receipt under
`System/receipts/` according to the receipt-record rules below before the egress
decision continues. Never offer an option to send, export, publish, or upload
an unredacted credential-floor match.

## What the check presents

Before proceeding, present all five of these things to the human:

1. **What is leaving:** identify the draft, file, or content.
2. **Where it is going:** name the intended recipient, path, or service.
3. **Labeled items:** enumerate every labeled item found in the outbound
   content, or state that none were found.
4. **Redacted-copy offer:** offer to make and use a copy with sensitive items
   removed or replaced.
5. **Explicit choice:** ask the human to proceed with the sensitive content,
   proceed with a redacted copy, or stop.

Proceed with sensitive content only after the human explicitly chooses it. If
the human chooses a redacted copy, use that copy. If the human stops, do not
perform the share-shaped step. In every case, finish the decision path by
writing an `egress` receipt under `System/receipts/` that records what was to
leave, the destination, the findings, the option chosen, and whether anything
left. Follow the receipt-record rules below. Any credential-floor redaction
also has its separate `redaction` receipt.

## Receipt records

Before writing a `redaction` or `egress` receipt, create `System/receipts/` if
it is absent. Each receipt is a Markdown record with YAML frontmatter delimited
by `---` lines. The frontmatter must contain:

- `schema: apparatus/receipt@v0`;
- the event matching the decision path: `event: redaction` or `event: egress`;
- `timestamp` set to the current UTC instant in `YYYY-MM-DDTHH:MM:SSZ` form;
  and
- a one-sentence `summary`.

Use the same UTC instant for the filename
`YYYY-MM-DD-HHMMSS-<event>.md`, where `<event>` matches the frontmatter. If that
name already exists, append `-2`, `-3`, and so on before `.md`. The Markdown
body records the detail required by the decision path: what was examined and
redacted for `redaction`; or what was to leave, the destination, findings,
choice, and whether anything left for `egress`.

## Mode independence

Egress behavior is identical in standard and private mode in v1. Private mode
differs only at Memory-write time. The check must never vary its behavior based
on `privacy_mode`.

## Phase 1 and implementation

In Phase 1, the assistant applies this specification manually using the files
in the workspace. PR-18 implements the same rules as tooling; implementation
must not change their meaning.
