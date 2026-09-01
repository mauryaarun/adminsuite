"""
SFTP dialogs.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class ChmodDialog(QDialog):
    """
    chmod permission editor.
    """

    def __init__(self, parent, current_mode: int):
        super().__init__(parent)

        self.setWindowTitle("Edit Permissions")
        self.setMinimumWidth(320)

        self.result_mode = current_mode

        lay = QFormLayout(self)

        self.boxes = {}

        for who in ("user", "group", "other"):
            row = QHBoxLayout()

            for p in ("r", "w", "x"):
                cb = QCheckBox(p)
                self.boxes[(who, p)] = cb
                row.addWidget(cb)

            lay.addRow(who.capitalize(), row)

        shifts = {"user": 6, "group": 3, "other": 0}
        perms = {"r": 4, "w": 2, "x": 1}

        for (who, p), cb in self.boxes.items():
            cb.setChecked(bool(current_mode & (perms[p] << shifts[who])))

        self.preview = QLabel("0000")
        lay.addRow("Octal:", self.preview)

        for cb in self.boxes.values():
            cb.stateChanged.connect(self._update)

        self._update()

        ok = QPushButton("Apply")
        ok.clicked.connect(self.accept)

        lay.addRow(ok)

    def _update(self) -> None:
        shifts = {"user": 6, "group": 3, "other": 0}
        perms = {"r": 4, "w": 2, "x": 1}

        value = 0

        for (who, p), cb in self.boxes.items():
            if cb.isChecked():
                value |= perms[p] << shifts[who]

        self.preview.setText(oct(value))
        self.result_mode = value
