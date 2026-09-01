"""
Ansible/multi-host command set storage.
"""

from __future__ import annotations

import copy
from typing import Any

from admin_suite.core.paths import ANSIBLE_COMMAND_SETS_FILE
from admin_suite.core.utils import read_json, write_json_secure

DEFAULT_CMD_SETS: list[dict[str, Any]] = [
    {
        "name": "System Health Check",
        "commands": [
            "uptime",
            "free -h",
            "df -h",
            "cat /proc/loadavg",
        ],
    },
    {
        "name": "Network Diagnostics",
        "commands": [
            "ip addr show",
            "ip route",
            "ss -tunlp | head -20",
            "cat /etc/resolv.conf",
        ],
    },
    {
        "name": "Service Status",
        "commands": [
            "systemctl list-units --state=failed",
            "systemctl list-units --type=service --state=running | head -20",
        ],
    },
    {
        "name": "Security Audit",
        "commands": [
            "last -10",
            "cat /etc/passwd | grep -v nologin | grep -v /bin/false",
            "find /etc -name '*.conf' -newer /etc/passwd -mtime -7 2>/dev/null | head -10",
        ],
    },
    {
        "name": "Disk & Storage",
        "commands": [
            "lsblk",
            "df -hT",
            "mount | grep -E 'ext4|xfs|btrfs'",
        ],
    },
    {
        "name": "Process Management",
        "commands": [
            "ps aux --sort=-%mem | head -15",
            "ps aux --sort=-%cpu | head -15",
        ],
    },
    {
        "name": "Package Updates Check",
        "commands": [
            "apt list --upgradable 2>/dev/null | head -20 || "
            "yum check-update 2>/dev/null | head -20 || "
            "dnf check-update 2>/dev/null | head -20"
        ],
    },
]


def normalize_commands(commands: list[str] | str) -> list[str]:
    """
    Normalize command list input.
    """
    if isinstance(commands, str):
        commands = commands.splitlines()

    out = []

    for command in commands:
        command = str(command).strip()

        if command:
            out.append(command)

    return out


class CommandSetStore:
    """
    Stores predefined multi-host command sets.
    """

    def __init__(self, path=None):
        self.path = path or ANSIBLE_COMMAND_SETS_FILE
        self.sets: list[dict[str, Any]] = self._load()

    def _load(self) -> list[dict[str, Any]]:
        data = read_json(self.path, None)

        if isinstance(data, list) and data:
            return data

        return copy.deepcopy(DEFAULT_CMD_SETS)

    def save(self) -> None:
        write_json_secure(self.path, self.sets)

    def all(self) -> list[dict[str, Any]]:
        return self.sets

    def get(self, index: int) -> dict[str, Any] | None:
        try:
            return self.sets[index]
        except IndexError:
            return None

    def add(self, name: str, commands: list[str] | str) -> None:
        self.sets.append(
            {
                "name": str(name).strip(),
                "commands": normalize_commands(commands),
            }
        )

        self.save()

    def update_commands(
        self,
        index: int,
        commands: list[str] | str,
    ) -> None:
        try:
            self.sets[index]["commands"] = normalize_commands(commands)
            self.save()
        except IndexError:
            pass

    def delete(self, index: int) -> None:
        try:
            self.sets.pop(index)
            self.save()
        except IndexError:
            pass
