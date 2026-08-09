# Apparatus — Agent Instructions

This is the Apparatus monorepo: the core package, the universal starter payload,
conformance fixtures, and the design and planning documents. This file is the
canonical instruction set; `CLAUDE.md` and any other app-specific instruction
files are shims that point here — the same pattern Apparatus ships to its users.

## Session start — read in this order

1. `README.md` — what Apparatus is; the job statement.
2. `docs/design/design-brief.md` — product requirements. Authoritative for all
   product decisions, second only to the ADRs.
3. `docs/adr/` — accepted decision records (vocabulary, protocol, harness
   contract, privacy, distribution). If the brief and an ADR conflict, the ADR
   wins; fix the brief in the same PR.
4. `docs/plan/README.md` — the phased development plan and current status.
5. The prompt file for the PR you are executing (`docs/plan/PR-XX-*.md`).

## Picking up work

- Work is pre-cut into focused PRs. Execute exactly one PR per branch, named
  `pr-XX-short-slug`.
- Prompt files are self-contained. If a required detail is missing, check the
  design brief and ADRs before deciding anything. If it is genuinely undecided,
  choose the smallest reversible default and record the question under "Open
  questions" in the design brief — do not invent product scope.

## Hard rules

- `uv run pytest` green before declaring done. Conformance fixtures change only
  deliberately, never loosened to make a failure pass.
- Vocabulary per ADR-0001 in all user- and product-facing text. "Harness" is an
  internal word only; user-facing text says "AI app" or "assistant".
- Harness-agnostic per ADR-0003: core and starter content may assume only the
  minimum agent capabilities — read files, write files, run approved commands.
- Original implementations only. Never copy code or prose from other
  repositories, and never reference private repositories, employers, or internal
  systems in any file or commit message.
- No secrets, tokens, personal data, or machine-specific absolute paths in the
  repository.
- Commits: imperative subject ≤ 72 chars, `PR-XX:` prefix for planned work, DCO
  sign-off trailer.

## Definition of done for any PR

1. Deliverables exist at the paths the prompt file specifies.
2. Acceptance criteria verified — state how in the PR description.
3. `uv run pytest` green.
4. Status table in `docs/plan/README.md` updated.
5. Focused diff; nothing outside the PR's scope.
