# PR-24: App certification and quickstarts

## Context — required reading

- `AGENTS.md`
- `docs/design/design-brief.md` — especially §8 (harness-agnostic contract) and
  §13 (success metrics)
- `docs/adr/ADR-0001-vocabulary.md` — brand-name rule and canonical terms
- `docs/adr/ADR-0002-protocol-and-state.md` — receipts and snapshot semantics
- `docs/adr/ADR-0003-harness-agnostic-contract.md` — certification is the
  support model; this PR implements its §3
- `docs/adr/ADR-0004-privacy-model.md` — the egress check and credential floor
- `docs/adr/ADR-0005-distribution-and-packaging.md` — payload and bootstrapper
  provenance for the runs
- `docs/plan/README.md` — phases, status table, dependencies
- `docs/spec/workspace.md` — the tree the checklist steps observe

## Objective

When this PR lands, Apparatus has a working certification program: a single
executable checklist that defines what "this AI app is supported" means, a
dated support matrix recording real runs of that checklist for at least three
AI apps against the same universal payload, and a one-page quickstart per app
so a first-time user can get from install to "hello" without a terminal. This
is the alpha exit test from the design brief (§13): support becomes an honest,
reproducible, documented claim instead of an assertion, and adding app N+1
becomes a docs-and-testing task per ADR-0003.

## Deliverables

- `docs/certification/checklist.md` — new; the executable certification
  checklist (five steps, pass criteria, evidence to record).
- `docs/certification/matrix.md` — new; the dated support matrix with results
  for at least three AI apps.
- `docs/quickstarts/<app>.md` — new; one quickstart appendix per app that has
  a row in the matrix, filename per the rule in "Conformance and tests".
  Default roster (see "Open decisions"): `claude-code.md`, `cursor.md`,
  `github-copilot.md`. If the roster changes, the file set changes with it.
- `README.md` — modified; add a link to the support matrix (one line or a
  short "Supported AI apps" bullet; no other README changes).
- `conformance/test_certification.py` — new; docs-consistency test (below).
- `docs/plan/README.md` — modified; PR-24 status row only.

## Acceptance criteria

1. `docs/certification/checklist.md` contains exactly five numbered steps, in
   this order: **welcome flow**, **produce a deliverable**, **snapshot and
   restore**, **recall with citation**, **egress check**. Each step specifies:
   setup (starting state), the operator's script (what the human says or
   does), expected assistant behavior, explicit pass criteria, and the
   evidence to record in the matrix row.
2. Every step's pass criteria are observable in workspace files — records,
   receipts under `System/receipts/`, snapshot state, `System/profile.yaml`,
   files under `Deliverables/` — never solely in the assistant's chat text.
   At minimum: welcome flow ends with a deployed profile; produce a
   deliverable ends with a file in `Deliverables/`, a cited source, an updated
   goal, and a snapshot; snapshot and restore proves a deliberate change is
   undone by restoring a prior snapshot; recall answers a Library question
   with a citation **and** returns an honest "not in your library" for a
   question the Library cannot answer;
   the egress check shows labeled items enumerated, a redacted copy offered,
   explicit human choice required, and an egress receipt written.
3. The checklist is app-agnostic: it contains no AI app brand names, uses
   ADR-0001 vocabulary throughout, and no step requires more of the app than
   read files, write files, and run approved commands (ADR-0003).
4. The checklist requires each run to start from a freshly deployed universal
   payload (built by the release pipeline or deployed by the bootstrapper) and
   to record the payload version or build identifier, so all apps are
   certified against the same payload.
5. `docs/certification/matrix.md` contains one results table with a row per
   run and these columns: app name (its own column, so the conformance test
   can parse it), app version, OS, payload identifier, run date, per-step
   pass/fail (one entry per checklist step), evidence notes (the per-step
   evidence the checklist requires recording), overall status, operator, and
   a link to that app's quickstart. At least three AI apps have rows with a
   run date and every column filled in.
