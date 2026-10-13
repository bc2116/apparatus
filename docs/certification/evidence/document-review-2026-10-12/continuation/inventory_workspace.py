"""Inventory only a disposable work area, including recovery state.
Directory mtimes are omitted because adding the requested file changes its parent.
File bytes, size, mode and mtime are compared; access times are not retention.
"""
import hashlib, json, stat, sys
from pathlib import Path

def inventory(root):
    entries = {}
    for p in sorted(root.rglob("*")):
        s = p.lstat()
        row = {"mode": stat.S_IMODE(s.st_mode)}
        if p.is_symlink():
            raise ValueError("Symlinks are outside this fixture")
        if p.is_dir():
            row["kind"] = "directory"
        elif p.is_file():
            row.update(kind="file", bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                       sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        else:
            raise ValueError("Unsupported fixture entry")
        entries[p.relative_to(root).as_posix()] = row
    return entries

if __name__ == "__main__":
    Path(sys.argv[2]).write_text(json.dumps(inventory(Path(sys.argv[1])), indent=2)+"\n")
