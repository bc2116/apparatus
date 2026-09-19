# Synthetic native-discovery inputs

`workarea/` is the common source seed. Each native case receives a separately
initialized copy. The sole canonical witness body is under the work-area
`.agents/skills/` tree; no project fixture duplicates that body.

`project-bound/` is copied beneath its case work area, initialized as its own
Git repository, then linked through `apparatus project bind`. It supplies custom
project instructions, a source, a sentinel, and one user-owned custom Skill.

`project-collision/` is likewise initialized as its own repository and
independently bound. Its second user-owned Skill has the same display name as
the work-area witness but different bytes. It is an ownership-preservation
control, never a candidate for replacement.

The root named, bound relevance, collision, and non-relevant cases use separate
temporary copies and fresh chats. The committed prompt files provide the exact
submitted wording apart from their documented runtime placeholders.
