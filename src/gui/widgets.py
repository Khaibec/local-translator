"""Custom reusable widgets for PySide6 GUI."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QPlainTextEdit, QFrame, QProgressBar,
    QSpinBox, QMenu, QMessageBox, QTableWidgetSelectionRange
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QTextCursor, QColor

from src.models import ChapterManifest, NovelMetadata


class DropAreaWidget(QFrame):
    """File drag-and-drop zone and file picker."""

    file_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setStyleSheet("""
            DropAreaWidget {
                border: 2px dashed #999;
                border-radius: 8px;
                background-color: #fafafa;
                padding: 12px;
            }
            DropAreaWidget:hover {
                border-color: #2196F3;
                background-color: #f0f7ff;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.label = QLabel("Drag & Drop Japanese document here (.txt, .docx, .pdf)\n— OR —")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #666; font-size: 13px;")
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)

        self.select_file_btn = QPushButton("Select File...")
        self.select_file_btn.clicked.connect(self._on_select_file)
        btn_layout.addWidget(self.select_file_btn)

        self.select_folder_btn = QPushButton("Select Novel Folder...")
        self.select_folder_btn.clicked.connect(self._on_select_folder)
        btn_layout.addWidget(self.select_folder_btn)

        layout.addLayout(btn_layout)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path:
                self.file_selected.emit(file_path)

    def _on_select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Japanese Document",
            "", "Supported Documents (*.txt *.md *.docx *.pdf);;Text Files (*.txt *.md);;Word (*.docx);;PDF (*.pdf)"
        )
        if file_path:
            self.file_selected.emit(file_path)

    def _on_select_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Novel Directory")
        if dir_path:
            self.file_selected.emit(dir_path)


