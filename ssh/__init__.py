"""
SSH subsystem.
"""

from admin_suite.ssh.credentials import (
    SshCredentials,
    profile_creds,
    profile_creds_tuple,
)

from admin_suite.ssh.client import (
    ssh_kwargs,
)

from admin_suite.ssh.hostkeys import (
    TrustOnceHostKeyPolicy,
    AdminSSHClient,
    create_ssh_client,
)

__all__ = [
    "SshCredentials",
    "profile_creds",
    "profile_creds_tuple",
    "ssh_kwargs",
    "TrustOnceHostKeyPolicy",
    "AdminSSHClient",
    "create_ssh_client",
]
