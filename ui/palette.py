"""
Command palette.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer

from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class CommandPaletteDialog(QDialog):
    """
    Fuzzy-style command palette.
    """

    def __init__(self, parent, commands):
        super().__init__(parent)

        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(560, 420)

        self.commands = commands

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Type a command, profile, or tool... (Esc closes)"
        )
        self.input.setStyleSheet("font-size:15px;padding:8px;")
        self.input.textChanged.connect(self.filter)

        layout.addWidget(self.input)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda: self.run_current())

        layout.addWidget(self.list, 1)

        # ------------------------------------------------------------
        # Fixed hint color handling.
        #
        # parent may be MainWindow, which has a services attribute.
        # If not, fall back to a neutral gray color.
        # ------------------------------------------------------------

        services = getattr(parent, "services", None)

        hint_color = "#888"

        if services is not None:
            try:
                hint_color = services.theme.current.get("sub", "#888")
            except Exception:
                hint_color = "#888"

        hint = QLabel("↑↓ to navigate · Enter to run")
        hint.setStyleSheet(
            f"color:{hint_color};font-size:11px;"
        )

        layout.addWidget(hint)

        self.filter("")

        self.input.setFocus()

    def filter(self, text: str) -> None:
        self.list.clear()

        t = text.lower()

        for command in self.commands:
            haystack = (
                command.get("name", "") + " " + command.get("hint", "")
            ).lower()

            if t and t not in haystack:
                continue

            item = QListWidgetItem(command.get("name", ""))
            item.setData(Qt.ItemDataRole.UserRole, command)

            if command.get("hint"):
                item.setToolTip(command["hint"])

            self.list.addItem(item)

        if self.list.count():
            self.list.setCurrentRow(0)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.run_current()

        elif event.key() == Qt.Key.Key_Down:
            if self.list.count():
                self.list.setCurrentRow(
                    min(
                        self.list.currentRow() + 1,
                        self.list.count() - 1,
                    )
                )

        elif event.key() == Qt.Key.Key_Up:
            if self.list.count():
                self.list.setCurrentRow(
                    max(
                        self.list.currentRow() - 1,
                        0,
                    )
                )

        else:
            super().keyPressEvent(event)

    def run_current(self) -> None:
        item = self.list.currentItem()

        if item:
            command = item.data(Qt.ItemDataRole.UserRole)

            self.accept()

            QTimer.singleShot(50, command["cb"])