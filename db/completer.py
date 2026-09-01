"""
SQL completer.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QCompleter


class SqlCompleter(QCompleter):
    """
    Simple SQL/table/column completer.
    """

    def __init__(self, edit):
        super().__init__([])

        self._edit = edit

        self.setWidget(edit)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)

        self.activated.connect(self._insert)

    def set_words(self, words: list[str]) -> None:
        self.setModel(QStringListModel(sorted(set(words))))

    def _prefix(self) -> str:
        tc = self._edit.textCursor()
        text = tc.block().text()[: tc.positionInBlock()]

        match = re.search(r"[\w.`\"]+$", text)

        return match.group(0) if match else ""

    def maybe_complete(self) -> None:
        prefix = self._prefix()

        if len(prefix) >= 2:
            self.setCompletionPrefix(prefix)

            rect = self._edit.cursorRect()
            rect.setWidth(280)

            self.complete(rect)

        else:
            self.popup().hide()

    def _insert(self, text: str) -> None:
        tc = self._edit.textCursor()
        prefix = self._prefix()

        tc.movePosition(
            QTextCursor.MoveOperation.Left,
            QTextCursor.MoveMode.KeepAnchor,
            len(prefix),
        )

        tc.insertText(text)

        self._edit.setTextCursor(tc)
