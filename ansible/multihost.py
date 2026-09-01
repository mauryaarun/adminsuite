"""
Multi-host SSH command executor.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from admin_suite.ssh.client import ssh_kwargs
from admin_suite.ssh.credentials import SshCredentials, profile_creds
from admin_suite.ssh.hostkeys import create_ssh_client


class MultiHostExecThread(QThread):
    """
    Execute one command on multiple SSH profiles sequentially.
    """

    result_ready = pyqtSignal(str, str, bool)
    all_done = pyqtSignal()

    def __init__(
        self,
        hosts: list[dict[str, Any]],
        command: str,
        timeout: int = 30,
    ):
        super().__init__()

        self.hosts = hosts
        self.command = command
        self.timeout = timeout

    def run(self) -> None:
        for host_data in self.hosts:
            name = host_data.get("name", "unknown")

            try:
                host = (
                    host_data.get("ssh_host")
                    or host_data.get("host")
                    or ""
                )

                port = (
                    host_data.get("ssh_port")
                    or host_data.get("port")
                    or 22
                )

                user = (
                    host_data.get("ssh_user")
                    or host_data.get("user")
                    or ""
                )

                use_agent = bool(host_data.get("use_agent", False))

                strict = bool(host_data.get("strict_host_keys", False))

                creds = host_data.get("creds")

                if creds is None or not isinstance(creds, SshCredentials):
                    creds = profile_creds(host_data)

                client = create_ssh_client(strict=strict)

                kw = ssh_kwargs(
                    host,
                    port,
                    user,
                    creds,
                    use_agent=use_agent,
                )

                kw["timeout"] = 10

                client.connect(**kw)

                stdin, stdout, stderr = client.exec_command(
                    self.command,
                    timeout=self.timeout,
                )

                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")

                rc = stdout.channel.recv_exit_status()

                client.close()

                self.result_ready.emit(name, out + err, rc == 0)

            except Exception as e:
                self.result_ready.emit(name, f"[ERROR] {e}", False)

        self.all_done.emit()
