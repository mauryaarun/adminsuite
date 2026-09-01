"""
Secret storage using keyring.
"""

from __future__ import annotations

from typing import Optional

try:
    import keyring
except ImportError:
    keyring = None

from admin_suite.core.paths import APP_NAME


class SecretStore:
    """
    Store secrets in the operating system keyring.

    Important behavior:
    - set(key, value) stores value if non-empty
    - set(key, "") deletes the old secret
    """

    def __init__(self, app_name: str = APP_NAME):
        self.app_name = app_name

    def get(self, key: str, default: str = "") -> str:
        """
        Get secret. Returns default if unavailable.
        """
        if keyring is None:
            return default

        try:
            value = keyring.get_password(self.app_name, key)
            return value if value is not None else default
        except Exception:
            return default

    def set(self, key: str, value: Optional[str]) -> None:
        """
        Store or delete secret.
        """
        if keyring is None:
            return

        try:
            if value:
                keyring.set_password(self.app_name, key, value)
            else:
                self.delete(key)
        except Exception:
            pass

    def delete(self, key: str) -> None:
        """
        Delete secret if it exists.
        """
        if keyring is None:
            return

        try:
            keyring.delete_password(self.app_name, key)
        except Exception:
            pass
