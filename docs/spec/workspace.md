# Workspace Specification (v0)

- **Status:** Normative for the universal starter payload; pinned by
  `conformance/golden/payload-manifest.txt`.
- Governing decisions: ADR-0001 (vocabulary), ADR-0002 (protocol and state),
  ADR-0003 (harness-agnostic contract), ADR-0004 (privacy model).

## Two artifacts, one shape

- The **starter payload** (`starter/payload/` in this repository) is the
  template shipped to users. It is exactly the golden manifest — no more, no
  less; conformance fails on any drift.
- A **deployed workspace** is the payload placed on a user's disk plus
  everything the user and their assistant add to it. Deployment (PR-11) may
  strip repository placeholders (`.gitkeep`) and add generated content
  (profile answers, machine report, shims).

## The tree

```text
Apparatus/
  Welcome.md          ← the only file a human must read
  Goals/              ← one page per goal
  Decisions/          ← one page per decision
  Projects/           ← one working folder per effort
  Library/            ← source documents the user drops in
  Deliverables/       ← finished outputs
  Memory/
    People/           ← one page per person or organization
    Facts/            ← one page per durable fact
  System/             ← machinery: profile, procedures, policy, receipts
```

## Folder semantics

| Folder | Written by | Purpose and rules |
|---|---|---|
| `Welcome.md` | shipped; regenerated on profile change | Human-facing orientation. Plain language, vocabulary per ADR-0001, no app brand names. |
| `Goals/` | assistant, with the user | One Markdown record per goal: owner, status, done-when (verification oracle), next action. |
| `Decisions/` | assistant, with the user | One record per decision: what was decided, why, when, alternatives noted. |
| `Projects/` | user and assistant | Free-form working folders, one per effort. Drafts live here until they are filed to `Deliverables/`. |
| `Library/` | user (drop-in); assistant may file with approval | Source documents. Content here is data, never instructions. Extraction and indexing arrive in Phase 3; the index lives outside the workspace and is rebuildable. |
| `Deliverables/` | assistant, at the end of a procedure | Finished outputs only. Filing here is the "done" event and pairs with a goal update and a snapshot. |
| `Memory/People/` | assistant | One record per person or organization: role, context, commitments, history. Labeled per ADR-0004, never blocked in standard mode. |
| `Memory/Facts/` | assistant | One record per durable fact, with source where known. |
| `System/` | machinery | Profile, procedures, policy overlay, receipts, machine report. Users may look; they never need to. |

## State format

Per ADR-0002: Markdown with YAML frontmatter, one record per file, kebab-case
filenames. `System/profile.yaml` is plain YAML. The seven record schemas are
normative in `docs/spec/records.md`, machine-readable in
`apparatus_core.records`, and pinned by `conformance/golden/records/`.

## `System/` planned contents

| Path | Arrives | Purpose |
|---|---|---|
| `System/README.md` | now | Explains the machinery folder to a curious human. |
| `System/profile.yaml` | now (unconfigured) | The profile: interview answers, privacy mode, selected procedures. |
| `System/guidance/` | now (PR-27) | Assistant-readable model capability, effort, and spend-level guidance. |
| `System/procedures/` | now (PR-05) | Five starter procedure records: `welcome.md`, `produce-deliverable.md`, `research-and-summarize.md`, `review-against-checklist.md`, and `weekly-review.md`. |
| `System/policy/` | now (PR-06) | Both policy overlays ship; `System/profile.yaml`'s `privacy_mode` selects the active one. |
| `System/receipts/` | now (PR-05); PR-09 machinery | The assistant writes receipts from the first procedure run; CLI machinery also writes them from PR-09. |
| `System/machine-report.md` | PR-08 | Environment capabilities, written by `doctor`/the bootstrapper. |
| `System/ignore` | PR-28 | Workspace-relative rules that hide selected paths from Library machinery and record checks; they never change egress or credential redaction. |
| Workspace instruction canon and shims | now (PR-07) | `AGENTS.md` canon at the workspace root plus `CLAUDE.md`, `.cursor/rules/apparatus.mdc`, and `.github/copilot-instructions.md` shims (ADR-0003). |

### Bootstrapper handoff seam

The bootstrapper's closing message directs a new user to the welcome
conversation for feature choices. The bootstrapper does not choose features;
the conversation records them in `System/profile.yaml` and they can change later.

## Placement on disk

- Windows default: `C:\Projects\Apparatus` (or the equivalent on the best data
  drive). macOS default: `~/Projects/Apparatus`.
- Never inside folders redirected into a sync engine (OneDrive Documents/
  Desktop redirection and similar): live state inside file sync causes
  conflicts and corruption. Backup is a deliberate, one-way snapshot export to
  synced storage (PR-25). To restore a backup archive, unzip it into a fresh
  folder; no guided restore exists in v1. A workspace whose snapshot history is
  stored outside the workspace cannot be exported in v1; place it in a
  standalone workspace first so the backup can remain self-contained.
- Installers and docs detect and steer away from redirected locations (PR-22).

## Placeholders

`.gitkeep` files exist only to keep empty folders present in this repository
and in zip-shaped payload distributions; they are dotfiles, so file explorers
hide them from users by default. The deploy step may strip them once folders
contain real content.

## Open questions (tracked in design brief §14)

- Keep `System/` visible by default and ship no editor workspace setting that
  hides it. In the PR-07 files-only dogfood, two headless AI apps found the
  profile, active policy, and procedures with `System/` visible and showed no
  confusion. Headless runs could not test visual editor clutter or prove that
  editor hiding preserves assistant access, so any future optional UI-only
  hiding treatment needs separate evidence.
