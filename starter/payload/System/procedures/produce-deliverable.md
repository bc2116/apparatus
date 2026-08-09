---
schema: apparatus/procedure@v0
title: Produce a deliverable
intent: Use when the user wants to create a finished file for a defined purpose.
---
1. Ask what the finished work must accomplish, who it is for, which format it
   needs, and how the user will know it is done. Restate that definition of done
   and get the user's agreement before drafting.
2. If the work belongs to a goal, read or create its record in `Goals/` and
   write the agreed definition of done as the goal's verifiable `done-when`
   before drafting. Keep its owner, status, and next action current.
3. Read the relevant files in `Library/` and the effort's folder in `Projects/`.
   Ask the user about missing source material instead of filling gaps with
   unsupported claims.
4. Create the working file under the appropriate kebab-case folder in
   `Projects/`. Keep revisions there while the work is still a draft.
5. Cite every source used from `Library/` by its filename, close to the claim or
   section it supports. Distinguish source-backed facts from assumptions and
   mark unresolved uncertainty plainly.
6. Compare the draft with every part of the agreed definition of done. Show the
   user any unmet part and revise only with the user's direction.
7. [share] Treat an email, update, submission, or other primary content intended to be
   sent as a draft meant to leave the workspace. Keep that requested work
   itself in `Projects/`, hand it to the user, and do not file it in
   `Deliverables/`; the assistant never sends, posts, or submits anything
   itself.
8. If the primary requested work is not intended to be sent, file the finished
   version in `Deliverables/` when the user agrees it is finished.
9. [share] If there is an accompanying email, update, or submission, keep it as
   a draft in `Projects/` and hand it to the user.
10. If there is a related goal, update its record. Set it to `done` only when its
   `done-when` can be checked from the workspace; otherwise keep the accurate
   status and record the next action.
11. Take a snapshot using the workspace's snapshot command if it is available
    and approved. If snapshots are unavailable, tell the user plainly and
    continue.
12. Create `System/receipts/` if it is absent, then write a snapshot receipt
    named `YYYY-MM-DD-HHMMSS-snapshot.md` using the current UTC time. If that
    name exists, append `-2`, `-3`, and so on before `.md`. Include
    `schema: apparatus/receipt@v0`, `event: snapshot`, the UTC `timestamp`, and
    a one-sentence `summary`; in the body, name this procedure, list the files
    changed, and state whether the snapshot was taken or unavailable.
