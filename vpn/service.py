from __future__ import annotations

import os
import re
import shlex
import signal
import subprocess
import threading
from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class VpnService(QObject):
    """
    VPN connection service.
    """

    result = pyqtSignal(dict)

    def __init__(self, services):
        super().__init__()

        self.services = services

        self.connected = False
        self.busy = False
        self.status_checking = False
        self.pending_toggle = False

    # ------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------

    def _log(self, message: str) -> None:
        self.services.emit_log("vpn", message)

    # ------------------------------------------------------------
    # CLI execution
    # ------------------------------------------------------------

    def _run_cli(
        self,
        args: list[str],
        timeout: int = 15,
        input_text: Optional[str] = None,
    ) -> tuple[int, str, str]:
        """
        Run VPN CLI safely.

        Returns:
            return_code, stdout, stderr
        """
        cli = str(self.services.config.get("vpn_cli", "") or "").strip()

        if not cli:
            return 127, "", "VPN CLI not configured"

        try:
            cli_argv = shlex.split(cli)
        except Exception as e:
            return 127, "", f"Invalid VPN CLI: {e}"

        if not cli_argv:
            return 127, "", "VPN CLI not configured"

        cmd = cli_argv + [str(a) for a in args]

        stdin_mode = (
            subprocess.PIPE
            if input_text is not None
            else subprocess.DEVNULL
        )

        popen_kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=stdin_mode,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if os.name != "nt":
            popen_kwargs["start_new_session"] = True

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)

            try:
                out, err = proc.communicate(
                    input=input_text,
                    timeout=timeout,
                )

            except subprocess.TimeoutExpired:
                killed = False

                if os.name != "nt":
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                        killed = True
                    except Exception:
                        pass

                if not killed:
                    try:
                        proc.kill()
                    except Exception:
                        pass

                try:
                    out, err = proc.communicate(timeout=2)
                except Exception:
                    out, err = "", ""

                return 124, out or "", err or f"VPN CLI timed out after {timeout}s"

            rc = proc.returncode if proc.returncode is not None else -1

            return rc, out or "", err or ""

        except FileNotFoundError:
            return 127, "", f"VPN CLI not found: {cli}"

        except Exception as e:
            return 1, "", str(e)

    # ------------------------------------------------------------
    # State parsing
    # ------------------------------------------------------------

    def parse_state(self, output: str, rc: Optional[int] = None) -> Optional[bool]:
        """
        Parse VPN status output.

        Returns:
            True  -> connected
            False -> disconnected
            None  -> unknown
        """
        txt = (output or "").lower()

        if re.search(r"state\s*:\s*connected", txt):
            return True

        if re.search(r"state\s*:\s*disconnected", txt):
            return False

        if re.search(r"\bnot connected\b", txt):
            return False

        if re.search(r"\bdisconnected\b", txt):
            return False

        if (
            rc == 0
            and re.search(r"\bconnected\b", txt)
            and not re.search(r"disconnect", txt)
        ):
            return True

        return None

    # ------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------

    def toggle(self) -> None:
        """
        Toggle VPN after verifying real state.
        """
        if self.busy:
            self._log("VPN toggle ignored: another VPN operation is running.")
            return

        if self.status_checking:
            self.pending_toggle = True
            self._log("Waiting for VPN status check before toggling.")
            return

        self.busy = True

        def work():
            rc, out, err = self._run_cli(["status"], timeout=6)
            state = self.parse_state(out + "\n" + err, rc)

            self.busy = False

            self.result.emit(
                {
                    "op": "toggle_status",
                    "state": state,
                    "rc": rc,
                    "out": out,
                    "err": err,
                }
            )

        threading.Thread(target=work, daemon=True).start()

    def connect_vpn(self) -> None:
        """
        Connect VPN.
        """
        if self.busy:
            self._log("VPN connect ignored: another VPN operation is running.")
            return

        if not self.services.config.get("vpn_cli") or not self.services.config.get(
            "vpn_host"
        ):
            self.result.emit(
                {
                    "op": "connect",
                    "error": "Set VPN CLI path and VPN host in Connection Manager first.",
                }
            )
            return

        self.busy = True

        def work():
            rc = -1
            out = ""
            err = ""

            rc2 = -1
            out2 = ""
            err2 = ""

            state = None

            try:
                cert_pass = self.services.secrets.get("vpn_cert_pass", "")
                vpn_pass = self.services.secrets.get("vpn_pass", "")

                inputs = f"{cert_pass}\n{vpn_pass}\ny\n"

                rc, out, err = self._run_cli(
                    [
                        "-s",
                        "connect",
                        str(self.services.config.get("vpn_host", "")),
                    ],
                    timeout=60,
                    input_text=inputs,
                )

                rc2, out2, err2 = self._run_cli(["status"], timeout=6)

                state = self.parse_state(out2 + "\n" + err2, rc2)

                if state is None:
                    state = self.parse_state(out + "\n" + err, rc)

            except Exception as e:
                err = str(e)

            finally:
                self.busy = False

                self.result.emit(
                    {
                        "op": "connect",
                        "rc": rc,
                        "out": out,
                        "err": err,
                        "rc2": rc2,
                        "out2": out2,
                        "err2": err2,
                        "state": state,
                    }
                )

        threading.Thread(target=work, daemon=True).start()

    def disconnect_vpn(self) -> None:
        """
        Disconnect VPN.
        """
        if self.busy:
            self._log("VPN disconnect ignored: another VPN operation is running.")
            return

        if not self.services.config.get("vpn_cli"):
            self.result.emit(
                {
                    "op": "disconnect",
                    "error": "Set VPN CLI path in Connection Manager first.",
                }
            )
            return

        self.busy = True

        def work():
            rc = -1
            out = ""
            err = ""

            rc2 = -1
            out2 = ""
            err2 = ""

            state = None

            try:
                rc, out, err = self._run_cli(
                    ["-s", "disconnect"],
                    timeout=30,
                )

                rc2, out2, err2 = self._run_cli(["status"], timeout=6)

                state = self.parse_state(out2 + "\n" + err2, rc2)

                if state is None:
                    state = self.parse_state(out + "\n" + err, rc)

            except Exception as e:
                err = str(e)

            finally:
                self.busy = False

                self.result.emit(
                    {
                        "op": "disconnect",
                        "rc": rc,
                        "out": out,
                        "err": err,
                        "rc2": rc2,
                        "out2": out2,
                        "err2": err2,
                        "state": state,
                    }
                )

        threading.Thread(target=work, daemon=True).start()

    def check_status(self) -> None:
        """
        Background status poll.
        """
        if self.busy:
            return

        if self.status_checking:
            return

        self.status_checking = True

        def work():
            rc, out, err = self._run_cli(["status"], timeout=6)
            state = self.parse_state(out + "\n" + err, rc)

            self.status_checking = False

            pending_toggle = self.pending_toggle
            self.pending_toggle = False

            self.result.emit(
                {
                    "op": "poll_status",
                    "state": state,
                    "rc": rc,
                    "out": out,
                    "err": err,
                    "pending_toggle": pending_toggle,
                }
            )

        threading.Thread(target=work, daemon=True).start()
