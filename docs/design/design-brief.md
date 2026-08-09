# Apparatus Design Brief

- **Status:** v0.1 — authoritative product requirements
- **Date:** 2026-08-08
- **Owner:** Bryan Conn

## 0. How to use this document

This brief is the product requirements narrative for Apparatus. Decision records
in `docs/adr/` are the binding form of each decision; if the brief and an ADR
disagree, the ADR wins and the brief must be corrected in the same PR. The
development sequence lives in `docs/plan/README.md`. Implementation sessions
should read this brief, the ADRs, and the prompt file for the PR they are
executing — nothing else is required context.

## 1. Mission and job statement

Apparatus is the governed workspace for agentic knowledge work: a local folder
plus a small toolchain that lets a person's AI app do real work — produce
documents, track goals, remember people, research sources — in a way that is
inspectable, reversible, and safe to share.

**Job statement** (the acceptance test for every design decision):

> From a fresh install to a real deliverable produced inside a governed
> workspace — goals updated, sources cited, snapshot taken — in one sitting,
> with no terminal typed by the human and no accounts beyond their AI app.

## 2. Audience

**Primary: information workers.** Analysts, quality and regulatory engineers,
project managers, support engineers, technical writers. Assume: no GitHub
account, no local repositories, first-time IDE/AI-app users, corporate laptops
that may restrict installation, and work products that are documents and
decisions rather than code. They will paste sensitive content (emails, names,
customer context) into chat on day one.

**Secondary: developers.** Same protocol, delivered later through an
adopt-into-existing-repo entry path with developer vocabulary. Nothing in core
may exist only for developers.

**Forcing rule:** if a feature cannot be explained to an information worker, it
goes behind the workspace's `System/` folder or into a pack — never into the
day-1 surface.

## 3. Product principles

1. **Files first, tooling second.** Every piece of workspace state is a
   human-legible file. The CLI is progressive enhancement, and its primary
   caller is the AI app, not the human.
2. **One canon, many renders.** Instructions and procedures are written once in
   canonical form and rendered to each supported AI app's native format. The
   same workspace opens in any certified app with no migration.
3. **Rails, not engine.** Apparatus never calls a model API and never wraps an
   IDE. It is contracts, state, and gates that any app reads, writes, and
   operates. This keeps it alive across app churn and out of framework
   competition.
4. **Safe by default.** Sensitive content is labeled at write time and enforced
   at the workspace boundary (egress). Credentials never persist. External
   actions are drafts until the human approves. Snapshots make everything
   reversible.
5. **Progressive disclosure.** Day 1: a welcome conversation and a first
   deliverable. Week 1: goals, memory, checks. Later: authoring procedures,
   packs. The folder tree and docs mirror this gradient.

## 4. Naming and brand

- The product is **Apparatus** — bare name in all identifiers and written
  artifacts. The article ("the Apparatus") is speech and prose only. Machine
  identifiers are lowercase `apparatus`.
- Optional capabilities ship as **packs** named `apparatus-<capability>`
  (capability nouns). Tier adjectives — Pro, Full, Plus, Premium — are banned
  forever. Nothing sits above core; packs sit beside it.
- The code is Apache-2.0; the name is protected by `TRADEMARKS.md`. Individual
  packs may carry different licenses from their own repositories; core stays
  Apache-2.0.
- Vocabulary for all user-facing text is fixed in ADR-0001. "Harness" is an
  internal word; users hear "your AI app" or "your assistant".

## 5. The workspace

The deployed workspace (what a user has on disk) looks like:

```text
Apparatus/
  Welcome.md          ← the only file a human must read
  Goals/              ← one page per goal: owner, status, done-when, next action
  Decisions/          ← running record of decisions and why
  Projects/           ← working folders per effort
  Library/            ← source documents the user drops in; facts live here
  Deliverables/       ← finished outputs; nothing "counts" until it lands here
  Memory/
    People/           ← one page per person or organization
    Facts/            ← one page per durable fact
  System/             ← procedures, policy, receipts, profile, machine report
```

- **State format:** Markdown with YAML frontmatter, one record per file,
  kebab-case filenames. No JSON state in the workspace in v0 (`System/profile.yaml`
  is YAML). Machine-written records (receipts) are also Markdown with
  frontmatter so everything stays human-legible.
