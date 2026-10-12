"""JSON state files written atomically: a reader, or a crash or kill in the middle of a write, never sees half a file."""
import json
import os
import tempfile
import time
from pathlib import Path


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=1))
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(40):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:          # Windows: someone is reading the old file at this very moment
                if attempt == 39:
                    raise
                time.sleep(0.05)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
