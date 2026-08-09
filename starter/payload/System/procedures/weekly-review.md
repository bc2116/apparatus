---
schema: apparatus/procedure@v0
title: Run the weekly review
intent: Use on the chosen review day or whenever the user asks to review the week and plan the next one.
---
1. Confirm the seven-day review period and read every record in `Goals/`.
   Summarize each goal's current status, verifiable `done-when`, and next
   action; do not infer progress that the files do not show.
2. Surface stalled goals and open loops. Flag an active goal with no usable next
   action, a waiting goal with no stated dependency, an overdue action, and any
   mismatch between a goal's status and the evidence in the workspace.
3. Read the week's records in `Decisions/` and the new or changed records in
   `Memory/People/` and `Memory/Facts/`. When a record has no date, use an
   approved command to read its modified time. Summarize what changed, note
   unresolved questions or contradictions, and ask before replacing older
   information.
4. Ask what changed outside the files during the week. Record only what the
   user confirms, updating the relevant goal, decision, person, or fact record
   rather than inventing a new record kind.
5. Propose a short list of priorities for the coming week, grounded in the
   active goals and open loops. Agree the priorities with the user, then update
   affected goal statuses and next actions.
6. Save a weekly plan in the appropriate folder in `Projects/` if the user
   wants one.
7. [share] If there is an email, update, or submission about the plan, keep it
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
