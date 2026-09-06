"""Opaque task controls; task content never enters this command's records."""

from __future__ import annotations

import json

from apparatus_core.retention import TaskRetentionError, context_for, set_no_memory, start_task


def register(subparsers):
    parser = subparsers.add_parser("task", help="control Memory retention for one task")
    actions = parser.add_subparsers(dest="task_action")
    start = actions.add_parser("start", help="start a task and return its opaque ID")
    start.add_argument("workspace", metavar="WORKSPACE")
    choice = start.add_mutually_exclusive_group()
    choice.add_argument("--no-memory", dest="save_memory", action="store_false")
    choice.add_argument("--save-memory", dest="save_memory", action="store_true")
    start.set_defaults(func=run, save_memory=None)
    for action in ("show", "no-memory"):
        command = actions.add_parser(action, help=f"{action} an existing task")
        command.add_argument("workspace", metavar="WORKSPACE")
        command.add_argument("task_id", metavar="ID")
        command.set_defaults(func=run)


def run(args):
    try:
        if args.task_action == "start":
            context = start_task(args.workspace, save_memory=args.save_memory)
        elif args.task_action == "no-memory":
            context = set_no_memory(args.workspace, args.task_id)
        else:
            context = context_for(args.workspace, task_id=args.task_id, require_task=True)
        print(json.dumps({"task_id": context.task_id,
                          "memory": "save" if context.save_memory else "no-save"}))
        return 0
    except TaskRetentionError as error:
        print(f"task: {error}")
        return 2
    except (OSError, ValueError):
        print("task: could not update task controls safely")
        return 2