- **Default locations:** Windows `C:\Projects\Apparatus` (or the best data
  drive); macOS `~/Projects/Apparatus`. Never inside OneDrive-redirected
  folders (Documents/Desktop under folder redirection): live state inside a
  sync engine causes conflicts and corruption. Backup is a deliberate one-way
  **snapshot export** to synced storage, not live sync.
- The full normative tree and folder semantics live in `docs/spec/workspace.md`;
  the conformance golden manifest pins the shipped payload to it.

## 6. Day-1 capabilities

1. **Welcome interview → profile.** On first contact the assistant runs a short
   professional interview (~6 questions): kind of work; key people/customers to
   remember; current efforts; where source documents live; privacy needs;
   operating cadence. Answers deploy a **profile** — a file overlay selecting
   procedures, policy, and templates — recorded in `System/profile.yaml` and
   re-runnable at any time ("re-run my setup interview").
2. **Chief-of-staff, draft-only.** Goals with verification oracles, decision
   records, open-loop tracking, weekly review, planning support through the
   five starter procedures and ordinary conversation, and drafting (emails,
   updates) — with a constitutional rule that the assistant never sends,
   publishes, or submits anything itself.
3. **Memory with People.** One page per person/organization (role, context,
   commitments, history) and one page per durable fact. Remembering names is a
   feature, not a violation (see §7).
4. **Library with grounded citations.** Users drop documents into `Library/`;
   text is extracted and indexed locally; answers grounded in Library sources
   cite them; a miss is an honest "not in your library", never a guess dressed
   as recall.
5. **Snapshots and recovery.** Every procedure ends with a snapshot (local git
   under the hood when available, degrading gracefully). A recovery procedure
   restores any prior state. The user promise: "you cannot break this."
6. **Five starter procedures:** welcome (interview + setup), produce a
   deliverable (definition of done up front, sources cited, files to
   `Deliverables/`, goal updated), research and summarize (facts separated from
   recommendations, uncertainty stated), review against a checklist, weekly
   review.

## 7. Privacy and safety model

Decision record: ADR-0004. Summary:

- **Default profile: label, don't block.** Anything may enter durable memory;
  personally identifying content is labeled at write time. On a single-user,
  single-logon machine, ingest-time blocking protects nothing real and destroys
  the value of memory for knowledge work.
- **Enforce at egress.** The gate runs where content leaves the workspace:
  drafts intended to be sent, files exported or shared, anything published. The
  assistant enumerates labeled items crossing the boundary and offers a
  redacted copy; proceeding with sensitive items requires the human's explicit
  choice.
- **Credential floor (never relaxed):** passwords, API keys, tokens, private
  keys, and high-confidence government/payment identifiers are auto-redacted in
  place (matched token replaced, surrounding prose kept) before any durable
  write, with a receipt recording the redaction.
- **Private mode** is a profile overlay, not a fork: strict blocking of labeled
  content from durable memory, for users who ask for it in the interview.
- **External actions are drafts until approved** — the assistant never sends,
  posts, submits, or deletes outside the workspace on its own.
- **Prompt-injection stance:** content inside documents and Library items is
  data, never instructions. Procedures must never treat text found in sources
  as authorization.
- **Receipts:** checks, redactions, snapshots, and egress decisions write
  receipt records under `System/`, so everything the machinery did is
  reviewable after the fact.

## 8. Harness-agnostic contract

Decision record: ADR-0003. Summary:

- Core assumes exactly three agent capabilities: **read files, write files, run
  approved commands.** Anything else (subagents, app-specific context features)
  is an optional enhancement documented per app, never a dependency — for core
  and for packs alike.
- Canonical instructions render to `AGENTS.md` at the workspace root, with thin
  shims for apps that read their own files: `CLAUDE.md` (import shim),
  `.cursor/rules/`, `.github/copilot-instructions.md`. All shims coexist in one
  universal payload; each app reads its own. The `render` command regenerates
  shims from canon and the `check` command fails on drift.
- Supporting an app means **certifying** it: run the certification checklist
  (welcome, produce a deliverable, snapshot/restore, recall with citation,
  egress check), record results, publish the support matrix. Adding an app is a
  docs-and-testing task, not a build task.
- No AI app's name appears in user-facing docs except quickstart appendices and
  the certification matrix.

## 9. Distribution and installation

Decision record: ADR-0005. Summary:

