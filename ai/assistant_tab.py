"""
AI Assistant Tab for generating and executing Shell/SQL commands.
"""
import logging
import re
import time
import threading
import traceback
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QPlainTextEdit, QMessageBox,
    QSplitter, QApplication, QToolButton, QSizePolicy,
    QCheckBox, QProgressBar, QInputDialog,
)
from admin_suite.ai.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

# ---------- Thread -> GUI signal bridges ----------
class _WorkerSignals(QObject):
    """Signals for background model fetching and connection pinging."""
    models_loaded = pyqtSignal(list)
    models_error = pyqtSignal(str)
    ping_success = pyqtSignal()
    ping_failed = pyqtSignal(str)

class _GenSignals(QObject):
    """Signals for streaming generation."""
    token = pyqtSignal(str)
    done = pyqtSignal(str, float, int)
    error = pyqtSignal(str)


class AIAssistantTab(QWidget):
    MAX_HISTORY = 15

    def __init__(self, services, main_window=None):
        super().__init__(main_window)
        logger.info("Initializing AIAssistantTab")
        
        self.services = services
        self.main_window = main_window
        self.client = OllamaClient()
        self._cancel_flag = False
        self._worker_thread: threading.Thread | None = None
        self._history: list[str] = []
        self._start_time = 0.0
        self._token_count = 0
        
        # Setup thread-safe signals
        self._signals = _WorkerSignals()
        self._signals.models_loaded.connect(self._populate_models)
        self._signals.models_error.connect(self._on_models_error)
        self._signals.ping_success.connect(self._on_ping_success)
        self._signals.ping_failed.connect(self._on_ping_failed)
        
        theme = self.services.theme.current
        self._accent = theme.get("accent", "#3b82f6")
        self._sub = theme.get("sub", "#888")
        self._ok = theme.get("ok", "#28a745")
        self._err = theme.get("err", "#dc3545")
        
        self._build_ui()
        logger.info("UI built, refreshing model list...")
        self._refresh_models()

    # =========================================================
    # UI
    # =========================================================
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QLabel("🤖 AI Command Assistant")
        header.setStyleSheet(f"color:{self._accent}; font-size:18px; font-weight:bold;")
        layout.addWidget(header)

        cfg = QHBoxLayout()
        cfg.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setFixedWidth(220)
        self.model_combo.setToolTip("Pick an installed model or type one (e.g. qwen2.5:7b)")
        cfg.addWidget(self.model_combo)

        self.refresh_models_btn = QToolButton()
        self.refresh_models_btn.setText("🔄")
        self.refresh_models_btn.setToolTip("Refresh model list from Ollama")
        self.refresh_models_btn.clicked.connect(self._refresh_models)
        cfg.addWidget(self.refresh_models_btn)
        
        cfg.addSpacing(12)
        cfg.addWidget(QLabel("Context:"))
        self.context_type = QComboBox()
        self.context_type.addItems(["Terminal (Shell)", "Database (SQL)"])
        self.context_type.setFixedWidth(160)
        cfg.addWidget(self.context_type)

        self.check_conn_btn = QPushButton("🔌 Test Connection")
        self.check_conn_btn.clicked.connect(self.test_connection)
        cfg.addWidget(self.check_conn_btn)
        cfg.addStretch()
        layout.addLayout(cfg)

        task_header = QHBoxLayout()
        task_header.addWidget(QLabel("Task Description:"))
        task_header.addStretch()
        hint = QLabel("Tip: Ctrl+Enter to generate · Ctrl+L to clear")
        hint.setStyleSheet(f"color:{self._sub}; font-style:italic; font-size:11px;")
        task_header.addWidget(hint)
        layout.addLayout(task_header)

        self.task_input = QPlainTextEdit()
        self.task_input.setFixedHeight(80)
        self.task_input.setPlaceholderText("Describe your task... (e.g., 'Find all files larger than 100MB in /var')")
        self.task_input.setStyleSheet("padding: 6px; border-radius: 4px;")
        layout.addWidget(self.task_input)

        QShortcut(QKeySequence("Ctrl+Return"), self.task_input).activated.connect(self.generate)
        QShortcut(QKeySequence("Ctrl+Enter"),  self.task_input).activated.connect(self.generate)
        QShortcut(QKeySequence("Ctrl+L"),      self).activated.connect(self._clear_all)

        recent_row = QHBoxLayout()
        recent_row.addWidget(QLabel("Recent:"))
        self.history_combo = QComboBox()
        self.history_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.history_combo.addItem("(no history yet)")
        self.history_combo.setEnabled(False)
        self.history_combo.currentIndexChanged.connect(self._on_history_selected)
        recent_row.addWidget(self.history_combo, 1)
        layout.addLayout(recent_row)

        examples = QHBoxLayout()
        examples.addWidget(QLabel("Try:"))
        for label, text in self._default_examples():
            chip = QPushButton(label)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setStyleSheet(
                "padding:3px 8px; border-radius:10px; font-size:11px; "
                f"background:{self._accent}22; color:{self._accent}; border:1px solid {self._accent}55;"
            )
            chip.clicked.connect(lambda _, t=text: self.task_input.setPlainText(t))
            examples.addWidget(chip)
        examples.addStretch()
        layout.addLayout(examples)

        gen_row = QHBoxLayout()
        self.wrap_chk = QCheckBox("Word wrap")
        self.wrap_chk.setChecked(True)
        self.wrap_chk.toggled.connect(self._toggle_wrap)
        gen_row.addWidget(self.wrap_chk)
        gen_row.addStretch()

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setStyleSheet(f"background:{self._err}; color:white; font-weight:bold; padding:6px 14px; border-radius:4px;")
        self.cancel_btn.clicked.connect(self._cancel_generation)
        self.cancel_btn.hide()
        gen_row.addWidget(self.cancel_btn)

        self.gen_btn = QPushButton("✨ Generate Command")
        self.gen_btn.setStyleSheet(f"background:{self._accent}; color:white; font-weight:bold; padding:8px 18px; border-radius:4px;")
        self.gen_btn.clicked.connect(self.generate)
        gen_row.addWidget(self.gen_btn)
        layout.addLayout(gen_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.hide()
        layout.addWidget(self.progress)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(6)
        
        out_widget = QWidget()
        out_layout = QVBoxLayout(out_widget)
        out_layout.setContentsMargins(0, 0, 0, 0)
        out_layout.addWidget(QLabel("Generated Command / Script:"))
        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setFont(QFont("JetBrains Mono, Consolas, monospace", 11))
        self.output_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.output_edit.setPlaceholderText("Generated script will appear here...")
        out_layout.addWidget(self.output_edit)
        splitter.addWidget(out_widget)

        act_widget = QWidget()
        act_layout = QVBoxLayout(act_widget)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.addWidget(QLabel("Actions:"))
        
        btn_row = QHBoxLayout()
        self.copy_btn = self._action_btn("📋 Copy", self.copy_output)
        self.clear_btn = self._action_btn("🧹 Clear", self._clear_output)
        self.regen_btn = self._action_btn("🔁 Regenerate", self.generate)
        self.exec_term_btn = self._action_btn("▶ Execute in Terminal", self.execute_in_terminal, bg=self._ok)
        self.exec_db_btn = self._action_btn("🗄 Execute in Database", self.execute_in_db, bg="#0078d4")
        
        for b in (self.copy_btn, self.clear_btn, self.regen_btn, self.exec_term_btn, self.exec_db_btn):
            btn_row.addWidget(b)
            b.setEnabled(False)
        btn_row.addStretch()
        act_layout.addLayout(btn_row)

        stats_row = QHBoxLayout()
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet(f"color:{self._sub}; font-size:11px;")
        stats_row.addWidget(self.stats_label)
        stats_row.addStretch()
        act_layout.addLayout(stats_row)
        splitter.addWidget(act_widget)
        
        splitter.setSizes([380, 140])
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("Ready. Ensure Ollama is running locally (default: http://127.0.0.1:11434).")
        self.status_label.setStyleSheet(f"color:{self._sub}; font-size:11px;")
        layout.addWidget(self.status_label)

    def _action_btn(self, text, slot, bg=None):
        b = QPushButton(text)
        if bg:
            b.setStyleSheet(f"background:{bg}; color:white; font-weight:bold; padding:6px 12px; border-radius:4px;")
        b.clicked.connect(slot)
        return b

    def _default_examples(self) -> list[tuple[str, str]]:
        ctx = self.context_type.currentText()
        if "Terminal" in ctx:
            return [
                ("Top 10 CPU procs", "List top 10 processes by CPU usage"),
                ("Disk usage",       "Show disk usage per folder in /var, sorted descending"),
                ("Large files",      "Find files larger than 100MB in /var"),
            ]
        return [
            ("Top users",      "Get top 10 most active users in the last 30 days"),
            ("Orphan rows",    "Find orders with no matching customer"),
            ("Slow queries",   "Show queries taking more than 5 seconds in the last hour"),
        ]

    # =========================================================
    # Model list / connection (Thread-Safe)
    # =========================================================
    def _refresh_models(self):
        logger.info("Refreshing model list from Ollama")
        self.status_label.setText("🔄 Fetching model list from Ollama...")
        self.refresh_models_btn.setEnabled(False)

        def work():
            try:
                logger.info("Background thread: calling list_models()")
                models = self.client.list_models()
                names = [m.get("name", "") for m in models if m.get("name")]
                logger.info(f"Background thread: got {len(names)} models")
                # SAFE: Emit signal to main thread
                self._signals.models_loaded.emit(names)
            except Exception as e:
                logger.error(f"Background thread: failed to fetch models: {e}")
                logger.error(traceback.format_exc())
                # SAFE: Emit error signal to main thread
                self._signals.models_error.emit(str(e))

        threading.Thread(target=work, daemon=True).start()
        logger.info("Background thread spawned for model refresh")

    def _populate_models(self, names: list[str]):
        self.refresh_models_btn.setEnabled(True)
        logger.info(f"Populating model combo with {len(names)} models")
        current = self.model_combo.currentText().strip() or "qwen2.5:7b"
        self.model_combo.clear()
        if names:
            self.model_combo.addItems(names)
        if current and current not in names:
            self.model_combo.insertItem(0, current)
        idx = self.model_combo.findText(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.status_label.setText(f"✅ Loaded {len(names)} model(s) from Ollama.")

    def _on_models_error(self, err: str):
        self.refresh_models_btn.setEnabled(True)
        self.status_label.setText(f"❌ Could not list models: {err}")
        logger.error(f"Failed to fetch models: {err}")

    def test_connection(self):
        logger.info("Testing Ollama connection")
        self.status_label.setText("🔌 Testing connection to Ollama...")
        self.check_conn_btn.setEnabled(False)

        def work():
            try:
                if self.client.ping():
                    self._signals.ping_success.emit()
                else:
                    self._signals.ping_failed.emit("Ollama returned an unexpected response.")
            except Exception as e:
                self._signals.ping_failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_ping_success(self):
        self.check_conn_btn.setEnabled(True)
        self.status_label.setText("✅ Connected to Ollama successfully.")
        self._refresh_models()

    def _on_ping_failed(self, err: str):
        self.check_conn_btn.setEnabled(True)
        self.status_label.setText(f"❌ Connection failed: {err}")
        logger.error(f"Connection test failed: {err}")

    # =========================================================
    # Prompt building & response parsing
    # =========================================================
    def _build_system_prompt(self) -> str:
        ctx = self.context_type.currentText()
        if "Terminal" in ctx:
            return (
                "You are an expert Linux system administrator. "
                "The user will give you a task. Provide ONLY the exact bash/shell command "
                "or script to accomplish it. Do not include explanations, conversational text, "
                "or markdown code blocks. Just output the raw commands."
            )
        base = (
            "You are an expert database administrator. "
            "The user will give you a task. Provide ONLY the exact SQL query to accomplish it. "
            "Do not include explanations, conversational text, or markdown code blocks. "
            "Just output the raw query."
        )
        if self.main_window and hasattr(self.main_window, "db_manager_widget"):
            schema = getattr(self.main_window.db_manager_widget, "current_schema", None)
            if schema:
                base += f" The current database/schema is '{schema}'."
        return base

    @staticmethod
    def _extract_command(content: str) -> str:
        if not content:
            return ""
        blocks = re.findall(r"```[a-zA-Z0-9_+-]*\s*\n?(.*?)```", content, re.DOTALL)
        if blocks:
            return blocks[-1].strip()
        inline = re.findall(r"`([^`\n]+)`", content)
        if inline and len(inline[-1]) > 3:
            return inline[-1].strip()
        cleaned = content.strip()
        for prefix in ("Here is", "Here's", "Sure", "Sure,", "The command is", "The query is", "Use this", "Try this", "Run this"):
            if cleaned.lower().startswith(prefix.lower()):
                nl = cleaned.find("\n")
                if nl != -1 and nl < 120:
                    cleaned = cleaned[nl + 1:].strip()
                break
        return cleaned

    # =========================================================
    # Generation (streaming)
    # =========================================================
    def generate(self):
        task = self.task_input.toPlainText().strip()
        if not task:
            QMessageBox.warning(self, "Validation Error", "Please provide a description of the task first.")
            return

        model = self.model_combo.currentText().strip() or "qwen2.5:7b"
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user",   "content": task},
        ]

        self._set_busy(True)
        self.output_edit.clear()
        self.stats_label.setText("")
        self.status_label.setText(f"⏳ Generating with '{model}' (streaming)...")
        self._start_time = time.time()
        self._token_count = 0
        self._cancel_flag = False
        self._push_history(task)

        signals = _GenSignals()
        signals.token.connect(self._on_token)
        signals.done.connect(self._on_done)
        signals.error.connect(self._on_error)

        def work():
            try:
                stream = self.client.chat(model, messages, stream=True)
                buf = ""
                for chunk in stream:
                    if self._cancel_flag:
                        break
                    delta = (chunk.get("message", {}).get("content", "") or chunk.get("response", ""))
                    if delta:
                        buf += delta
                        signals.token.emit(delta)
                
                final = self._extract_command(buf)
                elapsed = time.time() - self._start_time
                signals.done.emit(final, elapsed, self._token_count)
            except Exception as e:
                logger.error(f"Generation failed: {e}")
                signals.error.emit(str(e))

        self._worker_thread = threading.Thread(target=work, daemon=True)
        self._worker_thread.start()

    def _on_token(self, token: str):
        self._token_count += 1
        cursor = self.output_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(token)
        self.output_edit.setTextCursor(cursor)
        self.output_edit.ensureCursorVisible()
        elapsed = time.time() - self._start_time
        self.stats_label.setText(f"⏱ {elapsed:.1f}s · ~{self._token_count} tokens (streaming...)")

    def _on_done(self, final: str, elapsed: float, tokens: int):
        self.output_edit.setPlainText(final)
        self._set_busy(False)
        self.status_label.setText("✅ Generation complete.")
        self.stats_label.setText(f"⏱ {elapsed:.1f}s · ~{tokens} tokens · {len(final)} chars")
        self._update_action_buttons(bool(final))

    def _on_error(self, err: str):
        self._set_busy(False)
        self.output_edit.setPlainText(f"[ERROR] {err}")
        self.status_label.setText(f"❌ Generation failed: {err}")
        self._update_action_buttons(False)

    def _cancel_generation(self):
        self._cancel_flag = True
        self.status_label.setText("⏹ Cancellation requested...")

    def _set_busy(self, busy: bool):
        self.gen_btn.setEnabled(not busy)
        self.gen_btn.setVisible(not busy)
        self.cancel_btn.setVisible(busy)
        self.progress.setVisible(busy)
        self.task_input.setReadOnly(busy)

    def _update_action_buttons(self, has_output: bool):
        for b in (self.copy_btn, self.clear_btn, self.regen_btn, self.exec_term_btn, self.exec_db_btn):
            b.setEnabled(has_output)

    # =========================================================
    # History & Misc
    # =========================================================
    def _push_history(self, task: str):
        if task in self._history:
            self._history.remove(task)
        self._history.insert(0, task)
        self._history = self._history[: self.MAX_HISTORY]
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        for h in self._history:
            short = (h[:70] + "…") if len(h) > 70 else h
            self.history_combo.addItem(short)
        self.history_combo.setEnabled(True)
        self.history_combo.blockSignals(False)

    def _on_history_selected(self, idx: int):
        if 0 <= idx < len(self._history):
            self.task_input.setPlainText(self._history[idx])

    def _toggle_wrap(self, on: bool):
        mode = QPlainTextEdit.LineWrapMode.WidgetWidth if on else QPlainTextEdit.LineWrapMode.NoWrap
        self.output_edit.setLineWrapMode(mode)

    def _clear_output(self):
        self.output_edit.clear()
        self.stats_label.setText("")
        self._update_action_buttons(False)

    def _clear_all(self):
        self.task_input.clear()
        self._clear_output()
        self.status_label.setText("🧹 Cleared.")

    def copy_output(self):
        text = self.output_edit.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("📋 Copied to clipboard.")

    # =========================================================
    # Execution
    # =========================================================
    def _find_all_terminals(self) -> list[tuple[str, object]]:
        """Scans all tabs in the main window to find active terminal instances."""
        terminals = []
        if not self.main_window or not hasattr(self.main_window, "tabs"):
            return terminals
            
        for i in range(self.main_window.tabs.count()):
            widget = self.main_window.tabs.widget(i)
            tab_name = self.main_window.tabs.tabText(i) or f"Tab {i+1}"
            
            if hasattr(widget, "send_command"):
                term_name = getattr(widget, "name", None) or tab_name
                terminals.append((term_name, widget))
            elif hasattr(widget, "terminals") and widget.terminals:
                for j, term in enumerate(widget.terminals):
                    if hasattr(term, "send_command"):
                        term_name = getattr(term, "name", None) or f"{tab_name} #{j+1}"
                        terminals.append((term_name, term))
        return terminals

    def execute_in_terminal(self):
        if not self.main_window:
            return
        cmd = self.output_edit.toPlainText().strip()
        if not cmd:
            QMessageBox.warning(self, "Execute", "No command found to execute.")
            return
            
        terminals = self._find_all_terminals()
        if not terminals:
            QMessageBox.warning(self, "Execute", "No active terminal tabs found. Please open a terminal tab first.")
            return

        choices = []
        for name, _ in terminals:
            base_name = name
            counter = 1
            while name in choices:
                name = f"{base_name} ({counter})"
                counter += 1
            choices.append(name)

        if len(terminals) > 1:
            choices.append("▶ All Terminals")

        choice, ok = QInputDialog.getItem(
            self, "Select Target Terminal", "Choose a terminal to execute the command in:", choices, 0, False
        )
        
        if not ok or not choice:
            return

        if choice == "▶ All Terminals":
            for _, term in terminals:
                term.send_command(cmd)
            self.status_label.setText(f"▶ Sent command to ALL {len(terminals)} terminals.")
        else:
            idx = choices.index(choice)
            target = terminals[idx][1]
            target.send_command(cmd)
            self.status_label.setText(f"▶ Sent command to terminal: {choice}")

    def execute_in_db(self):
        if not self.main_window:
            return
        sql = self.output_edit.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "Execute", "No SQL query found to execute.")
            return
            
        if hasattr(self.main_window, "db_manager_widget"):
            db_mgr = self.main_window.db_manager_widget
            db_mgr.query_edit.setPlainText(sql)
            self.main_window.tabs.setCurrentWidget(db_mgr)
            self.status_label.setText("🗄 SQL loaded into Database Manager. Press F5 to run.")
        else:
            QMessageBox.warning(self, "Execute", "Database Manager widget not found.")