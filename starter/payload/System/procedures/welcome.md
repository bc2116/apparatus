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
3. Summarize the answers in plain language and ask the user to correct or
   confirm them before writing files. For any skipped question, retain the
   current valid value from `System/profile.yaml`; if it is missing or invalid,
   ask the user instead of inventing a replacement.
4. Rewrite `System/profile.yaml` with `schema: apparatus/profile@v0`,
   `status: configured`, and the confirmed interview answers. Write
   `key_people` as `{name, role, organization}` entries, `current_efforts` as
   `{title, done_when, next_action}` entries, and `source_locations` as plain
   language strings. Keep the current valid value of any skipped answer.
5. Run `apparatus profile apply` from the workspace. It deploys the selected
   profile overlay and adds only missing People and Goals records; it never
   replaces, renames, or deletes existing user records.
6. Run `apparatus check` and explain any result plainly. Confirm the new
   records and remind the user that they can say "re-run my setup interview"
   whenever their setup changes.
7. Before the next `[share]` step, name the
   intended recipient, path, or service as `TARGET` and run
   `apparatus egress check WORKSPACE DRAFT-FILE --destination TARGET` with the
   explicit workspace path and draft file; omit `--destination` only when the
   destination is genuinely unknown. Do not pass `--decision` on this initial
   inspection. Show the user every finding, redacted-copy offer, and unavailable
   copy, then ask for exactly one fresh choice: use the redacted copy, send the
   original, or stop. Rerun the same check with the same destination and
   `--decision use-redacted`, `--decision send-original`, or `--decision stop`
   only after that choice. Proceed to sharing only when the decision-bearing
   check exits successfully and records pre-share authorization. A stop or
   refusal means do not share. After a credential refusal, ask again; only a
   new explicit `use-redacted` choice and fresh successful check may proceed.
8. [share] If there is an email, update, or submission, keep it as a draft in
   `Projects/` and hand it to the user; the assistant never sends, posts, or
   submits anything itself.
