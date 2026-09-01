"""
SQL syntax highlighter.
"""

from __future__ import annotations

import re

from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat

SQL_KEYWORDS = [
    "SELECT",
    "FROM",
    "WHERE",
    "INSERT",
    "UPDATE",
    "DELETE",
    "CREATE",
    "DROP",
    "ALTER",
    "TABLE",
    "INTO",
    "VALUES",
    "SET",
    "JOIN",
    "LEFT",
    "RIGHT",
    "INNER",
    "OUTER",
    "ON",
    "AND",
    "OR",
    "NOT",
    "NULL",
    "IS",
    "IN",
    "LIKE",
    "BETWEEN",
    "ORDER",
    "BY",
    "GROUP",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "AS",
    "DISTINCT",
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "UNION",
    "ALL",
    "EXISTS",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "INDEX",
    "PRIMARY",
    "KEY",
    "FOREIGN",
    "REFERENCES",
    "DATABASE",
    "SCHEMA",
    "SHOW",
    "DESCRIBE",
    "EXPLAIN",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "USE",
    "WITH",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
]


class SQLHighlighter(QSyntaxHighlighter):
    """
    Basic SQL highlighter.
    """

    def __init__(self, document):
        super().__init__(document)

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569cd6"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178"))

        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8"))

        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955"))
        comment_format.setFontItalic(True)

        self.rules = []

        for keyword in SQL_KEYWORDS:
            pattern = re.compile(r"\b" + keyword + r"\b", re.IGNORECASE)
            self.rules.append((pattern, keyword_format))

        self.rules.append((re.compile(r"'[^']*'"), string_format))
        self.rules.append((re.compile(r'"[^"]*"'), string_format))
        self.rules.append((re.compile(r"\b\d+(\.\d+)?\b"), number_format))
        self.rules.append((re.compile(r"--.*$"), comment_format))

        self.comment_start = re.compile(r"/\*")
        self.comment_end = re.compile(r"\*/")
        self.comment_format = comment_format

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(
                    match.start(),
                    match.end() - match.start(),
                    fmt,
                )

        self.setCurrentBlockState(0)

        start_index = 0

        if self.previousBlockState() != 1:
            start_match = self.comment_start.search(text)
            start_index = start_match.start() if start_match else -1

        while start_index >= 0:
            end_match = self.comment_end.search(text, start_index)

            if end_match:
                end_index = end_match.end()

                self.setFormat(
                    start_index,
                    end_index - start_index,
                    self.comment_format,
                )

                start_match = self.comment_start.search(text, end_index)
                start_index = start_match.start() if start_match else -1

            else:
                self.setCurrentBlockState(1)

                self.setFormat(
                    start_index,
                    len(text) - start_index,
                    self.comment_format,
                )

                break
