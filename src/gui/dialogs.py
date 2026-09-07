"""Settings, Glossary, and Prompt management dialogs for PySide6 GUI."""

from pathlib import Path
from typing import Dict, Optional
import yaml

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QPlainTextEdit, QGroupBox, QFileDialog
)
from PySide6.QtCore import Qt

from src.config import AppConfig
from src.translation.prompt_builder import PromptBuilder

DEFAULT_PROMPT_TEMPLATE = """You are a professional Japanese (ja) to Vietnamese (vi) translator.

Your task is to translate Japanese text into natural, accurate Vietnamese.

GENERAL RULES:
- Preserve the original meaning.
- Do not add information.
- Do not omit information.
- Do not summarize.
- Do not explain the translation.
- Preserve paragraph structure.
- Preserve headings.
- Preserve numbers.
- Preserve code, commands, URLs, and technical identifiers.
- Use consistent terminology throughout the document.

STYLE:
- Use natural Vietnamese.
- Avoid overly literal translation when it produces unnatural Vietnamese.
- Preserve the author's tone.
- Preserve the level of formality.
- Do not add commentary.

TERMINOLOGY:
{GLOSSARY}

CONTEXT FROM PREVIOUS CHUNK:
{CONTEXT}

TEXT TO TRANSLATE:
{TEXT}

OUTPUT:
Return only the Vietnamese translation."""


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings - Local Translator")
        self.resize(550, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Ollama Group
        ollama_group = QGroupBox("Ollama Service")
        ollama_form = QFormLayout(ollama_group)
        self.host_input = QLineEdit(self.config.ollama_host)
        self.model_input = QLineEdit(self.config.ollama_model)
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(10, 3600)
        self.timeout_input.setValue(self.config.ollama_timeout)
        ollama_form.addRow("Host URL:", self.host_input)
        ollama_form.addRow("Model Name:", self.model_input)
        ollama_form.addRow("Timeout (sec):", self.timeout_input)
        layout.addWidget(ollama_group)

        # Translation Group
        trans_group = QGroupBox("Translation Parameters (16 GB RAM Optimized)")
        trans_form = QFormLayout(trans_group)
        self.chunk_size_input = QSpinBox()
        self.chunk_size_input.setRange(100, 10000)
        self.chunk_size_input.setValue(self.config.chunk_size)

        self.context_size_input = QSpinBox()
        self.context_size_input.setRange(0, 3000)
        self.context_size_input.setValue(self.config.context_size)

        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(0.0, 1.0)
        self.temperature_input.setSingleStep(0.05)
        self.temperature_input.setValue(self.config.temperature)

        self.retries_input = QSpinBox()
        self.retries_input.setRange(0, 10)
        self.retries_input.setValue(self.config.max_retries)

        trans_form.addRow("Chunk Size (chars):", self.chunk_size_input)
        trans_form.addRow("Context Tail (chars):", self.context_size_input)
        trans_form.addRow("Temperature:", self.temperature_input)
        trans_form.addRow("Max Retries:", self.retries_input)
        layout.addWidget(trans_group)

        # Crawler Group
        crawler_group = QGroupBox("Web Novel Crawler")
        crawler_form = QFormLayout(crawler_group)
        self.delay_input = QDoubleSpinBox()
        self.delay_input.setRange(0.1, 10.0)
        self.delay_input.setSingleStep(0.5)
        self.delay_input.setValue(self.config.crawler_delay)

        self.crawler_timeout_input = QSpinBox()
        self.crawler_timeout_input.setRange(5, 120)
        self.crawler_timeout_input.setValue(self.config.crawler_timeout)

        crawler_form.addRow("Polite Delay (sec):", self.delay_input)
        crawler_form.addRow("Request Timeout (sec):", self.crawler_timeout_input)
        layout.addWidget(crawler_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _save_settings(self):
        # Update config in-memory
        self.config.ollama_host = self.host_input.text().strip()
        self.config.ollama_model = self.model_input.text().strip()
        self.config.ollama_timeout = self.timeout_input.value()
        self.config.chunk_size = self.chunk_size_input.value()
        self.config.context_size = self.context_size_input.value()
        self.config.temperature = self.temperature_input.value()
        self.config.max_retries = self.retries_input.value()
        self.config.crawler_delay = self.delay_input.value()
        self.config.crawler_timeout = self.crawler_timeout_input.value()

        # Persist to settings.yaml
        data = {
            "ollama": {
                "host": self.config.ollama_host,
                "model": self.config.ollama_model,
                "timeout_seconds": self.config.ollama_timeout,
            },
            "translation": {
                "source_language": self.config.source_language,
                "target_language": self.config.target_language,
                "chunk_size": self.config.chunk_size,
                "context_size": self.config.context_size,
                "temperature": self.config.temperature,
                "max_retries": self.config.max_retries,
                "retry_backoff": self.config.retry_backoff,
                "continue_on_error": self.config.continue_on_error,
                "concurrency": self.config.concurrency,
            },
            "crawler": {
                "timeout_seconds": self.config.crawler_timeout,
                "max_retries": self.config.crawler_max_retries,
                "delay_seconds": self.config.crawler_delay,
                "user_agent": self.config.crawler_user_agent,
            },
            "paths": {
                "input_dir": str(self.config.input_dir.relative_to(self.config.project_root) if self.config.input_dir.is_relative_to(self.config.project_root) else self.config.input_dir),
                "output_dir": str(self.config.output_dir.relative_to(self.config.project_root) if self.config.output_dir.is_relative_to(self.config.project_root) else self.config.output_dir),
                "cache_dir": str(self.config.cache_dir.relative_to(self.config.project_root) if self.config.cache_dir.is_relative_to(self.config.project_root) else self.config.cache_dir),
                "logs_dir": str(self.config.logs_dir.relative_to(self.config.project_root) if self.config.logs_dir.is_relative_to(self.config.project_root) else self.config.logs_dir),
                "prompt_path": str(self.config.prompt_path.relative_to(self.config.project_root) if self.config.prompt_path.is_relative_to(self.config.project_root) else self.config.prompt_path),
                "glossary_path": str(self.config.glossary_path.relative_to(self.config.project_root) if self.config.glossary_path.is_relative_to(self.config.project_root) else self.config.glossary_path),
            }
        }
        with open(self.config.settings_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.accept()


class GlossaryDialog(QDialog):
    """Interactive editor for config/glossary.txt."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Glossary Editor - Terminology Dictionary")
        self.resize(650, 450)
        self._init_ui()
        self._load_glossary()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Define custom terms in format: Japanese = Vietnamese.\n"
            "Changes will be saved to config/glossary.txt and automatically applied to translation jobs."
        )
        info_label.setStyleSheet("color: #666;")
        layout.addWidget(info_label)

        # Search Bar
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter terms...")
        self.search_input.textChanged.connect(self._filter_terms)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Japanese Term", "Vietnamese Translation"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Term")
        self.add_btn.clicked.connect(self._add_row)
        self.delete_btn = QPushButton("- Delete Selected")
        self.delete_btn.clicked.connect(self._delete_selected)
        self.save_btn = QPushButton("Save to File")
        self.save_btn.clicked.connect(self._save_glossary)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.close_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _load_glossary(self):
        content = self.config.get_glossary_content()
        terms = PromptBuilder.parse_glossary_content(content)
        self.table.setRowCount(0)
        for row_idx, (ja, vi) in enumerate(sorted(terms.items())):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(ja))
            self.table.setItem(row_idx, 1, QTableWidgetItem(vi))

    def _add_row(self):
        row_idx = self.table.rowCount()
        self.table.insertRow(row_idx)
        self.table.setItem(row_idx, 0, QTableWidgetItem(""))
        self.table.setItem(row_idx, 1, QTableWidgetItem(""))
        self.table.editItem(self.table.item(row_idx, 0))

    def _delete_selected(self):
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        for r in selected_rows:
            self.table.removeRow(r)

    def _filter_terms(self, query: str):
        query = query.strip().lower()
        for r in range(self.table.rowCount()):
            ja_item = self.table.item(r, 0)
            vi_item = self.table.item(r, 1)
            ja_text = ja_item.text().lower() if ja_item else ""
            vi_text = vi_item.text().lower() if vi_item else ""
            match = not query or (query in ja_text or query in vi_text)
            self.table.setRowHidden(r, not match)

    def _save_glossary(self):
        lines = [
            "# Bảng thuật ngữ chuyên ngành (Japanese = Vietnamese)",
            "# Định dạng: <Từ tiếng Nhật> = <Bản dịch tiếng Việt>",
            ""
        ]
        saved_count = 0
        for r in range(self.table.rowCount()):
            ja_item = self.table.item(r, 0)
            vi_item = self.table.item(r, 1)
            ja_text = ja_item.text().strip() if ja_item else ""
            vi_text = vi_item.text().strip() if vi_item else ""
            if ja_text and vi_text:
                lines.append(f"{ja_text} = {vi_text}")
                saved_count += 1

        self.config.glossary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        QMessageBox.information(
            self, "Glossary Saved",
            f"Successfully saved {saved_count} terminology pairs to {self.config.glossary_path.name}!"
        )
        self.accept()


class PromptDialog(QDialog):
    """Editor for config/prompt.txt translation template."""

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Prompt Template Editor")
        self.resize(650, 520)
        self._init_ui()
        self._load_prompt()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Customize the translation prompt. Must include the following placeholders:\n"
            "  • {GLOSSARY} : Injected terminology from glossary.txt\n"
            "  • {CONTEXT}  : Sliced tail context of the previous translated chunk\n"
            "  • {TEXT}     : Target Japanese chunk to translate"
        )
        info_label.setStyleSheet("color: #444; font-family: monospace; font-size: 11px;")
        layout.addWidget(info_label)

        self.editor = QPlainTextEdit()
        self.editor.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.editor)

        btn_layout = QHBoxLayout()
        self.reset_btn = QPushButton("Reset to Default")
        self.reset_btn.clicked.connect(self._reset_to_default)
        self.save_btn = QPushButton("Save to File")
        self.save_btn.clicked.connect(self._save_prompt)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _load_prompt(self):
        try:
            content = self.config.get_prompt_template()
            self.editor.setPlainText(content)
        except Exception:
            self.editor.setPlainText(DEFAULT_PROMPT_TEMPLATE)

    def _reset_to_default(self):
        confirm = QMessageBox.question(
            self, "Reset Prompt",
            "Are you sure you want to reset the prompt to default?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            self.editor.setPlainText(DEFAULT_PROMPT_TEMPLATE)

    def _save_prompt(self):
        content = self.editor.toPlainText().strip()
        for placeholder in ["{GLOSSARY}", "{CONTEXT}", "{TEXT}"]:
            if placeholder not in content:
                QMessageBox.warning(
                    self, "Missing Placeholder",
                    f"The prompt template must contain the placeholder: {placeholder}"
                )
                return

        self.config.prompt_path.write_text(content + "\n", encoding="utf-8")
        QMessageBox.information(self, "Prompt Saved", "Prompt template updated successfully!")
        self.accept()
