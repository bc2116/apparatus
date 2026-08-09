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
filenames. `System/profile.yaml` is plain YAML. Record schemas land in PR-04;
until then the payload ships structure, not records.

## `System/` planned contents

| Path | Arrives | Purpose |
|---|---|---|
| `System/README.md` | now | Explains the machinery folder to a curious human. |
| `System/profile.yaml` | now (unconfigured) | The profile: interview answers, privacy mode, selected procedures. |
| `System/procedures/` | PR-05 | Procedure records the assistant follows. |
| `System/policy/` | PR-06 | Active policy overlay (standard or private mode). |
| `System/receipts/` | PR-09+ | One record per machinery event: checks, redactions, snapshots, egress decisions. |
| `System/machine-report.md` | PR-08 | Environment capabilities, written by `doctor`/the bootstrapper. |
| Workspace instruction canon and shims | PR-07 | `AGENTS.md` canon at workspace root plus app shims (ADR-0003). |

## Placement on disk

- Windows default: `C:\Projects\Apparatus` (or the equivalent on the best data
  drive). macOS default: `~/Projects/Apparatus`.
- Never inside folders redirected into a sync engine (OneDrive Documents/
  Desktop redirection and similar): live state inside file sync causes
  conflicts and corruption. Backup is a deliberate, one-way snapshot export to
  synced storage (PR-25).
- Installers and docs detect and steer away from redirected locations (PR-22).

## Placeholders

`.gitkeep` files exist only to keep empty folders present in this repository
and in zip-shaped payload distributions; they are dotfiles, so file explorers
hide them from users by default. The deploy step may strip them once folders
contain real content.

## Open questions (tracked in design brief §14)

- Whether to hide `System/` via editor workspace settings: hiding reduces
  clutter but may also hide it from some apps' context/search features. Test
  during the PR-07 dogfood and record the outcome here.