class ChapterTableWidget(QWidget):
    """Table showing chapters of a novel with status, chunk counts, filters, range selection, and deletion."""

    translate_requested = Signal(list)  # list of chapter indices
    delete_chapters_requested = Signal(list, str)  # (indices, delete_type: "translation_only" | "source_only" | "all")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chapters_data: List[Dict[str, Any]] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controls & Filter Bar
        ctrl_layout = QHBoxLayout()

        ctrl_layout.addWidget(QLabel("Lọc:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Completed", "Pending", "Failed"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        ctrl_layout.addWidget(self.filter_combo)

        ctrl_layout.addSpacing(10)
        ctrl_layout.addWidget(QLabel("Chọn từ ch:"))
        self.range_start_spin = QSpinBox()
        self.range_start_spin.setRange(0, 99999)
        self.range_start_spin.setValue(0)
        self.range_start_spin.setSpecialValueText("Đầu")
        ctrl_layout.addWidget(self.range_start_spin)

        ctrl_layout.addWidget(QLabel("đến:"))
        self.range_end_spin = QSpinBox()
        self.range_end_spin.setRange(0, 99999)
        self.range_end_spin.setValue(0)
        self.range_end_spin.setSpecialValueText("Hết")
        ctrl_layout.addWidget(self.range_end_spin)

        self.select_range_btn = QPushButton("Chọn")
        self.select_range_btn.clicked.connect(self._select_range)
        ctrl_layout.addWidget(self.select_range_btn)

        ctrl_layout.addStretch()

        self.translate_selected_btn = QPushButton("▶ Dịch chương đã chọn")
        self.translate_selected_btn.clicked.connect(self._on_translate_selected)
        ctrl_layout.addWidget(self.translate_selected_btn)

        # Delete Button with Menu
        self.delete_btn = QPushButton("🗑 Xóa chương...")
        delete_menu = QMenu(self)
        del_trans_action = delete_menu.addAction("Xóa bản dịch (Output + Cache)")
        del_trans_action.triggered.connect(lambda: self._on_delete_action("translation_only"))
        del_src_action = delete_menu.addAction("Xóa bản gốc (Input)")
        del_src_action.triggered.connect(lambda: self._on_delete_action("source_only"))
        del_all_action = delete_menu.addAction("Xóa hoàn toàn (Input + Output + Cache)")
        del_all_action.triggered.connect(lambda: self._on_delete_action("all"))
        self.delete_btn.setMenu(delete_menu)
        ctrl_layout.addWidget(self.delete_btn)

        layout.addLayout(ctrl_layout)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Title", "Crawl Status", "Translation Status", "Chunks"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.table)

    def set_chapters(self, chapters: List[Dict[str, Any]]):
        """Populate table with chapter records.

        Each dict: {'index': int, 'title': str, 'crawled': bool, 'translated': bool, 'failed': bool, 'chunks': str}
        """
        self._chapters_data = chapters
        self._populate_table()

    def _populate_table(self):
        self.table.setRowCount(0)
        filter_val = self.filter_combo.currentText()

        for ch in self._chapters_data:
            idx = ch.get("index", 1)
            title = ch.get("title", f"Chapter {idx}")
            crawled = ch.get("crawled", False)
            translated = ch.get("translated", False)
            failed = ch.get("failed", False)
            chunks = ch.get("chunks", "-")

            # Filter check
            if filter_val == "Completed" and not translated:
                continue
            if filter_val == "Pending" and (translated or failed):
                continue
            if filter_val == "Failed" and not failed:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            # Item 0: index
            idx_item = QTableWidgetItem(f"{idx:04d}")
            idx_item.setTextAlignment(Qt.AlignCenter)
            idx_item.setData(Qt.UserRole, idx)
            self.table.setItem(row, 0, idx_item)

            # Item 1: title
            self.table.setItem(row, 1, QTableWidgetItem(title))

            # Item 2: crawl status
            crawl_item = QTableWidgetItem("✓ Crawled" if crawled else "Pending")
            crawl_item.setTextAlignment(Qt.AlignCenter)
            crawl_item.setForeground(QColor("green") if crawled else QColor("gray"))
            self.table.setItem(row, 2, crawl_item)

            # Item 3: translation status
            if translated:
                trans_item = QTableWidgetItem("✓ Completed")
                trans_item.setForeground(QColor("green"))
            elif failed:
                trans_item = QTableWidgetItem("✗ Failed")
                trans_item.setForeground(QColor("red"))
            else:
                trans_item = QTableWidgetItem("Pending")
                trans_item.setForeground(QColor("gray"))
            trans_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, trans_item)

            # Item 4: chunks
            chunk_item = QTableWidgetItem(str(chunks))
            chunk_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, chunk_item)

    def _apply_filter(self):
        self._populate_table()

    def _select_range(self):
        start = self.range_start_spin.value()
        end = self.range_end_spin.value()
        self.table.clearSelection()
        col_count = self.table.columnCount()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                ch_idx = item.data(Qt.UserRole)
                if (start == 0 or ch_idx >= start) and (end == 0 or ch_idx <= end):
                    self.table.setRangeSelected(
                        QTableWidgetSelectionRange(r, 0, r, col_count - 1),
                        True
                    )

    def _get_selected_indices(self) -> List[int]:
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()))
        selected_indices = []
        for r in selected_rows:
            item = self.table.item(r, 0)
            if item:
                selected_indices.append(item.data(Qt.UserRole))
        return selected_indices

    def _on_translate_selected(self):
        selected_indices = self._get_selected_indices()
        if selected_indices:
            self.translate_requested.emit(selected_indices)

    def _on_delete_action(self, mode: str):
        indices = self._get_selected_indices()
        if indices:
            self.delete_chapters_requested.emit(indices, mode)

    def _show_context_menu(self, pos):
        indices = self._get_selected_indices()
        if not indices:
            return

        menu = QMenu(self)
        action_trans = menu.addAction(f"▶ Dịch {len(indices)} chương đã chọn")
        action_trans.triggered.connect(self._on_translate_selected)
        menu.addSeparator()
        action_del_trans = menu.addAction("🗑 Xóa bản dịch (Output + Cache)")
        action_del_trans.triggered.connect(lambda: self._on_delete_action("translation_only"))
        action_del_src = menu.addAction("🗑 Xóa bản gốc (Input)")
        action_del_src.triggered.connect(lambda: self._on_delete_action("source_only"))
        action_del_all = menu.addAction("🗑 Xóa hoàn toàn (Input + Output + Cache)")
        action_del_all.triggered.connect(lambda: self._on_delete_action("all"))

        menu.exec(self.table.viewport().mapToGlobal(pos))


