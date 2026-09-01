"""
SQL quoting and literal helpers.
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any


def placeholder(backend: str) -> str:
    """
    Return parameter placeholder for backend.
    """
    if backend == "sqlite":
        return "?"

    return "%s"


def qident(ident: Any, backend: str) -> str:
    """
    Safely quote SQL identifier.

    MySQL:
        `ident`

    SQLite / PostgreSQL:
        "ident"
    """
    s = str(ident)

    if backend == "mysql":
        return "`" + s.replace("`", "``") + "`"

    return '"' + s.replace('"', '""') + '"'


def sql_literal(value: Any, backend: str) -> str:
    """
    Produce a SQL literal for export/dump generation.

    This is intended for SQL export, not for live parameterized execution.
    """
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float, decimal.Decimal)):
        return str(value)

    if isinstance(value, (bytes, bytearray)):
        hex_value = value.hex()

        if backend == "postgresql":
            return f"decode('{hex_value}', 'hex')"

        return f"X'{hex_value}'"

    if isinstance(value, datetime.datetime):
        return "'" + value.isoformat(sep=" ") + "'"

    if isinstance(value, datetime.date):
        return "'" + value.isoformat() + "'"

    if isinstance(value, datetime.time):
        return "'" + value.isoformat() + "'"

    s = str(value)

    if backend == "mysql":
        s = s.replace("\\", "\\\\").replace("'", "\\'")
    else:
        s = s.replace("'", "''")

    return f"'{s}'"
