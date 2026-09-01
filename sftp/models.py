"""
SFTP task models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SftpAction(str, Enum):
    """
    SFTP operation type.
    """

    LIST = "list"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    READ = "read"
    WRITE = "write"
    MKDIR = "mkdir"
    CHMOD = "chmod"
    DELETE = "delete"
    RENAME = "rename"
    STAT = "stat"


@dataclass
class SftpTask:
    """
    Describes one SFTP operation.

    Important design change:
    - remote editor writes must use `content`
    - `local_path` must remain a real local filesystem path
    """

    action: SftpAction = SftpAction.LIST

    # Current remote directory for LIST and refresh operations.
    path: str = "/"

    # Local filesystem path for upload/download.
    local_path: str = ""

    # Remote filesystem path.
    remote_path: str = ""

    # Explicit text content for WRITE operations.
    content: str | None = None

    # Permission mode for chmod.
    mode: int = 0

    # Recursive directory transfer.
    recursive: bool = False
