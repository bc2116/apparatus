# ADR-0007: A first optional module for mailbox surveys

- **Status:** Accepted — implementation is sequenced separately
- **Date:** 2026-10-06
- **Scope:** Narrows ADR-0006's module deferral to one concrete consumer.

## Context

People want help finding useful categories in historical correspondence without
adopting another user's folders, personal relationships or cleanup rules.
A mailbox survey is a concrete optional workflow with a useful first result:
a source-backed category map, examples and honest coverage. It also gives the
module mechanism a real consumer instead of commissioning a general platform.

## Decision

1. **Start with a separate Skill-first module.** Mailbox Survey is optional,
   distributed separately from `apparatus-core` and its seven built-in Skills.
   The first package contains a portable Skill, supporting files, synthetic
   examples and a read-only report validator. Core never imports the module
   merely because it exists in this monorepo.
2. **Use existing access.** The assistant uses an already authorized native
   connector when available, or reads an explicitly supplied sample. The
   module does not acquire credentials, provide a connector, call a model,
   or assume that installation grants access. Only file reading, writing the
   requested deliverable, and approved commands are required for the fallback.
3. **Propose categories; do not change mail.** Offer sensible starting examples
   such as purchases, deliveries and subscriptions, then adapt to evidence.
   Categories may overlap. Existing provider labels, semantic suggestions,
   preservation preferences and possible future actions are different things.
   No survey labels, moves, archives, sends or deletes mail. Reviewing a
   category map does not authorize such actions.
4. **Keep evidence and coverage legible.** Report the chosen source and scope,
   reviewed items, exclusions, unknown counts, supported category examples
   and unresolved items. A model answer does not repair missing evidence.
   Structural validation proves consistency, not source truth, classification
   quality, authority, or complete mailbox coverage.
5. **Honor task retention.** A no-save task can produce its requested report.
   It cannot automatically retain source bodies, Memory, Library cards,
   preferences or learned Skills. Source text is data, never instructions.
   Task controls do not change the AI app's own retention behavior.
6. **Separate package presence from work-area deployment.** A Python package
   can be installed while its Skill has not been deployed or discovered.
   Inventory must eventually include modules with no command entry point.
   A later lifecycle must preserve edited/foreign files, bind updates to
   exact owned preimages, and report partial installation and recovery limits.
   A distributable module cannot impersonate a learned Skill to acquire its
   ownership or snapshot coverage.
7. **Keep the first implementation bounded.** PR-63 adds the portable prototype
   and report contract. It adds no workspace ownership record, installation
   command, native discovery adapter or recovery claim. Later lifecycle and
   packaging integration require their own implementation prompts and deliberate
   schema/fixture changes. No catalog, marketplace, arbitrary download loader,
   billing tier, scheduler or general model router is commissioned.
8. **Qualify optional engines separately.** A future assessment engine can
   implement a stable evidence/report boundary without changing the user flow.
   Domain policy and thresholds must be configurable and versioned. Provider
   identity, coverage and quality need independent evidence before claims of
   readiness. The initial prototype has no provider dependency or action path.

## Compatibility and consequences

This decision preserves ADR-0006's files-first, single-user, native-connector,
task-retention and ordinary-file fallback boundaries. It replaces only the
blanket scheduling deferral for this concrete module and the minimum lifecycle
it demonstrates a need for. Other later modules remain deferred.

The YAML report is a requested project deliverable, not a managed workspace
record or new core record kind. Core snapshots exclude it as project work.
Module source resources likewise gain no recovery coverage by having a portable
Skill format. General module-owned state requires an explicit later contract.

The ordinary core release can ship independently. A built wheel, green tests
or a successful supplied-sample exercise does not establish native connector
coverage, automatic Skill invocation, or quality across real mailboxes.
