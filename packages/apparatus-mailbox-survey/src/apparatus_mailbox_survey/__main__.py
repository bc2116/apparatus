"""Read-only report validation command."""

import os
import stat
import sys

from .report import MAX_BYTES, validate_report


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "validate":
        print("Usage: apparatus-mailbox-survey validate PATH", file=sys.stderr)
        return 2
    descriptor = None
    try:
        descriptor = os.open(args[1], os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("Input must be a regular file")
        source = os.fdopen(descriptor, "rb")
        descriptor = None  # The file object now owns the descriptor.
        with source:
            content = source.read(MAX_BYTES + 1)
    except (OSError, ValueError):
        print("report: unable to read input", file=sys.stderr)
        return 2
    finally:
        if descriptor is not None:
            os.close(descriptor)
    findings = validate_report(content)
    for finding in findings:
        print(finding, file=sys.stderr)
    if findings:
        return 1
    print("Report is structurally valid; evidence and authority are unverified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
