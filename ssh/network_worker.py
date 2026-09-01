"""
Qt worker for SSH networking tools.
"""

from __future__ import annotations

import threading
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from admin_suite.ssh.networking import (
    ConnectionResources,
    ForwardRule,
    SshTarget,
    connect_ssh_target,
    start_forwarding,
)


class SshNetworkingWorker(QThread):
    """
    Runs an SSH networking session with port forwarding support.
    """

    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    forward_started = pyqtSignal(object, int)
    stopped = pyqtSignal()

    def __init__(
        self,
        target: SshTarget,
        forwards: List[ForwardRule],
        agent_forwarding: bool = False,
        parent=None,
    ):
        super().__init__(parent)

        self.target = target
        self.forwards = forwards
        self.agent_forwarding = agent_forwarding

        self._stop_event = threading.Event()
        self._transport = None
        self._resources: Optional[ConnectionResources] = None
        self._handlers = []
        self._agent_channel = None

    def stop(self) -> None:
        self._stop_event.set()

        for handler in self._handlers:
            try:
                handler.stop()
            except Exception:
                pass

        if self._agent_channel is not None:
            try:
                self._agent_channel.close()
            except Exception:
                pass

        if self._resources is not None:
            try:
                self._resources.close()
            except Exception:
                pass

    def run(self) -> None:
        try:
            self.status_changed.emit("connecting")
            self.log_message.emit(
                f"Connecting to {self.target.username}@{self.target.host}:{self.target.port}"
            )

            transport, resources = connect_ssh_target(self.target)

            self._transport = transport
            self._resources = resources

            self.status_changed.emit("connected")
            self.log_message.emit("SSH connection established.")

            if self.agent_forwarding:
                self.log_message.emit(
                    "Agent forwarding requested. "
                    "For terminal sessions, ensure your SSH worker calls "
                    "enable_agent_forwarding(channel) on the session channel."
                )

            self._handlers = start_forwarding(
                transport,
                self.forwards,
                log_cb=self.log_message.emit,
            )

            for rule in self.forwards:
                if rule.kind != "remote":
                    self.forward_started.emit(rule, int(rule.listen_port))

            self.status_changed.emit("running")

            while not self._stop_event.wait(0.5):
                if not transport.is_active():
                    self.log_message.emit("SSH transport closed.")
                    break

        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.log_message.emit(f"Networking error: {exc}")

        finally:
            self.status_changed.emit("stopping")

            for handler in self._handlers:
                try:
                    handler.stop()
                except Exception:
                    pass

            if self._resources is not None:
                try:
                    self._resources.close()
                except Exception:
                    pass

            self.status_changed.emit("stopped")
            self.stopped.emit()