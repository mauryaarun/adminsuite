"""
SSH host-key handling.
"""

from __future__ import annotations

import os
from pathlib import Path

import paramiko

from admin_suite.core.paths import HOST_KEYS_FILE


class TrustOnceHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """
    Trust a host key on first use, but save it.

    Later host-key changes will raise Paramiko BadHostKeyException.
    """

    def __init__(self, host_keys_file: str | Path = HOST_KEYS_FILE):
        self.host_keys_file = str(host_keys_file)

    def missing_host_key(self, client, hostname, key) -> None:
        try:
            client.get_host_keys().add(hostname, key.get_name(), key)

            parent = os.path.dirname(self.host_keys_file)

            if parent:
                os.makedirs(parent, exist_ok=True)

            client.save_host_keys(self.host_keys_file)

            try:
                os.chmod(self.host_keys_file, 0o600)
            except Exception:
                pass

        except Exception:
            # Host-key persistence failure should not necessarily abort login,
            # but it will reduce trust persistence.
            pass


class AdminSSHClient(paramiko.SSHClient):
    """
    Hardened SSH client.

    - loads system known_hosts
    - loads Admin Suite known_hosts
    - supports strict mode
    - downgrades AutoAddPolicy to trust-on-first-use with saved keys
    """

    def __init__(
        self,
        strict: bool = False,
        host_keys_file: str | Path = HOST_KEYS_FILE,
    ):
        super().__init__()

        self.host_keys_file = str(host_keys_file)

        try:
            self.load_system_host_keys()
        except Exception:
            pass

        try:
            if os.path.exists(self.host_keys_file):
                self.load_host_keys(self.host_keys_file)
        except Exception:
            pass

        if strict:
            super().set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            super().set_missing_host_key_policy(
                TrustOnceHostKeyPolicy(self.host_keys_file)
            )

    def set_missing_host_key_policy(self, policy) -> None:
        """
        Existing code often sets AutoAddPolicy.

        We downgrade AutoAddPolicy to TrustOnceHostKeyPolicy.
        """
        if isinstance(policy, paramiko.AutoAddPolicy):
            policy = TrustOnceHostKeyPolicy(self.host_keys_file)

        super().set_missing_host_key_policy(policy)


def create_ssh_client(
    strict: bool = False,
    host_keys_file: str | Path = HOST_KEYS_FILE,
) -> AdminSSHClient:
    """
    Create AdminSSHClient.
    """
    return AdminSSHClient(
        strict=strict,
        host_keys_file=host_keys_file,
    )
