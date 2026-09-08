# Cursor Luna fresh second conversation — operator observation

Same Cursor 3.19.13 / macOS 27 / GPT-5.6 Luna Medium selection. A new conversation was started in the same project, using prompt-2.txt, with no corrective follow-up. Native UI reported 1 minute 19 seconds. Task 31110f7b-38d2-4fa7-83fa-92740a85f621 used memory: no-save.

Exact relevant final-answer text as exposed by the native accessibility view:

“The practice workshop has two sessions and 12 places per session.”

“Venue is undecided. Total duration is not specified (session lengths and timetable are absent). The only timing detail on record is a water break after 45 minutes; that is not a session length or a total.”

The answer cited Memory/Facts/workshop-format-and-capacity.md and project-a/workshop-plan.md, both tracing to source.md. It reported saving facilitator-note.md, preserving local-note.md, and no Memory writes, Library cards, learned Skills, activity notes or automatic snapshots. It reported no native denials; none were observed by the operator. No complete hidden provider tool trace is claimed.

Independent root verification found the persisted facilitator note accurate, with Memory and Library citations and total duration unknown. after-second.json and second-oracle.json show all 85 pre-existing files byte-identical and exactly two added files: the requested facilitator note and content-free no-save task metadata. The record supports this named two-conversation case; it does not generalize to other Cursor models or native retention behavior.