class RecentJobsWidget(QWidget):
    """Scans and lists recent translation jobs from the filesystem cache."""

    job_opened = Signal(str, bool)  # (identifier, is_novel)
    job_deleted = Signal(str, bool)  # (identifier, is_novel)

    def __init__(self, cache_dir: Path, input_dir: Path, parent=None):
        super().__init__(parent)
        self.cache_dir = Path(cache_dir)
        self.input_dir = Path(input_dir)
        self._init_ui()
        self.refresh_jobs()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Recent Translation & Crawl Jobs (from local cache):"))
        top_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self.refresh_jobs)
        top_layout.addWidget(self.refresh_btn)

        self.open_btn = QPushButton("Open Selected Job")
        self.open_btn.clicked.connect(self._on_open_job)
        top_layout.addWidget(self.open_btn)

        self.delete_btn = QPushButton("🗑 Delete Selected Job")
        self.delete_btn.clicked.connect(self._on_delete_job)
        top_layout.addWidget(self.delete_btn)

        layout.addLayout(top_layout)

        # Jobs Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name / Title", "Type / Ncode", "Progress", "Status", "Last Updated"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.doubleClicked.connect(self._on_open_job)
        layout.addWidget(self.table)

    def refresh_jobs(self):
        """Scan cache directory for novels and single document jobs."""
        self.table.setRowCount(0)
        jobs = []

        # 1. Scan Novel Jobs (cache/novels/<ncode>)
        novels_dir = self.cache_dir / "novels"
        if novels_dir.exists():
            for ndir in novels_dir.iterdir():
                if not ndir.is_dir():
                    continue
                manifest_file = ndir / "manifest.json"
                novel_meta_file = self.input_dir / ndir.name / "novel.json"

                title = ndir.name
                if novel_meta_file.exists():
                    try:
                        with open(novel_meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            title = data.get("title", ndir.name)
                    except Exception:
                        pass

                total_chs = 0
                translated_chs = 0
                status = "In Progress"
                updated_at = "-"

                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            m = json.load(f)
                            if title == ndir.name and "title" in m:
                                title = m.get("title", title)
                            total_chs = m.get("total_chapters", 0)
                            translated_chs = m.get("translated_chapters", 0)
                            updated_at = m.get("updated_at", "-")[:19].replace("T", " ")
                            if translated_chs >= total_chs and total_chs > 0:
                                status = "Completed"
                            elif m.get("translation_status") == "failed":
                                status = "Failed"
                    except Exception:
                        pass

                progress_str = f"{translated_chs} / {total_chs} chapters"
                jobs.append({
                    "name": title,
                    "id": ndir.name,
                    "is_novel": True,
                    "progress": progress_str,
                    "status": status,
                    "updated_at": updated_at
                })

        # 2. Scan Single Doc Jobs (cache/<job_id>/manifest.json)
        if self.cache_dir.exists():
            for cdir in self.cache_dir.iterdir():
                if not cdir.is_dir() or cdir.name == "novels":
                    continue
                manifest_file = cdir / "manifest.json"
                if manifest_file.exists():
                    try:
                        with open(manifest_file, "r", encoding="utf-8") as f:
                            m = json.load(f)
                            src = m.get("source_file", cdir.name)
                            total = m.get("total_chunks", 0)
                            completed = m.get("completed_chunks", 0)
                            stat = "Completed" if completed >= total and total > 0 else m.get("status", "In Progress").title()
                            upd = m.get("updated_at", "-")[:19].replace("T", " ")
                            jobs.append({
                                "name": Path(src).name,
                                "id": src,
                                "is_novel": False,
                                "progress": f"{completed} / {total} chunks",
                                "status": stat,
                                "updated_at": upd
                            })
                    except Exception:
                        pass

        # Sort jobs by updated_at descending
        jobs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        for j in jobs:
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(j["name"])
            name_item.setData(Qt.UserRole, (j["id"], j["is_novel"]))
            self.table.setItem(row, 0, name_item)

            type_item = QTableWidgetItem(f"Novel ({j['id']})" if j["is_novel"] else "Document")
            self.table.setItem(row, 1, type_item)

            self.table.setItem(row, 2, QTableWidgetItem(j["progress"]))

            status_item = QTableWidgetItem(j["status"])
            if j["status"] == "Completed":
                status_item.setForeground(QColor("green"))
            elif j["status"] == "Failed":
                status_item.setForeground(QColor("red"))
            self.table.setItem(row, 3, status_item)

            self.table.setItem(row, 4, QTableWidgetItem(j["updated_at"]))

    def _on_open_job(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                job_id, is_novel = item.data(Qt.UserRole)
                self.job_opened.emit(job_id, is_novel)

    def _on_delete_job(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                job_id, is_novel = item.data(Qt.UserRole)
                self.job_deleted.emit(job_id, is_novel)


class LogViewerWidget(QWidget):
    """Console-style log output viewer with auto-scroll and file export."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Log text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.text_edit)

        # Controls
        ctrl_layout = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Console")
        self.clear_btn.clicked.connect(self.text_edit.clear)
        ctrl_layout.addWidget(self.clear_btn)

        self.save_btn = QPushButton("Save Log to File...")
        self.save_btn.clicked.connect(self._save_log)
        ctrl_layout.addWidget(self.save_btn)

        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

    def append_log(self, level: str, message: str):
        """Append a log line with timestamp and level prefix."""
        color = "#d4d4d4"
        if level == "WARNING":
            color = "#ffb74d"
        elif level == "ERROR":
            color = "#e57373"
        elif level == "INFO":
            color = "#81c784"

        html_line = f'<span style="color: {color};">[{level}] {message}</span>'
        self.text_edit.appendHtml(html_line)
        self.text_edit.moveCursor(QTextCursor.End)

    def clear(self):
        """Clear the console log."""
        self.text_edit.clear()

    def _save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Logs", "translator.log", "Log Files (*.log *.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.text_edit.toPlainText())
