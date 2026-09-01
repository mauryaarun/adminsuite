"""
Central application services.

Later UI modules should receive this service container instead of using
global variables.
"""

from __future__ import annotations

from typing import Any

from admin_suite.core import (
    ConfigStore,
    DebugPipeline,
    NotificationHub,
    SecretStore,
    ThemeManager,
    ensure_dirs,
)

from admin_suite.core import paths


COMMON_PASSWORD_KEYS = (
    "ssh_pass",
    "db_pass",
    "vpn_cert_pass",
    "vpn_pass",
)


class AppServices:
    """
    Dependency container for the application.
    """

    def __init__(self):
        ensure_dirs()

        self.paths = paths

        self.config = ConfigStore()
        self.secrets = SecretStore()

        self.debug = DebugPipeline()
        self.notifications = NotificationHub()

        self.theme = ThemeManager()

    def emit_log(self, source: str, message: str) -> None:
        """
        Convenience logger.
        """
        self.debug.emit(source, message)

    def apply_theme(self, app: Any) -> None:
        """
        Apply configured UI theme to a QApplication instance.
        """
        theme_name = self.config.get("ui_theme", "Breeze Dark")
        self.theme.apply(app, theme_name)

    def load_passwords(self) -> dict[str, str]:
        """
        Load common global password fields from keyring.
        """
        return {
            key: self.secrets.get(key, "")
            for key in COMMON_PASSWORD_KEYS
        }

    def save_passwords(self, values: dict[str, str]) -> None:
        """
        Save/delete common global password fields in keyring.
        """
        for key in COMMON_PASSWORD_KEYS:
            self.secrets.set(key, values.get(key, ""))
