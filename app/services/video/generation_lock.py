"""OS-held execution ownership for local video jobs, including across processes.

Lock files remain on disk deliberately: unlinking them would allow two owners to
lock different inodes. Process termination releases the lock, not the filename.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import BinaryIO

from ..storage import validate_id


class GenerationLock:
    def __init__(self, stream: BinaryIO) -> None:
        self.stream = stream

    @classmethod
    def acquire(cls, directory: Path, job_id: str) -> GenerationLock | None:
        directory.mkdir(parents=True, exist_ok=True)
        stream = (directory / f"{validate_id(job_id)}.lock").open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            if exc.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                return None
            raise
        return cls(stream)

    def close(self) -> None:
        if self.stream.closed:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
