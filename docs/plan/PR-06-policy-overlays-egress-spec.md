# PR-06: Policy overlays and egress-gate spec

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§7 privacy and safety model, §14 open questions)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0002-protocol-and-state.md`
- `docs/adr/ADR-0003-harness-agnostic-contract.md`
- `docs/adr/ADR-0004-privacy-model.md` (governs this PR)
- `docs/plan/README.md`
- `docs/spec/workspace.md`
- `docs/spec/records.md` (receipt schema, from PR-04)

## Objective

When this PR lands, the starter payload carries both privacy policy overlays
(standard and private mode) as plain-language documents the assistant reads
and follows, and the repository carries the v1 egress specification that
turns ADR-0004's "enforce at egress" from principle into an enforceable
taxonomy. The egress gate is the load-bearing safety feature of the whole
product; this PR is where its rules become concrete enough for PR-05's
procedures to obey by hand in Phase 1 and for PR-18 to implement in code. It
also narrows the egress open question in design brief §14.

## Deliverables

- `starter/payload/System/policy/standard.md` — the default overlay,
  implementing ADR-0004 "label, don't block" in plain language addressed to
  the assistant:
  - Labeling rules: personally identifying content (names, contact details,
    identifiers) gets a `labels` entry in the record's frontmatter at write
    time; labels never delete or alter content; remembering people in
    `Memory/People/` is a feature, and labels exist to make records
    handleable at the boundary, not suspect.
  - The credential floor, stated as a literal never-relaxed list: passwords,
    API keys, tokens, private keys, and high-confidence government or
    payment identifiers are replaced in place before any durable write (the
    matched token replaced, surrounding prose kept), with a `redaction`
    receipt written to `System/receipts/`.
  - Egress behavior: before any share-shaped step the assistant enumerates
    labeled items in the outbound content, offers a redacted copy, proceeds
    with sensitive items only on the user's explicit choice, and writes an
    `egress` receipt either way. State the three trigger classes inline —
    a deployed workspace does not contain this repository's `docs/`, so the
    overlay must carry the taxonomy itself, kept consistent with
    `docs/spec/egress.md` (the spec is normative; the overlay is the
    deployed carrier).
- `starter/payload/System/policy/private.md` — the private-mode overlay:
  identical structure, but labeled content is blocked from durable Memory
  writes (the assistant asks before saving anything that would carry a
  label, or omits it); the credential floor and egress gate are unchanged —
  private mode only ever tightens.
- Both files are instruction documents, not new record kinds (no eighth
  schema); each opens with one line stating which `privacy_mode` value in
  `System/profile.yaml` activates it. Both ship in every payload; the
  profile selects the active one.
- `docs/spec/egress.md` — the normative v1 egress specification:
  - Definition: egress is content leaving the workspace. The v1 trigger
    taxonomy, each with a one-line definition and two concrete examples:
    (1) **send-intent drafts** — content composed to be sent (email, message,
    form submission) at the moment of handoff to the user for sending;
    (2) **exports and copies out** — a procedure writing or copying workspace
    content to any path outside the workspace folder;
    (3) **publish and upload** — content destined for a website, shared
    drive, ticket system, or any external service.
    Non-triggers, stated explicitly: moves within the workspace (including
    filing to `Deliverables/`), snapshots, and Library ingestion.
  - How procedures declare share-shaped steps: a deterministic, greppable
    marker on the step line — the literal prefix `[share]` — so a human, an
    assistant, and later the PR-18 gate can all find declarations the same
    way. Undeclared share-shaped behavior is a procedure defect.
  - What the gate must present to the human before proceeding: what is
    leaving, where it is going, the enumerated labeled items it contains, the
    offer of a redacted copy, and the explicit choice to proceed or stop —
    followed by an `egress` receipt recording the decision either way.
  - Content-scan semantics for free-form outbound files: drafts in
    `Projects/` and other non-record files carry no frontmatter labels, so
    the spec must define how the gate finds sensitive content in them. v1
    scans outbound content with three deterministic sources: the
    credential-floor patterns; the same PII pattern classes the write-time
    labeler applies (email, phone number, address-like, id-like — pinned in
    PR-12); and exact matches of names and emails drawn from
    `Memory/People/` records. Free-text detection of personal names that
    appear in no People record is out of scope for v1, and the spec states
    that limitation plainly.
  - Mode independence, stated explicitly: egress behavior is identical in
    standard and private mode in v1 — private mode differs only at
    Memory-write time. The gate never varies its behavior by `privacy_mode`.
  - Phase note: in Phase 1 the assistant applies this spec manually;
    PR-18 implements it as tooling. Same rules, one spec.
- `docs/design/design-brief.md` — update §14: replace the egress open
  question with a pointer to `docs/spec/egress.md`, leaving open only what
  genuinely remains open (see Open decisions below).
- `conformance/golden/payload-manifest.txt` — add the two policy files,
  deliberately, in this PR.
- `docs/spec/workspace.md` — `System/policy/` row updated to "now (PR-06)":
  both overlays ship; `System/profile.yaml` `privacy_mode` selects the
  active one.
- `docs/plan/README.md` — status table row for PR-06 updated.

## Acceptance criteria

1. Exactly two new payload files, at
   `starter/payload/System/policy/standard.md` and
   `starter/payload/System/policy/private.md`; no other payload changes.
2. `standard.md` contains the credential-floor list verbatim as ADR-0004
   states it, marked as never relaxed in any mode.
3. `private.md` differs from `standard.md` only in its mode-activation line
   and its Memory-write rules (labeled content blocked from durable Memory
   writes); its credential-floor and egress sections are textually identical
   to `standard.md`'s, verifiable by diff.
4. `docs/spec/egress.md` defines exactly the three v1 trigger classes, names
   explicit non-triggers, fixes the `[share]` step marker, and specifies the
   five things the gate presents to the human.
5. `docs/spec/egress.md` defines the content-scan semantics for free-form
   outbound files (which carry no frontmatter labels): the credential-floor
   patterns, the write-time labeler's PII pattern classes, and exact matches
   of names and emails drawn from `Memory/People/` records — and states
   plainly that free-text names appearing in no People record are a
   documented v1 limitation.
6. `docs/spec/egress.md` states explicitly that egress behavior is identical
   in standard and private mode in v1 — private mode differs only at
   Memory-write time — which is why criterion 3's textual identity holds by
   construction.
7. Every egress decision path in both overlays and the spec ends in a receipt
   (`egress` or `redaction` per the PR-04 receipt schema).
8. Design brief §14 no longer lists the egress trigger taxonomy as fully
   open; it points to the spec and retains only the residual questions.
9. All payload text follows ADR-0001 vocabulary and is addressed to the
   assistant in plain language; nothing requires more than read files, write
   files, run approved commands (ADR-0003).
10. Golden manifest and workspace spec updated in this same PR; payload
    conformance test passes.

## Conformance and tests

- Changed deliberately: `conformance/golden/payload-manifest.txt` gains the
  two policy paths (called out in the PR description).
- Optional but encouraged: extend the conformance tests to assert both policy
  files contain the credential-floor list, pinning the never-relaxed floor as
  executable spec.
- `uv run pytest` green.

## Out of scope

- No egress-gate implementation, no labeler, no redaction code (PR-12 and
  PR-18 build to this spec).
- No changes to the five starter procedures; retrofitting `[share]` markers
  into them happens in PR-07 dogfooding or PR-18, not here.
- No new record kinds and no receipt-schema changes.
- No interview or profile-deployment logic (PR-11/PR-17).

## Dependencies

- PR-04 (record schemas — the receipt schema and reserved `labels` field this
  policy text relies on).

## Open decisions

- **Is chat display egress?** Content shown in the assistant's reply can be
  copied anywhere, but treating every reply as egress would make the gate
  constant noise. Smallest reversible default: chat display is not egress in
  v1; only the three declared trigger classes gate. Record this in
  `docs/spec/egress.md` and keep it listed in brief §14 as residual.
- **Clipboard copies.** A step that puts content on the system clipboard is
  share-shaped in spirit but hard to observe. Default: treat clipboard steps
  as exports (trigger class 2) when a procedure declares them; revisit in
  PR-18.
