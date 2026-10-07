"""Read-only report commands and explicit module deployment commands."""

import json
import os
import stat
import sys

from .report import MAX_BYTES, validated_report, validate_report
from .summary import summarize_report


def _read_report(path):
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("Input must be a regular file")
        source = os.fdopen(descriptor, "rb")
        descriptor = None  # The file object now owns the descriptor.
        with source:
            return source.read(MAX_BYTES + 1)
    except (OSError, ValueError):
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_summary(text):
    rendered = text + "\n"
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        rendered.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        rendered = rendered.encode(encoding, errors="backslashreplace").decode(encoding)
    sys.stdout.write(rendered)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] not in {"validate", "summary", "status", "install", "repair"}:
        print("Usage: apparatus-mailbox-survey validate REPORT | summary REPORT | status WORKAREA | install WORKAREA | repair WORKAREA", file=sys.stderr)
        return 2
    if args[0] in {"status", "install", "repair"}:
        from .deployment import DeploymentError, operate
        try:
            result = operate(args[1], args[0])
        except DeploymentError as error:
            print(f"module: {error}", file=sys.stderr)
            return error.code
        print(json.dumps(result))
        return 0

    content = _read_report(args[1])
    if content is None:
        print("report: unable to read input", file=sys.stderr)
        return 2
    if args[0] == "validate":
        findings = validate_report(content)
        for finding in findings:
            print(finding, file=sys.stderr)
        if findings:
            return 1
        print("Report is structurally valid; evidence and authority are unverified.")
        return 0

    report, findings = validated_report(content)
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        return 1
    _write_summary(summarize_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
