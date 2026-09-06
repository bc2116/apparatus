---
schema: apparatus/procedure@v0
title: Set up the workspace
intent: Use when the workspace is new or the user asks to run the setup interview again.
---
1. Read `System/profile.yaml` and the existing records in `Goals/` and
   `Memory/People/`. Tell the user that setup can add to what is already there
   without discarding their work.
2. Ask these seven plain-language questions, one at a time, and let the user
   skip any question:
   - What kinds of work do you want help with?
   - Which people, customers, or organizations should this workspace remember,
     and what is each one's role?
   - What are you working on now, what would done look like, and what is the
     next action for each effort?
   - Where do your source documents live, and which of them are already in
     `Library/`?
   - Should privacy mode be `standard`, which can remember labeled personal
     details, or `private`, which does not keep those details in durable
     Memory?
   - Which lowercase weekday should be the weekly review day?
   - Which spend level should guide your assistant: `frugal`, `balanced`, or
     `thorough`?
   After the interview questions, offer these setup choices in this order. For
   each, state the current valid value as the default and say: "you can change
   this any time by asking me." If there is no valid current value, use the
   product fallback shown below. Ask only for a change the user wants;
   otherwise retain the current value:
   - `library_indexing` (default `true`): lets the assistant extract, index,
     and recall sources in `Library/`.
   - `snapshots` (default `true`): saves workspace snapshots so the user can
     return to an earlier version.
   - `ignore_rules` (default `true`): applies `System/ignore` to Library
     machinery; built-in OS-noise defaults always stay active.
   - Privacy mode (default `standard`): `standard` labels personal details;
     `private` does not keep them in durable Memory.
   - Spend level (default `balanced`): chooses how much model capability and
     cost the assistant applies.
3. Summarize the answers in plain language and ask the user to correct or
   confirm them before writing files. For any skipped question, retain the
   current valid value from `System/profile.yaml`; if it is missing or invalid,
   ask the user instead of inventing a replacement.
4. Prepare the complete configured profile as YAML in memory, never as a
   durable temporary file and never in command arguments. Keep
   `schema: apparatus/profile@v0`, set `status: configured`, write `key_people`
   as `{name, role, organization}` entries, `current_efforts` as
   `{title, done_when, next_action}` entries, `source_locations` as plain
   language strings, and `features` with all three named selections. Keep the
   current valid value of any skipped answer.
5. From the workspace, provide that YAML to `apparatus profile apply --stdin`
   through standard input. This applies the credential floor before the
   answers reach durable files, deploys the selected profile overlay, and adds
   only missing People and Goals records. It never replaces, renames, or
   deletes existing user records.
6. Run `apparatus check` and explain any result plainly. Confirm the new
   records and remind the user that they can say "re-run my setup interview"
   whenever their setup changes.
7. Prepare any requested email, update, or submission in `Projects/`.
   Perform actual external actions only with the user's authority and the AI
   app's native permissions; no second Apparatus approval is needed.
8. Take a snapshot using the workspace's snapshot command if it is available
   and approved. If snapshots are unavailable, tell the user plainly and
   continue.
9. Confirm that the snapshot command wrote its schema-valid snapshot receipt
    under `System/receipts/`. If snapshots are unavailable, confirm that the
    workspace records that unavailable state instead.
