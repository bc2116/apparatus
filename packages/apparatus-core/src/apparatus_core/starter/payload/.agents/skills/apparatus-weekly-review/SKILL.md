---
name: apparatus-weekly-review
description: Use only when the user requests a review of the week or a plan for the next one.
---
1. Run this Skill only when requested. A stored `review_day` does not trigger
   work or establish a schedule. Use the requested period, or state a reasonable
   seven-day period; ask only if the dates materially affect the request.
2. Read relevant Goals and current Memory, including decisions and legacy
   Decisions records. Follow `AGENTS.md` lifecycle rules: do not recall outdated
   or forgotten content as current or recreate forgotten records. Summarize
   status, verifiable `done-when` and next actions from actual evidence.
3. Surface stalled goals, unmet dependencies, missing next actions and
   contradictions. Distinguish unavailable coverage from no activity. Ask about
   events outside the files only when necessary for the requested review;
   never infer undocumented progress.
4. Propose priorities grounded in the request, active goals and open loops.
   Save a requested plan in its project. Make authorized updates when the task
   permits retention, marking goals done only with verifiable evidence. Do not
   turn recommendations into unrequested commitments or external actions.
5. For a no-save task, provide the review and save its requested deliverable
   without persisting Memory, goal updates, activity notes, learned Skills or
   Library cards. Skip routine Library offers and automatic snapshots.
6. At a meaningful completion boundary, follow the snapshot feature and task
   decision. Use `apparatus --task ID snapshot WORKSPACE` when available and
   automatic saves are permitted. The command owns its receipt; do not create
   a second snapshot receipt. Explain unavailable recovery and continue.
   Managed-state snapshots exclude project files and Library originals.
7. Actual external actions require the user's authority and the AI app's native
   permissions; no second Apparatus approval is needed.
