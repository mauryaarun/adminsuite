"""
SSH client helpers.
"""

from __future__ import annotations

import os
from typing import Any

from admin_suite.ssh.credentials import SshCredentials


def ssh_kwargs(
    host: str,
    port: Any,
    user: str,
    creds: SshCredentials,
    use_agent: bool = False,
) -> dict[str, Any]:
    """
    Build Paramiko connect kwargs.

    Important:
    - key_path + passphrase is used for SSH key authentication
    - password is used for password authentication
    """
    try:
        port_i = int(port) if port else 22
    except Exception:
        port_i = 22

    kw: dict[str, Any] = {
        "hostname": host,
        "port": port_i,
        "username": user,
        "timeout": 15,
        "banner_timeout": 15,
        "auth_timeout": 15,
        "look_for_keys": False,
        "allow_agent": bool(use_agent),
    }

    key_path = creds.key_path

    if key_path:
        key_path = os.path.expanduser(key_path)

    if key_path and os.path.exists(key_path):
        kw["key_filename"] = key_path

        if creds.passphrase:
            kw["passphrase"] = creds.passphrase

    elif creds.password:
        kw["password"] = creds.password

    return kw
