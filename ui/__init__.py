"""
UI subsystem.
"""

from admin_suite.ui.toasts import (
    Toast,
    NotificationCenterDialog,
)

from admin_suite.ui.palette import (
    CommandPaletteDialog,
)

from admin_suite.ui.dialogs import (
    ProfileDialog,
    DbProfileDialog,
    ConnectionManagerDialog,
    ThemeDialog,
    KeyManagerDialog,
    SessionLogViewerDialog,
    SnippetDialog,
    SnippetManagerDialog,
)

from admin_suite.ui.main_window import (
    MainWindow,
)

__all__ = [
    "Toast",
    "NotificationCenterDialog",
    "CommandPaletteDialog",
    "ProfileDialog",
    "DbProfileDialog",
    "ConnectionManagerDialog",
    "ThemeDialog",
    "KeyManagerDialog",
    "SessionLogViewerDialog",
    "SnippetDialog",
    "SnippetManagerDialog",
    "MainWindow",
]
