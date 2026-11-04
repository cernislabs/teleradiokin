"""Study storage abstraction.

Studies are stored outside the database. The `StudyStorage` protocol defines the
contract; `LocalFilesystemStorage` implements it against the local filesystem.
A future S3-compatible adapter implements the same protocol with no change to
callers (services depend on the protocol, not the implementation).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO, Protocol


class StudyStorage(Protocol):
    """Contract for persisting and retrieving study binary objects."""

    def save(self, relative_path: str, data: BinaryIO) -> str: ...

    def append_bytes(self, relative_path: str, data: bytes) -> int: ...

    def move(self, src_relative_path: str, dst_relative_path: str) -> str: ...

    def open(self, relative_path: str) -> BinaryIO: ...

    def exists(self, relative_path: str) -> bool: ...

    def size(self, relative_path: str) -> int: ...

    def delete(self, relative_path: str) -> None: ...

    def full_path(self, relative_path: str) -> str: ...


class LocalFilesystemStorage:
    """Filesystem-backed implementation rooted at a configured directory."""

    def __init__(self, root_path: str) -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, relative_path: str) -> Path:
        # Prevent path traversal outside the storage root. `is_relative_to` is an
        # exact ancestor check (unlike a string prefix, which would treat a
        # sibling like `<root>-evil` as inside the root).
        root = self._root.resolve()
        target = (self._root / relative_path).resolve()
        if target != root and not target.is_relative_to(root):
            raise ValueError("Resolved path escapes the storage root.")
        return target

    def save(self, relative_path: str, data: BinaryIO) -> str:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            shutil.copyfileobj(data, fh)
        return relative_path

    def append_bytes(self, relative_path: str, data: bytes) -> int:
        target = self._resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as fh:
            fh.write(data)
        return target.stat().st_size

    def move(self, src_relative_path: str, dst_relative_path: str) -> str:
        """Move an object to a new key. Uses a same-filesystem rename when
        possible (no second IO pass over large study files), else copies."""
        src = self._resolve(src_relative_path)
        dst = self._resolve(dst_relative_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError:
            # Cross-device or other failure: fall back to a streamed copy.
            with src.open("rb") as rf, dst.open("wb") as wf:
                shutil.copyfileobj(rf, wf)
            src.unlink(missing_ok=True)
        return dst_relative_path

    def open(self, relative_path: str) -> BinaryIO:
        return self._resolve(relative_path).open("rb")

    def exists(self, relative_path: str) -> bool:
        return self._resolve(relative_path).exists()

    def size(self, relative_path: str) -> int:
        return self._resolve(relative_path).stat().st_size

    def delete(self, relative_path: str) -> None:
        target = self._resolve(relative_path)
        if target.exists():
            target.unlink()

    def full_path(self, relative_path: str) -> str:
        return str(self._resolve(relative_path))
