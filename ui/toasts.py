"""
Toast notifications and notification center.
"""

from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QTimer,
)

from PyQt6.QtGui import QGuiApplication

from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Toast(QWidget):
    """
    Small animated toast popup.
    """

    _stack = []

    def __init__(
        self,
        theme: dict,
        level: str,
        title: str,
        msg: str,
        anchor_window=None,
    ):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )

        color = {
            "ok": theme["ok"],
            "warn": theme["warn"],
            "error": theme["danger"],
            "info": theme["accent"],
        }.get(level, theme["accent"])

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)

        card.setStyleSheet(
            f"background:{theme['panel2']};"
            f"border:1px solid {color};"
            f"border-left:4px solid {color};"
            "border-radius:6px;"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"color:{color};font-weight:bold;font-size:13px;border:none;"
        )

        msg_label = QLabel(msg)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(
            f"color:{theme['text']};font-size:12px;border:none;"
        )

        card_layout.addWidget(title_label)
        card_layout.addWidget(msg_label)

        layout.addWidget(card)

        self.setWindowOpacity(0.0)

        if anchor_window:
            geo = anchor_window.geometry()

            y = geo.bottom() - 90 - (len(Toast._stack) * 86)

            self.move(
                geo.right() - 380,
                max(40, y),
            )

        else:
            screen = QGuiApplication.primaryScreen().geometry()

            self.move(
                screen.right() - 400,
                screen.bottom() - 120 - len(Toast._stack) * 86,
            )

        Toast._stack.append(self)

        self.show()

        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(220)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(0.97)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

        QTimer.singleShot(3800, self.fade_out)

    def fade_out(self) -> None:
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.windowOpacity())
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.close)
        self.anim.start()

    def closeEvent(self, event):
        if self in Toast._stack:
            Toast._stack.remove(self)

        super().closeEvent(event)


class NotificationCenterDialog(QDialog):
    """
    Notification center dialog.
    """

    def __init__(self, parent, services):
        super().__init__(parent)

        self.services = services

        self.setWindowTitle("Notification Center")
        self.resize(560, 480)

        layout = QVBoxLayout(self)

        bar = QHBoxLayout()

        clear = QPushButton("Clear All")
        clear.clicked.connect(self._clear_all)

        bar.addStretch()
        bar.addWidget(clear)

        layout.addLayout(bar)

        self.list = QListWidget()

        layout.addWidget(self.list)

        self._fill()

    def _clear_all(self) -> None:
        self.services.notifications.clear()
        self._fill()

    def _fill(self) -> None:
        self.list.clear()

        icons = {
            "ok": "✅",
            "warn": "⚠️",
            "error": "❌",
            "info": "ℹ️",
        }

        for n in self.services.notifications.items:
            item = QListWidgetItem(
                f"{icons.get(n['level'], '•')} "
                f"[{n['ts']}] {n['title']} — {n['msg']}"
            )

            self.list.addItem(item)
