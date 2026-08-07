"""Cross-process advisory file locking for the JSON-file stores.

The timeline, A2A, and paper-trade stores are plain JSON files written by
four separate processes (server, timeline server, listener, dispatcher).
A `threading.Lock` only serializes writers inside one interpreter, so a
read-modify-write can still lose updates across processes. `file_lock`
closes that gap with an `flock` on a sibling `.lock` file.

Callers must hold the lock across the *whole* read-modify-write, not just
the write, or the race is merely narrowed rather than closed.
"""

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict

# One re-entrant-ish thread lock per store path, so threads inside a single
# process serialize before they ever contend on the OS-level lock.
_THREAD_LOCKS: Dict[str, threading.Lock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def _thread_lock_for(path: Path) -> threading.Lock:
    key = str(path)
    with _THREAD_LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def file_lock(target_path: Path):
    """Serialize access to `target_path` across threads and processes.

    fcntl is Unix-only; on platforms without it the thread lock still
    applies and the cross-process guarantee degrades to best-effort
    (matching the previous behaviour of the paper-trade ledger)."""
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with _thread_lock_for(target_path):
        try:
            import fcntl
        except ImportError:
            yield
            return

        lock_file = target_path.with_suffix(target_path.suffix + ".lock")
        with open(lock_file, "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