6. Matrix results are honest per ADR-0003, checkable row by row: "certified"
   appears in the overall-status column only in rows whose five per-step
   results all read pass; every other row carries a non-certified overall
   status and a note on each failed or partial step; each row's evidence
   notes satisfy the checklist's "evidence to record" list for every step, so
   a reviewer can cross-check row against checklist; no two rows have
   identical evidence notes. Apps not listed are simply not claimed. The PR
   description states who performed each row's run and when (per the
   `AGENTS.md` definition of done: state how criteria were verified).
7. Each quickstart is under one page (≤ 50 lines of body text) and covers
   exactly: install the app, open the workspace folder in it, and say hello to
   start the welcome conversation. Screenshots are optional placeholder
   comments (e.g., `<!-- screenshot: ... -->`). No terminal commands are asked
   of the human. Apart from the app's own name and install steps, vocabulary
   follows ADR-0001.
8. AI app brand names introduced by this PR appear only under
   `docs/quickstarts/` and in `docs/certification/matrix.md` (ADR-0001 rule 4).
   The checklist, README line, and plan row stay brand-free (the README links
   the matrix without naming apps).
9. `README.md` links `docs/certification/matrix.md`; the diff touches no other
   README content.
10. `uv run pytest` is green and the PR-24 row in `docs/plan/README.md` is
    updated in the same PR.

## Conformance and tests

- New `conformance/test_certification.py` (pytest, stdlib only), asserting:
  - `docs/certification/checklist.md` exists and contains the five required
    step headings in order;
  - the checklist contains no app name that appears in the matrix results
    table (parse the table's app column; compare case-insensitively);
  - every app named in the matrix results table has a corresponding file
    under `docs/quickstarts/` (filename rule: app name lowercased, spaces and
    punctuation collapsed to single hyphens — an app listed as "Example App"
    maps to `docs/quickstarts/example-app.md`);
  - `README.md` contains the relative link `docs/certification/matrix.md`.
- `conformance/golden/payload-manifest.txt` is unchanged: this PR ships no
  payload content. Existing payload conformance must stay green.
- `uv run pytest` green is required, as always.

## Out of scope

- No changes to `packages/apparatus-core/` code, the starter payload, the shim
  set, or any CLI verb. A product defect found during a run is recorded as a
  failed step in the matrix with notes — it is not fixed in this PR.
- No automation that drives an AI app to execute the checklist; certification
  runs are performed manually by an operator.
- No app-specific enhancement adapters (ADR-0003 §4) — quickstarts stop at
  "say hello".
- No shipping of quickstarts or the checklist inside the universal payload.
- No marketing language, rankings, or comparisons between apps in the matrix;
  results only.
- No screenshots as binary assets in this PR; placeholders only.

## Dependencies

- PR-22 (Bootstrapper v1), per the status table in `docs/plan/README.md` —
  runs need a deployable payload and a machine report, and PR-22 transitively
  brings the payload builder and release pipeline (PR-20, PR-21).
- A human operator with the roster apps installed must perform the
  certification runs ("Out of scope": no automation drives an app). An
  implementation session that does not have the operator's recorded run
  results cannot satisfy criteria 5–6; it must stop and request the runs —
  never fabricate, extrapolate, or copy matrix rows.

## Open decisions

- **Initial app roster.** No ADR pins which three apps are certified first.
  Smallest reversible default: the three apps whose shims the universal
  payload already carries per ADR-0003 §2 — Claude Code, Cursor, and GitHub
  Copilot (in VS Code). If one is unavailable on the certification machine,
  substitute another available app, add its quickstart, and record what
  actually ran; the matrix reflects reality, not intent.
- **Where quickstarts surface for end users** (repo docs only vs. bundled with
  the installer or a docs site). Smallest reversible default: repo docs only;
  the payload and installer are unchanged by this PR.
