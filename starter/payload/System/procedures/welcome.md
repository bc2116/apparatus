---
schema: apparatus/procedure@v0
title: Set up the workspace
intent: Use when the workspace is new or the user asks to run the setup interview again.
---
1. Read `System/profile.yaml` and the existing records in `Goals/` and
   `Memory/People/`. Tell the user that setup can add to or update what is
   already there without discarding their work.
2. Ask these six plain-language questions, one at a time, and let the user skip
   any question:
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
3. Summarize the answers in plain language and ask the user to correct or
   confirm them before writing files. If the user skips the work-types,
   privacy-mode, or review-day question, retain that field's current valid value
   from `System/profile.yaml` and include the retained value in the summary. If
   the current value is missing or invalid, ask the user instead of inventing a
   replacement.
4. Rewrite `System/profile.yaml` with exactly the five profile keys: keep
   `schema: apparatus/profile@v0` and set `status: configured`. For
   `privacy_mode`, `work_types`, and `review_day`, write each confirmed new
   answer or copy its current valid value unchanged when that question was
   skipped. Never reset a valid profile choice merely because the interview is
   being run again.
5. For each current effort the user wants tracked, create or update one
   kebab-case record in `Goals/`. Include `schema: apparatus/goal@v0`, a title,
   owner, a verifiable `done-when`, and a concrete `next-action`. Give a newly
   created current effort `status: active`. For an existing goal, preserve its
   current valid status unless the user confirms a change, then record the
   confirmed status accurately; never reset it to `active` merely because the
   interview is being run again. Ask for any required value that the interview
   did not supply.
6. For each person or organization the user explicitly wants remembered,
   create or update one kebab-case record in `Memory/People/` with
   `schema: apparatus/person@v0`, its name, and the role and context the user
   provided. In private mode, do not save labeled personal details; explain
   when that choice prevents a requested people record from being written.
7. Tell the user setup is complete and that they can change it at any time by
   saying "re-run my setup interview." Keep any email, update, or submission
   as a draft in `Projects/` and hand it to the user; the assistant never sends,
   posts, or submits anything itself.
8. Take a snapshot using the workspace's snapshot command if it is available
   and approved. If snapshots are unavailable, tell the user plainly and
   continue.
9. Create `System/receipts/` if it is absent, then write a snapshot receipt
   named `YYYY-MM-DD-HHMMSS-snapshot.md` using the current UTC time. If that
   name exists, append `-2`, `-3`, and so on before `.md`. Include
   `schema: apparatus/receipt@v0`, `event: snapshot`, the UTC `timestamp`, and
   a one-sentence `summary`; in the body, name this procedure, list the files
   changed, and state whether the snapshot was taken or unavailable.
