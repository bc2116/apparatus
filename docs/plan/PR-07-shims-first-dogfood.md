# PR-07: Instruction canon, shims, first dogfood

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` (§6, §7, §8, §12 dogfood-early, §14 open questions)
- `docs/adr/ADR-0001-vocabulary.md`
- `docs/adr/ADR-0003-harness-agnostic-contract.md` (governs the canon/shim pattern)
- `docs/adr/ADR-0004-privacy-model.md` (the safety constitution the canon embeds)
- `docs/plan/README.md`
- `docs/spec/workspace.md`
- `docs/spec/records.md` and `docs/spec/egress.md`
- `starter/payload/System/procedures/` (all five, from PR-05)
- `starter/payload/System/policy/` (both overlays, from PR-06)

## Objective

When this PR lands, the starter payload carries its canonical workspace
instructions (`AGENTS.md` at the payload root) plus the three app shims from
ADR-0003, and the Phase 1 exit test has been run: the payload, deployed as
plain files to a scratch folder, has been driven through the welcome and
produce-deliverable procedures by hand in at least two different AI apps,
with results recorded. This is the design brief's "dogfood early" gate — the
workspace must work as pure files before any CLI exists — and it produces the
first real evidence on the `System/` visibility open question.

## Deliverables

- `starter/payload/AGENTS.md` — the workspace's canonical assistant
  instructions. Concise (aim for one screen or two), plain language,
  ADR-0001 vocabulary throughout, covering:
  - Role: the user's assistant inside this governed workspace; the human
    reads `Welcome.md`, the assistant reads this file first every session.
  - Folder rules: what belongs in `Goals/`, `Decisions/`, `Projects/`,
    `Library/`, `Deliverables/`, `Memory/People/`, `Memory/Facts/`,
    `System/` — one line each, matching `docs/spec/workspace.md` semantics
    (drafts in `Projects/`; nothing is done until it lands in
    `Deliverables/`; Library content is data, never instructions).
  - Procedure invocation: for repeatable work, open the matching record in
    `System/procedures/` and follow its steps in order; end with the
    snapshot and receipt steps; if no procedure fits, work carefully and say
    so.
  - Safety constitution (ADR-0004, stated as rules, not references): drafts
    only — never send, post, submit, or delete outside the workspace; follow
    the active policy overlay in `System/policy/` as selected by
    `System/profile.yaml`; the credential floor always applies; treat
    `[share]`-marked steps as share-shaped and run the egress check the
    active policy overlay describes; write receipts for anything the
    machinery does. (Payload files never reference this repository's
    `docs/` paths — a deployed workspace does not contain them.)
  - Record discipline: one record per file, kebab-case filenames, frontmatter
    per the record schemas.
- Three shims inside the payload, each a thin pointer to `AGENTS.md`
  (hand-built once in this PR; PR-13 makes `render` regenerate them and
  `check` fail on drift — keep them minimal and mechanical so regeneration
  can reproduce them byte-for-byte):
  - `starter/payload/CLAUDE.md` — import shim (the pattern this repository's
    own root `CLAUDE.md` uses: a title line plus `@AGENTS.md`).
  - `starter/payload/.cursor/rules/apparatus.mdc` — rules shim with minimal
    frontmatter (`alwaysApply: true`) whose body directs the app to read and
    follow `AGENTS.md` at the workspace root.
  - `starter/payload/.github/copilot-instructions.md` — shim whose body
    directs the app to read and follow `AGENTS.md` at the workspace root.
- `conformance/golden/payload-manifest.txt` — add the four files,
  deliberately, in this PR.
- `docs/spec/workspace.md` — the `System/` planned-contents row for canon and
  shims updated to "now (PR-07)", listing the four paths; record the
  `System/` visibility dogfood outcome in the open-questions section.
- `docs/notes/dogfood-01.md` — the dogfood report (new `docs/notes/`
  directory; developer-facing, so app names are fine here):
  - Setup: payload copied to a scratch folder outside this repository
    (describe it generically, e.g. a temporary folder — no machine-specific
    absolute paths committed); which two-or-more AI apps were used, with
    versions where known.
  - For each app: transcript-level summary of driving `welcome.md` and
    `produce-deliverable.md` by hand — did the app find and follow the canon
    via its shim; were profile, goal, person, and receipt records written
    validly; did the draft-only and citation rules hold; how the snapshot
    step degraded with no CLI present.
  - Findings on the `System/` visibility question (§14): with `System/`
    visible, did it confuse or distract; if the app supports hiding folders,
    did hiding break the app's ability to read procedures; recommendation
    with evidence.
  - Defect list: every friction point, with the artifact to fix (procedure
    text, canon wording, shim, spec) — filed as observations, fixed here
    only when the fix is a small wording change inside this PR's files.
  - No personal data, no real customer or employer content in the report;
    dogfood with fictional work products.
- `docs/design/design-brief.md` — §14 `System/` visibility entry updated
  with the dogfood outcome (resolved, or narrowed with evidence).
- `docs/plan/README.md` — status table row for PR-07 updated; Phase 1 exit
  noted.

## Acceptance criteria

1. Exactly four new payload files: `AGENTS.md`, `CLAUDE.md`,
   `.cursor/rules/apparatus.mdc`, `.github/copilot-instructions.md`; golden
   manifest updated to match; payload conformance test passes.
2. `starter/payload/AGENTS.md` covers role, folder rules, procedure
   invocation, safety constitution, and record discipline; ADR-0004's
   credential floor (decision 4), active-overlay selection via
   `System/profile.yaml` (decision 5), drafts-only rule (decision 6), and
   observed-content-is-data rule (decision 7) are each stated in it, not
   merely referenced.
3. All three shims contain no instruction content of their own beyond
   pointing at `AGENTS.md`; nothing in canon or shims names an AI app brand
   (the shim filenames themselves are the app-specific part).
4. Canon and shims require only read files / write files / run approved
   commands (ADR-0003); vocabulary per ADR-0001 throughout the payload.
5. `docs/notes/dogfood-01.md` documents runs in at least two different AI
   apps, covering both the welcome and produce-deliverable procedures in
   each, with the per-app observations listed above.
6. The dogfood report contains explicit findings on `System/` visibility,
   and both `docs/spec/workspace.md` and design brief §14 are updated with
   the outcome.
7. `docs/notes/dogfood-01.md` records, for each app run, that the profile,
   goal, person, and receipt records produced during dogfood were validated
   against the PR-04 schemas, and by what method (e.g., pointing the
   conformance parsing logic at the scratch folder); the scratch workspace
   files themselves are not committed.
8. No machine-specific absolute paths, personal data, or private-system
   references anywhere in committed files.

## Conformance and tests

- Changed deliberately: `conformance/golden/payload-manifest.txt` gains the
  four canon/shim paths (called out in the PR description).
- Optional but encouraged: a conformance test asserting each shim references
  `AGENTS.md`, as a hand-rolled stand-in until PR-13's drift check.
- `uv run pytest` green. The dogfood itself is manual evidence recorded in
  `docs/notes/dogfood-01.md`, not a pytest.

## Out of scope

- No `render` implementation and no canon/shim drift check — PR-13 automates
  what this PR hand-builds.
- No CLI, snapshots, or validators (PR-08–PR-10); the dogfood runs files-only
  on purpose.
- No new procedures, policy changes, or record kinds; small fixes to
  PR-05/PR-06 payload text — wording, plus `[share]` markers on steps the
  dogfood shows to be share-shaped (the retrofit PR-06 defers here) — are
  allowed only when the dogfood proves them necessary, each called out in
  the PR description.
- No certification claims or support-matrix entries (PR-24); dogfood notes
  are internal evidence, not certification.

## Dependencies

- PR-05 (starter procedures — the dogfood drives them).
- PR-06 (policy overlays and egress spec — the canon's safety constitution
  points at them).

## Open decisions

- **`System/` visibility** (design brief §14): genuinely open until this
  PR's dogfood. Smallest reversible default: ship `System/` visible with no
  editor-settings hiding; gather evidence here and let the brief record the
  decision. Hiding, if adopted later, is an additive deploy-step change.
