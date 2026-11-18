"""Small, dependency-free helpers shared by the launcher and pipeline."""

import os
import shutil
import sys
from pathlib import Path


def find_opencode():
    # On Windows use the native binary, not a .cmd shim that would require
    # passing vocabulary and prompts through a command shell.
    return shutil.which("opencode.exe" if sys.platform == "win32" else "opencode")


class InstanceLock:
    """An OS lock released on process exit; no stale-PID files or extra packages."""

    def __init__(self, path, windows=None):
        self.path = Path(path)
        self.windows = os.name == "nt" if windows is None else windows
        self.stream = None

    def acquire(self):
        stream = self.path.open("a+b")
        try:
            if self.windows:
                import msvcrt
                if self.path.stat().st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            raise
        self.stream = stream
        return self

    def release(self):
        if self.stream is None:
            return
        try:
            if self.windows:
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            # Closing the file also releases flock on POSIX.
            self.stream.close()
            self.stream = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()
