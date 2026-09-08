# Cursor IDE lean release-candidate observation

This bounded evidence set records two native Cursor IDE 3.19.13 chats on macOS 27 using Grok 4.6 High with Fast Off. The observations below were supplied from native UI review; this repository does not claim an independent tool trace.

## Saving chat

The first chat lasted 2m11s. It produced `project-a/workshop-plan.md` from `source.md`, saved the explicit sourced Memory fact (two sessions with 12 places each), and registered the plan in the default-cache Library with an original registration, extraction, current card, and managed snapshot. The saving task ID was `ac846292-4f16-4b55-adbb-3a61cd022b7c`.

A same-chat verification follow-up lasted 37s. Native UI showed `Used apparatus-produce-deliverable` opening the exact canonical skill at `area/.agents/skills/apparatus-produce-deliverable/SKILL.md`, with its complete body displayed. The follow-up read the plan, source, and sentinel; it made no corrections. The task ID remained the same, and all files were unchanged by the follow-up.

## Fresh no-save chat

The second fresh chat lasted 1m12s. It was a no-save task (`4dadcc3e-a564-44dc-9aae-e8b3509e9d13`), recalled Memory and Library citations, and saved `project-a/facilitator-note.md`. It left the venue undecided and did not state a duration because duration is absent from the evidence. Native UI asserted the no-save outcome. An independent filesystem SHA-256 oracle found all 85 pre-existing files unchanged, with only task metadata and the requested deliverable added.

## Scope and gaps

The prompts are normalized with absolute fixture paths replaced by `<fixture-root>` and `<fixture-runtime>` tokens. The supplied Cursor export contains human messages only and does not include tool traces or the follow-up message. The second typed prompt is included separately from the later-supplied prompt file; no second native transcript export exists.

The fixture confirms the default cache (`cache_override: null`) and the installed CLI path in the prompt points to the explicit synthetic fixture runtime, not a system installer. Exact global native permission settings, provider retention, signing, public release, and full certification claims were not verified and are outside this evidence set. No raw conversation, personal absolute paths, private accounts, or global state are included.

## Final-reply qualification found during closeout

The native second-chat final reply called the source a “45-minute water break.”
The source specifies a break **after** 45 minutes and gives no break length.
The saved facilitator note correctly preserves that distinction. Retention,
Memory/Library recall and saved-output checks passed, but this final-reply
wording makes the overall second-chat result qualified. It is not an
unqualified two-chat compatibility pass.
