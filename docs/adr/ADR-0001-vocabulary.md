# ADR-0001: Vocabulary and naming

- **Status:** Accepted
- **Date:** 2026-08-08

## Context

Apparatus serves information workers who have never used an IDE, a repo, or a
terminal. Developer vocabulary ("repo", "commit", "validate", "loop") is a
barrier, and inconsistent naming between docs, procedures, and the assistant's
own speech reads as unreliability. The docs' primary reader is the AI app; the
human reads `Welcome.md` and their outputs — but the words the assistant uses
back to the human come from these artifacts, so they must be fixed once, in the
artifacts themselves. Dual naming (internal term + display term) is how drift
starts, so there is exactly one canonical term per concept.

## Decision

Canonical user-facing vocabulary, used in all product artifacts, starter
content, and assistant-facing procedure text:

| Concept | Canonical term | Do not use (user-facing) |
|---|---|---|
| The governed folder | **workspace** | repo, repository, project root |
| A repeatable playbook the assistant follows | **procedure** | loop, workflow, contract, skill |
| A validation run | **check** | validate, lint, test |
| A saved version point | **snapshot** | commit, checkpoint |
| Returning to a snapshot | **restore** | revert, reset, rollback |
| The source-document collection | **Library** | corpus, knowledge base, RAG |
| Finished outputs | **Deliverables** | artifacts, outputs |
| Durable remembered content | **Memory** (with **People** and **Facts**) | vault, database, store |
| The machinery folder | **System** | internals, engine, config |
| The user's AI tool | **AI app** / **assistant** | harness, agent, LLM, model, IDE |
| How much model capability and cost to apply | **spend level**: `frugal` \| `balanced` \| `thorough` | cheap mode, budget, tier adjectives |

Rules:

1. "Harness" and "agent" are internal/engineering words only (this repo's dev
   docs may use them); they never appear in user-facing text.
2. The product name is **Apparatus** — bare, capitalized in prose and display;
   machine identifiers are lowercase `apparatus`. The article ("the Apparatus")
   is speech only and never appears in identifiers.
3. Optional capabilities are **packs**, named `apparatus-<capability>` with
   capability nouns. Tier adjectives (Pro, Full, Plus, Premium, Enterprise) are
   permanently banned in pack and product naming.
4. No AI app's brand name appears in user-facing docs except per-app quickstart
   appendices and the certification matrix.

## Consequences

- Reviews enforce the table; a vocabulary violation is a defect.
- Renamed concepts require updating this ADR first.
- "Procedure" is flagged for validation with real users before beta (see design
  brief §14); until changed here, it is canon.
