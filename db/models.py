"""
Database result models.
"""

from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import QAbstractTableModel, Qt


class SqlResultModel(QAbstractTableModel):
    """
    Lightweight table model for SQL results.

    This is more efficient than QStandardItemModel for large result sets.
    """

    def __init__(
        self,
        headers: Optional[list[str]] = None,
        rows: Optional[list[list[Any]]] = None,
        parent=None,
    ):
        super().__init__(parent)

        self._headers = headers or []
        self._rows = rows or []

    def rowCount(self, parent=None) -> int:
        return len(self._rows)

    def columnCount(self, parent=None) -> int:
        return len(self._headers)

    def data(self, index, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if not index.isValid():
            return None

        try:
            value = self._rows[index.row()][index.column()]
        except IndexError:
            return None

        if value is None:
            return "NULL"

        return str(value)

    def headerData(self, section, orientation, role):
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            try:
                return str(self._headers[section])
            except IndexError:
                return None

        return str(section + 1)

    def set_result(
        self,
        headers: list[str],
        rows: list[list[Any]],
    ) -> None:
        self.beginResetModel()
        self._headers = headers or []
        self._rows = rows or []
        self.endResetModel()

    def clear(self) -> None:
        self.set_result([], [])

    def value(self, row: int, column: int) -> Any:
        """
        Return original DB value, not display string.
        """
        try:
            return self._rows[row][column]
        except IndexError:
            return None

    def row_values(self, row: int) -> list[Any]:
        """
        Return original DB values for one row.
        """
        try:
            return list(self._rows[row])
        except IndexError:
            return []
