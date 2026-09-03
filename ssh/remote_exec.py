from __future__ import annotations

import subprocess
from typing import Any, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from admin_suite.ssh.client import ssh_kwargs
from admin_suite.ssh.credentials import SshCredentials, profile_creds
from admin_suite.ssh.hostkeys import create_ssh_client


class RemoteExecThread(QThread):
    """
    Execute one command remotely or locally.
    """

    finished_cmd = pyqtSignal(str, int)

    def __init__(
        self,
        profile: Optional[dict[str, Any]] = None,
        cmd: str = "",
        timeout: Optional[float] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.cmd = cmd
        self.timeout = timeout

    def run(self) -> None:
        try:
            # If no profile or empty profile, run locally
            if not self.profile:
                result = subprocess.run(
                    self.cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )
                output = result.stdout
                if result.stderr:
                    output += "\n" + result.stderr
                self.finished_cmd.emit(output, result.returncode)
                return

            # Extract connection parameters from profile
            host = self.profile.get("ssh_host", "localhost")
            port = int(self.profile.get("ssh_port", 22) or 22)
            user = self.profile.get("ssh_user", "")
            
            # Extract credentials
            creds = profile_creds(self.profile)
            
            # Build SSH kwargs with all connection parameters
            kw = ssh_kwargs(
                host=host,
                port=port,
                user=user,
                creds=creds,
            )
            
            # Create and connect SSH client
            client = create_ssh_client()
            client.connect(**kw)
            
            # Execute command
            stdin, stdout, stderr = client.exec_command(
                self.cmd,
                timeout=self.timeout,
            )
            
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            rc = stdout.channel.recv_exit_status()
            
            client.close()
            self.finished_cmd.emit(out + err, rc)
            
        except subprocess.TimeoutExpired:
            self.finished_cmd.emit("[timeout]\n", 124)
        except Exception as e:
            self.finished_cmd.emit(f"[error] {e}\n", -1)