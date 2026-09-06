"""Explicit project links; binding changes only the control and owned pointer."""

from __future__ import annotations

import json
from contextlib import nullcontext

from apparatus_core.project_binding import BindingError, bind_project, resolve_project_context


def register(subparsers):
    parser = subparsers.add_parser("project", help="link a project to its work area")
    actions = parser.add_subparsers(dest="project_action", required=True)
    bind = actions.add_parser("bind", help="set up a portable work-area link")
    bind.add_argument("project", metavar="PROJECT")
    bind.add_argument("--workspace", required=True, metavar="WORKAREA")
    bind.add_argument("--replace", action="store_true", help="explicitly retarget an existing valid link")
    bind.set_defaults(func=run)
    show = actions.add_parser("show", help="show this project's selected work area")
    show.add_argument("project", metavar="PROJECT")
    show.set_defaults(func=run)


def run(args):
    try:
        if args.project_action == "bind":
            result = bind_project(args.project, args.workspace, replace=args.replace)
            print("Project linked to its work area." if result.changed else "Project link is already current.")
        else:
            selected = getattr(args, "_project_context", None)
            with (nullcontext(selected) if selected is not None else resolve_project_context(args.project)) as context:
                context.validate()
                print(json.dumps({"workspace": str(context.workspace), "workspace_id": context.workspace_id}))
        return 0
    except (BindingError, OSError) as error:
        print(f"project: {error}")
        return 2