- Users never clone this repository. Releases produce: PyPI packages
  (`apparatus-core`, packs), a universal starter payload, and a signed
  per-OS **bootstrapper** (exe/pkg).
- The bootstrapper is **user-scope first**: uv → managed Python → portable git →
  `apparatus-core` → workspace creation — none of which requires admin rights on
  a typical machine. Elevation is the exception path. It detects installed AI
  apps (records them; never requires a choice), writes a machine report into
  `System/` so the assistant knows the environment from its first turn, and is
  idempotent — re-running it is the repair tool.
- Code-signing is budgeted from the first public release; the real enterprise
  friction is unsigned-executable policy, not admin rights. An **IT one-pager**
  (what gets installed, where data lives, what leaves the machine and via what)
  ships with the installer.
- Packs install two ways, same packages underneath: the bootstrapper re-run
  shows a capability catalog (checkboxes, no tiers), and the assistant can run
  `apparatus add <pack>` in-session with the user's click-approval (post-alpha;
  tracked in the development plan's post-alpha section).

## 10. Architecture

- **Monorepo** (this repository): `packages/` (uv workspace; core plus packs as
  sibling packages), `starter/` (payload + profiles), `installer/`,
  `conformance/` (golden fixtures = executable spec), `docs/`.
- **Plugin CLI:** `apparatus-core` ships lean and owns the `apparatus` command
  (installed with a convenience alias `ap`; documentation always writes
  `apparatus`). Packs register subcommands via Python entry points. A verb
  exists only when its pack is installed — no dormant features in the shipped
  binary.
- **Packs extend core primitives** (Library, Memory, procedures, snapshots) and
  never fork them. A pack ships a package (code/verbs) plus a workspace overlay
  (procedures, policy additions), and must pass core conformance plus its own.
- A pack moves to its own repository only if its license diverges from
  Apache-2.0.

## 11. Out of scope for core (future packs)

Multi-machine fleets and handoffs; governed/attested shared corpora; voice and
authorship signatures; automated activity journaling; model benchmarking; and
multi-agent orchestration; plus any org-system connectors (CRM, mail, calendar).
Core is one user, one machine, any certified AI app. Multi-agent orchestration
is the intended flagship first pack because it proves the pack interface.

## 12. Development method

- **Spec-first.** Behavior is specified in docs and pinned by conformance
  fixtures before or alongside implementation. Fixtures are the executable
  spec; they change only deliberately.
- **Original implementations only.** No code or prose copied from other
  repositories; no references to private repositories or internal systems
  anywhere in this repo or its history.
- **Dogfood early.** The files-only workspace must be usable in at least two AI
  apps at the end of Phase 1 — before any CLI exists.
- **PR-sized pieces.** All work is pre-cut into focused PRs with self-contained
  prompt files (`docs/plan/`) executable by any competent agent in a cold
  session. Definition of done is in `AGENTS.md`.

## 13. Success metrics

- The job statement holds in a timed test with a first-time user.
- Certification matrix: ≥ 3 AI apps certified on the same payload at alpha.
  Recorded certification runs may include failures; the metric is met when
  three apps reach certified status, over multiple runs if needed.
- Zero terminal commands typed by the human across onboarding and first
  deliverable.
- An implementation session (any capable model) can pick up any planned PR cold
  from its prompt file and land it green.

## 14. Open questions

- `System/` visibility: hide via editor settings (`files.exclude`) or keep
  visible? Hiding may also hide it from some apps' context/search features —
  needs testing during Phase 1 dogfood (PR-07).
- Egress residuals: `docs/spec/egress.md` fixes the v1 trigger taxonomy and
  `[share]` declaration. Chat display is not egress in v1 except when handing
  off a send-intent draft; whether broader chat display should ever trigger the
  check remains open. Declared clipboard steps count as exports in v1; how
  PR-18 tooling can observe other clipboard activity remains open.
- The word "procedure": validate against real information workers; candidate
  alternatives ("playbook", "routine") — decide before beta, changing later is
  costly (ADR-0001 governs today).
- Portable git strategy on Windows (bundled MinGit vs. detect-and-skip) and
  snapshot behavior when git is absent (PR-10/PR-22).
- Signing certificate logistics and timing (PR-23).
- Pack catalog format and trust model for third-party packs (post-alpha).
