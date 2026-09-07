"""Main Window implementation for PySide6 GUI."""

import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QProgressBar, QTabWidget, QGroupBox,
    QMessageBox, QStatusBar, QSplitter, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QColor

from src.config import load_config, AppConfig
from src.translation.ollama_client import OllamaClient
from src.crawler.syosetu import SyosetuCrawler
from src.gui.widgets import (
    DropAreaWidget, ChapterTableWidget, RecentJobsWidget, LogViewerWidget
)
from src.gui.dialogs import SettingsDialog, GlossaryDialog, PromptDialog
from src.gui.workers import (
    CrawlWorker, NovelTranslationWorker, SingleDocTranslationWorker
)


class MainWindow(QMainWindow):
    """Main application window for Local Japanese -> Vietnamese Translator."""

    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config = config or load_config()
        self.active_worker = None
        self.current_novel_ncode: Optional[str] = None
        self.current_novel_title: Optional[str] = None
        self.selected_target_path: Optional[Path] = None

        self.setWindowTitle("Local Japanese -> Vietnamese Document & Novel Translator")
        self.resize(1000, 720)
        self.setMinimumSize(850, 600)

        self._init_ui()
        self._check_ollama_status()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # -------------------------------------------------------------
        # Top Bar: Ollama Status & Utility Buttons
        # -------------------------------------------------------------
        top_bar = QHBoxLayout()

        self.ollama_status_label = QLabel("Ollama: Checking...")
        self.ollama_status_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        top_bar.addWidget(self.ollama_status_label)

        self.check_ollama_btn = QPushButton("Check Ollama")
        self.check_ollama_btn.clicked.connect(self._check_ollama_status)
        top_bar.addWidget(self.check_ollama_btn)

        top_bar.addStretch()

        self.glossary_btn = QPushButton("📖 Glossary")
        self.glossary_btn.clicked.connect(self._open_glossary_dialog)
        top_bar.addWidget(self.glossary_btn)

        self.prompt_btn = QPushButton("📝 Prompt")
        self.prompt_btn.clicked.connect(self._open_prompt_dialog)
        top_bar.addWidget(self.prompt_btn)

        self.settings_btn = QPushButton("⚙ Settings")
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        top_bar.addWidget(self.settings_btn)

        main_layout.addLayout(top_bar)

        # -------------------------------------------------------------
        # Input Section (Two Types: Online Novel URL vs Local File)
        # -------------------------------------------------------------
        input_group = QGroupBox("Target Selection")
        input_layout = QVBoxLayout(input_group)

        # URL Input & Chapter Range
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Syosetu URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://ncode.syosetu.com/n1234ab/  or  n1234ab")
        url_layout.addWidget(self.url_input)

        url_layout.addWidget(QLabel("Từ ch:"))
        self.crawl_start_ch = QSpinBox()
        self.crawl_start_ch.setRange(0, 99999)
        self.crawl_start_ch.setValue(0)
        self.crawl_start_ch.setSpecialValueText("Đầu")
        self.crawl_start_ch.setToolTip("Chương bắt đầu (0 = từ đầu)")
        url_layout.addWidget(self.crawl_start_ch)

        url_layout.addWidget(QLabel("đến:"))
        self.crawl_end_ch = QSpinBox()
        self.crawl_end_ch.setRange(0, 99999)
        self.crawl_end_ch.setValue(0)
        self.crawl_end_ch.setSpecialValueText("Hết")
        self.crawl_end_ch.setToolTip("Chương kết thúc (0 = đến hết)")
        url_layout.addWidget(self.crawl_end_ch)

        self.crawl_btn = QPushButton("Crawl Only")
        self.crawl_btn.clicked.connect(self._on_crawl_clicked)
        url_layout.addWidget(self.crawl_btn)

        self.crawl_trans_btn = QPushButton("Crawl + Translate")
        self.crawl_trans_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.crawl_trans_btn.clicked.connect(self._on_crawl_translate_clicked)
        url_layout.addWidget(self.crawl_trans_btn)

        input_layout.addLayout(url_layout)

        # Local File Selector / Drop Area
        self.drop_area = DropAreaWidget()
        self.drop_area.file_selected.connect(self._on_local_file_selected)
        input_layout.addWidget(self.drop_area)

        # Selected local file indicator
        file_indicator_layout = QHBoxLayout()
        self.selected_target_label = QLabel("No local file selected.")
        self.selected_target_label.setStyleSheet("color: #666; font-style: italic;")
        file_indicator_layout.addWidget(self.selected_target_label)

        self.translate_file_btn = QPushButton("Translate Selected Document")
        self.translate_file_btn.setEnabled(False)
        self.translate_file_btn.clicked.connect(self._on_translate_local_file)
        file_indicator_layout.addWidget(self.translate_file_btn)

        input_layout.addLayout(file_indicator_layout)
        main_layout.addWidget(input_group)

        # -------------------------------------------------------------
        # Job Progress & Controls
        # -------------------------------------------------------------
        progress_group = QGroupBox("Job Progress & Controls")
        progress_layout = QVBoxLayout(progress_group)

        self.status_detail_label = QLabel("Status: Idle")
        self.status_detail_label.setStyleSheet("font-size: 13px; font-weight: 500;")
        progress_layout.addWidget(self.status_detail_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)

        # Control Buttons
        ctrl_layout = QHBoxLayout()
        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        ctrl_layout.addWidget(self.pause_btn)

        self.resume_btn = QPushButton("▶ Resume")
        self.resume_btn.setEnabled(False)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        ctrl_layout.addWidget(self.resume_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        ctrl_layout.addWidget(self.cancel_btn)

        ctrl_layout.addStretch()
        progress_layout.addLayout(ctrl_layout)
        main_layout.addWidget(progress_group)

        # -------------------------------------------------------------
        # Tabs: Novel Manager | Recent Jobs | Live Logs
        # -------------------------------------------------------------
        self.tabs = QTabWidget()

        # Tab 1: Novel Manager
        self.novel_manager_tab = QWidget()
        nm_layout = QVBoxLayout(self.novel_manager_tab)

        nm_top_layout = QHBoxLayout()
        self.novel_header_label = QLabel("No novel loaded.")
        self.novel_header_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        nm_top_layout.addWidget(self.novel_header_label)

        nm_top_layout.addStretch()

        self.delete_novel_btn = QPushButton("🗑 Xóa toàn bộ truyện này")
        self.delete_novel_btn.setEnabled(False)
        self.delete_novel_btn.setStyleSheet("color: #d32f2f; font-weight: bold;")
        self.delete_novel_btn.clicked.connect(self._on_delete_current_novel)
        nm_top_layout.addWidget(self.delete_novel_btn)

        nm_layout.addLayout(nm_top_layout)

        self.chapter_table = ChapterTableWidget()
        self.chapter_table.translate_requested.connect(self._on_translate_specific_chapters)
        self.chapter_table.delete_chapters_requested.connect(self._on_delete_chapters)
        nm_layout.addWidget(self.chapter_table)

        self.tabs.addTab(self.novel_manager_tab, "📚 Novel & Chapter Manager")

        # Tab 2: Recent Jobs
        self.recent_jobs_widget = RecentJobsWidget(
            cache_dir=self.config.cache_dir,
            input_dir=self.config.input_dir
        )
        self.recent_jobs_widget.job_opened.connect(self._on_open_recent_job)
        self.recent_jobs_widget.job_deleted.connect(self._on_delete_recent_job)
        self.tabs.addTab(self.recent_jobs_widget, "⏱ Recent Jobs")

        # Tab 3: Live Logs
        self.log_viewer = LogViewerWidget()
        self.tabs.addTab(self.log_viewer, "📋 Live Logs")

        main_layout.addWidget(self.tabs)

    # -------------------------------------------------------------
    # Ollama Diagnostics
    # -------------------------------------------------------------
    def _check_ollama_status(self):
        client = OllamaClient(
            host=self.config.ollama_host,
            model=self.config.ollama_model,
            timeout=5
        )
        if client.is_reachable():
            try:
                models = client.list_installed_models()
                if client.is_model_installed(self.config.ollama_model):
                    self.ollama_status_label.setText(
                        f"● Ollama: Connected ({self.config.ollama_model})"
                    )
                    self.ollama_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.ollama_status_label.setText(
                        f"● Ollama: Connected (Model '{self.config.ollama_model}' missing!)"
                    )
                    self.ollama_status_label.setStyleSheet("color: orange; font-weight: bold;")
            except Exception:
                self.ollama_status_label.setText("● Ollama: Reachable")
                self.ollama_status_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.ollama_status_label.setText(f"● Ollama: Offline ({self.config.ollama_host})")
            self.ollama_status_label.setStyleSheet("color: red; font-weight: bold;")

    # -------------------------------------------------------------
    # Dialog Openers
    # -------------------------------------------------------------
    def _open_settings_dialog(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec():
            self._check_ollama_status()
            self.log_viewer.append_log("INFO", "Settings updated successfully.")

    def _open_glossary_dialog(self):
        dlg = GlossaryDialog(self.config, self)
        dlg.exec()

    def _open_prompt_dialog(self):
        dlg = PromptDialog(self.config, self)
        dlg.exec()

    # -------------------------------------------------------------
    # Local File Selection
    # -------------------------------------------------------------
    def _on_local_file_selected(self, path_str: str):
        path = Path(path_str)
        self.selected_target_path = path
        if path.is_file():
            self.selected_target_label.setText(f"Selected Document: {path.name}")
            self.translate_file_btn.setEnabled(True)
            self.translate_file_btn.setText(f"Translate {path.name}")
        elif path.is_dir():
            # Check if novel folder
            if (path / "novel.json").exists():
                self._load_novel_into_ui(path.name)
            else:
                self.selected_target_label.setText(f"Selected Directory: {path.name}")
                self.translate_file_btn.setEnabled(True)

    def _on_translate_local_file(self):
        if not self.selected_target_path:
            return

        path = self.selected_target_path
        if path.is_dir():
            self._start_novel_translation(path.name)
        else:
            self._start_single_doc_translation(path)

    # -------------------------------------------------------------
    # Crawl Handlers
    # -------------------------------------------------------------
    def _on_crawl_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a Syosetu novel URL or ncode.")
            return

        start_ch = self.crawl_start_ch.value() if self.crawl_start_ch.value() > 0 else None
        end_ch = self.crawl_end_ch.value() if self.crawl_end_ch.value() > 0 else None
        self._start_crawl(url, auto_translate=False, start_chapter=start_ch, end_chapter=end_ch)

    def _on_crawl_translate_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a Syosetu novel URL or ncode.")
            return

        start_ch = self.crawl_start_ch.value() if self.crawl_start_ch.value() > 0 else None
        end_ch = self.crawl_end_ch.value() if self.crawl_end_ch.value() > 0 else None
        self._start_crawl(url, auto_translate=True, start_chapter=start_ch, end_chapter=end_ch)

    def _start_crawl(
        self,
        url: str,
        auto_translate: bool = False,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None
    ):
        self._set_job_running(True)
        self.progress_bar.setValue(0)
        self.tabs.setCurrentWidget(self.log_viewer)

        self.active_worker = CrawlWorker(
            url=url,
            config=self.config,
            start_chapter=start_chapter,
            end_chapter=end_chapter
        )
        self.active_worker.progress.connect(self._on_crawl_progress)
        self.active_worker.status_changed.connect(self.status_detail_label.setText)
        self.active_worker.log_message.connect(self.log_viewer.append_log)
        self.active_worker.finished.connect(
            lambda meta: self._on_crawl_finished(meta, auto_translate, start_chapter, end_chapter)
        )
        self.active_worker.error.connect(self._on_job_error)
        self.active_worker.start()

    def _on_crawl_progress(self, current: int, total: int, msg: str):
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(pct)
        self.status_detail_label.setText(f"Crawling: {current}/{total} - {msg}")

    def _on_crawl_finished(
        self,
        metadata: dict,
        auto_translate: bool,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None
    ):
        self._set_job_running(False)
        ncode = metadata.get("ncode")
        self.recent_jobs_widget.refresh_jobs()
        self._load_novel_into_ui(ncode)

        if auto_translate:
            self.log_viewer.append_log("INFO", f"Starting translation for crawled novel '{metadata.get('title')}'...")
            self._start_novel_translation(ncode, start_chapter=start_chapter, end_chapter=end_chapter)
        else:
            QMessageBox.information(
                self, "Crawl Completed",
                f"Successfully crawled '{metadata.get('title')}' ({metadata.get('chapter_count')} chapters)!"
            )

    # -------------------------------------------------------------
    # Translation Handlers
    # -------------------------------------------------------------
    def _start_novel_translation(
        self,
        ncode_or_dir: str,
        start_chapter: Optional[int] = None,
        end_chapter: Optional[int] = None,
        selected_chapters: Optional[List[int]] = None
    ):
        self._set_job_running(True)
        self.tabs.setCurrentWidget(self.novel_manager_tab)

        self.active_worker = NovelTranslationWorker(
            ncode_or_dir=ncode_or_dir,
            config=self.config,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            selected_chapters=selected_chapters
        )
        self.active_worker.chapter_progress.connect(self._on_novel_chapter_progress)
        self.active_worker.chunk_progress.connect(self._on_novel_chunk_progress)
        self.active_worker.overall_progress.connect(self._on_overall_progress)
        self.active_worker.status_changed.connect(self.status_detail_label.setText)
        self.active_worker.chapter_finished.connect(self._on_chapter_finished)
        self.active_worker.log_message.connect(self.log_viewer.append_log)
        self.active_worker.job_finished.connect(self._on_novel_translation_finished)
        self.active_worker.job_error.connect(self._on_job_error)
        self.active_worker.paused.connect(self._on_job_paused)
        self.active_worker.start()

    def _start_single_doc_translation(self, file_path: Path):
        self._set_job_running(True)
        self.tabs.setCurrentWidget(self.log_viewer)

        self.active_worker = SingleDocTranslationWorker(
            file_path=file_path,
            config=self.config
        )
        self.active_worker.chunk_progress.connect(lambda c, tot, chars: self.status_detail_label.setText(f"Translating chunk {c}/{tot} ({chars} chars)..."))
        self.active_worker.overall_progress.connect(self._on_overall_progress)
        self.active_worker.status_changed.connect(self.status_detail_label.setText)
        self.active_worker.log_message.connect(self.log_viewer.append_log)
        self.active_worker.job_finished.connect(self._on_single_doc_finished)
        self.active_worker.job_error.connect(self._on_job_error)
        self.active_worker.paused.connect(self._on_job_paused)
        self.active_worker.start()

    def _on_novel_chapter_progress(self, current: int, total: int, title: str):
        self.status_detail_label.setText(f"Translating: Chapter {current}/{total} - {title}")

    def _on_novel_chunk_progress(self, current: int, total: int, chars: int):
        self.status_detail_label.setText(f"Translating Chunk {current}/{total} ({chars} chars)...")

    def _on_overall_progress(self, percent: int, msg: str):
        self.progress_bar.setValue(percent)

    def _on_chapter_finished(self, ch_idx: int, out_path: str):
        # Refresh chapter table in UI
        if self.current_novel_ncode:
            self._load_novel_into_ui(self.current_novel_ncode)

    def _on_novel_translation_finished(self, summary: dict):
        self._set_job_running(False)
        self.recent_jobs_widget.refresh_jobs()
        if self.current_novel_ncode:
            self._load_novel_into_ui(self.current_novel_ncode)

        QMessageBox.information(
            self, "Novel Translation Completed",
            f"Novel '{summary.get('title')}' finished translating!\n"
            f"Output saved to: {summary.get('output_dir')}"
        )

    def _on_single_doc_finished(self, summary: dict):
        self._set_job_running(False)
        self.recent_jobs_widget.refresh_jobs()
        QMessageBox.information(
            self, "Document Translation Completed",
            f"Document translated successfully!\nOutput: {summary.get('output_file')}"
        )

    def _on_translate_specific_chapters(self, chapter_indices: list):
        if not self.current_novel_ncode:
            return
        self.log_viewer.append_log("INFO", f"Translating selected chapters: {chapter_indices}")
        self._start_novel_translation(self.current_novel_ncode, selected_chapters=chapter_indices)

    # -------------------------------------------------------------
    # Pause, Resume, Cancel Controls
    # -------------------------------------------------------------
    def _set_job_running(self, running: bool):
        self.crawl_btn.setEnabled(not running)
        self.crawl_trans_btn.setEnabled(not running)
        self.translate_file_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.resume_btn.setEnabled(False)
        self.cancel_btn.setEnabled(running)

    def _on_pause_clicked(self):
        if self.active_worker and hasattr(self.active_worker, "pause"):
            self.active_worker.pause()
            self.pause_btn.setEnabled(False)
            self.resume_btn.setEnabled(True)

    def _on_resume_clicked(self):
        if self.active_worker and hasattr(self.active_worker, "resume_translation"):
            self.active_worker.resume_translation()
            self.pause_btn.setEnabled(True)
            self.resume_btn.setEnabled(False)
            self.status_detail_label.setText("Resumed...")

    def _on_cancel_clicked(self):
        if self.active_worker:
            self.active_worker.cancel()
            self._set_job_running(False)
            self.status_detail_label.setText("Job Cancelled.")

    def _on_job_paused(self):
        self.status_detail_label.setText("Paused (safe point reached). Completed chunks saved.")

    def _on_job_error(self, err_msg: str):
        self._set_job_running(False)
        self.status_detail_label.setText("Job Failed.")
        QMessageBox.critical(self, "Job Error", f"An error occurred:\n{err_msg}")

    # -------------------------------------------------------------
    # Novel Details Loading
    # -------------------------------------------------------------
    def _load_novel_into_ui(self, ncode: str):
        self.current_novel_ncode = ncode.lower()
        novel_in_dir = self.config.input_dir / self.current_novel_ncode
        novel_json = novel_in_dir / "novel.json"

        title = self.current_novel_ncode
        if novel_json.exists():
            try:
                with open(novel_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    title = meta.get("title", title)
            except Exception:
                pass
        self.current_novel_title = title

        # Scan chapters
        chapters_in = novel_in_dir / "chapters"
        chapters_out = self.config.output_dir / self.current_novel_ncode / "chapters"
        from src.cache.novel_cache_manager import NovelCacheManager
        cache_mgr = NovelCacheManager(self.config.cache_dir, ncode=self.current_novel_ncode)

        chapter_rows = []
        if chapters_in.exists():
            for cf in sorted(chapters_in.glob("*.txt")):
                try:
                    num = int(cf.stem)
                except ValueError:
                    continue

                crawled = True
                translated = (chapters_out / cf.name).exists() and cache_mgr.is_chapter_translated(num)
                manifest = cache_mgr.load_chapter_manifest(num)
                failed = manifest is not None and manifest.status == "failed"
                ch_title = manifest.chapter_title if manifest else f"Chapter {num}"
                chunks_str = f"{manifest.completed_chunks}/{manifest.total_chunks}" if manifest and manifest.total_chunks > 0 else "-"

                chapter_rows.append({
                    "index": num,
                    "title": ch_title,
                    "crawled": crawled,
                    "translated": translated,
                    "failed": failed,
                    "chunks": chunks_str
                })

        self.novel_header_label.setText(
            f"Novel: {title} ({self.current_novel_ncode}) — {len(chapter_rows)} Chapter(s)"
        )
        self.delete_novel_btn.setEnabled(True)
        self.chapter_table.set_chapters(chapter_rows)
        self.tabs.setCurrentWidget(self.novel_manager_tab)

    def _on_open_recent_job(self, job_id_or_ncode: str, is_novel: bool):
        if is_novel:
            self._load_novel_into_ui(job_id_or_ncode)
        else:
            self._on_local_file_selected(job_id_or_ncode)

    def _on_delete_current_novel(self):
        if not self.current_novel_ncode:
            return
        self._delete_novel(self.current_novel_ncode)

    def _on_delete_recent_job(self, job_id: str, is_novel: bool):
        if is_novel:
            self._delete_novel(job_id)
        else:
            self._delete_single_doc_job(job_id)

    def _delete_novel(self, ncode: str):
        ncode = ncode.lower()
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(
                self, "Job Running",
                "Một tác vụ đang chạy. Vui lòng Tạm dừng (Pause) hoặc Hủy (Cancel) tác vụ trước khi xóa!"
            )
            return

        reply = QMessageBox.question(
            self, "Xác nhận xóa tiểu thuyết",
            f"Bạn có chắc chắn muốn xóa toàn bộ tiểu thuyết '{ncode}'?\n\n"
            f"Hành động này sẽ XÓA VĨNH VIỄN:\n"
            f"  • Thư mục bản gốc: input/{ncode}\n"
            f"  • Thư mục bản dịch: output/{ncode}\n"
            f"  • Bộ nhớ đệm: cache/novels/{ncode}\n\n"
            f"Thao tác này KHÔNG THỂ KHÔI PHỤC!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Perform deletion
        shutil.rmtree(self.config.input_dir / ncode, ignore_errors=True)
        shutil.rmtree(self.config.output_dir / ncode, ignore_errors=True)
        shutil.rmtree(self.config.cache_dir / "novels" / ncode, ignore_errors=True)

        self.log_viewer.append_log("INFO", f"Đã xóa hoàn toàn tiểu thuyết '{ncode}' (input, output, cache).")
        self.recent_jobs_widget.refresh_jobs()

        if self.current_novel_ncode == ncode:
            self.current_novel_ncode = None
            self.current_novel_title = None
            self.novel_header_label.setText("No novel loaded.")
            self.delete_novel_btn.setEnabled(False)
            self.chapter_table.set_chapters([])

        QMessageBox.information(self, "Đã xóa", f"Tiểu thuyết '{ncode}' đã được xóa hoàn toàn khỏi hệ thống.")

    def _delete_single_doc_job(self, file_path_str: str):
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(
                self, "Job Running",
                "Một tác vụ đang chạy. Vui lòng dừng tác vụ trước khi xóa!"
            )
            return

        reply = QMessageBox.question(
            self, "Xác nhận xóa tác vụ",
            f"Bạn có muốn xóa dữ liệu cache của tài liệu này?\n{file_path_str}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # Scan cache dirs for matching source_file
        if self.config.cache_dir.exists():
            for cdir in self.config.cache_dir.iterdir():
                if not cdir.is_dir() or cdir.name == "novels":
                    continue
                mf = cdir / "manifest.json"
                if mf.exists():
                    try:
                        with open(mf, "r", encoding="utf-8") as f:
                            m = json.load(f)
                            if m.get("source_file") == file_path_str:
                                shutil.rmtree(cdir, ignore_errors=True)
                    except Exception:
                        pass
        self.recent_jobs_widget.refresh_jobs()

    def _on_delete_chapters(self, indices: List[int], mode: str):
        if not self.current_novel_ncode:
            return
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.warning(
                self, "Job Running",
                "Một tác vụ đang chạy. Vui lòng dừng tác vụ trước khi xóa chương!"
            )
            return

        ncode = self.current_novel_ncode
        ch_count = len(indices)

        if mode == "translation_only":
            msg = (
                f"Bạn có chắc muốn xóa bản dịch của {ch_count} chương đã chọn?\n\n"
                f"Bản dịch trong output/{ncode}/chapters/ và cache dịch sẽ bị xóa.\n"
                f"Bản gốc trong input/{ncode}/chapters/ vẫn được GIỮ NGUYÊN để có thể dịch lại."
            )
        elif mode == "source_only":
            msg = (
                f"Bạn có chắc muốn xóa bản gốc của {ch_count} chương đã chọn?\n\n"
                f"File gốc trong input/{ncode}/chapters/ sẽ bị XÓA VĨNH VIỄN khỏi đĩa."
            )
        else:  # all
            msg = (
                f"Bạn có chắc muốn xóa HOÀN TOÀN {ch_count} chương đã chọn?\n\n"
                f"Hành động này sẽ XÓA VĨNH VIỄN:\n"
                f"  • File gốc trong input/{ncode}/chapters/\n"
                f"  • File bản dịch trong output/{ncode}/chapters/\n"
                f"  • Toàn bộ cache của các chương này."
            )

        reply = QMessageBox.question(
            self, "Xác nhận xóa chương", msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        from src.cache.novel_cache_manager import NovelCacheManager
        cache_mgr = NovelCacheManager(self.config.cache_dir, ncode=ncode)

        for idx in indices:
            # Delete source from input/
            if mode in ["source_only", "all"]:
                in_f = self.config.input_dir / ncode / "chapters" / f"{idx:04d}.txt"
                if in_f.exists():
                    try:
                        in_f.unlink()
                    except Exception:
                        pass

            # Delete translation from output/
            if mode in ["translation_only", "all"]:
                out_f = self.config.output_dir / ncode / "chapters" / f"{idx:04d}.txt"
                if out_f.exists():
                    try:
                        out_f.unlink()
                    except Exception:
                        pass

            # Update cache
            cache_mgr.delete_chapter_cache(idx, translation_only=(mode == "translation_only"))

        self.log_viewer.append_log("INFO", f"Đã xóa {ch_count} chương ({mode}) của novel '{ncode}'.")
        self._load_novel_into_ui(ncode)
        self.recent_jobs_widget.refresh_jobs()
        QMessageBox.information(self, "Đã xóa chương", f"Đã xóa thành công {ch_count} chương.")
