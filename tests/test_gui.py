"""Unit and headless integration tests for GUI components, dialogs, and widgets."""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Configure offscreen Qt platform before creating any Qt objects
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.config import AppConfig
from src.gui.dialogs import SettingsDialog, GlossaryDialog, PromptDialog
from src.gui.widgets import (
    DropAreaWidget,
    ChapterTableWidget,
    RecentJobsWidget,
    LogViewerWidget,
)
from src.gui.main_window import MainWindow
from src.gui.workers import CrawlWorker, NovelTranslationWorker, SingleDocTranslationWorker
from src.document.reader import PdfReader, get_reader


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QApplication instance exists for the entire test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_config(tmp_path):
    """Create a temporary AppConfig with isolated directories and config files."""
    proj_dir = tmp_path / "proj"
    config_dir = proj_dir / "config"
    input_dir = proj_dir / "input"
    output_dir = proj_dir / "output"
    cache_dir = proj_dir / "cache"
    logs_dir = proj_dir / "logs"

    config_dir.mkdir(parents=True)
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    # Initial files
    prompt_file = config_dir / "prompt.txt"
    prompt_file.write_text(
        "GLOSSARY:\n{GLOSSARY}\nCONTEXT:\n{CONTEXT}\nTEXT:\n{TEXT}\nOUTPUT:",
        encoding="utf-8"
    )

    glossary_file = config_dir / "glossary.txt"
    glossary_file.write_text(
        "冒険者 = mạo hiểm giả\n魔法 = ma pháp\n",
        encoding="utf-8"
    )

    settings_file = config_dir / "settings.yaml"
    settings_yaml = f"""
ollama:
  host: "http://localhost:11434"
  model: "translategemma:4b"
  timeout_seconds: 600

translation:
  source_language: "Japanese"
  target_language: "Vietnamese"
  chunk_size: 1800
  context_size: 600
  temperature: 0.1
  max_retries: 3
  retry_backoff: 2.0
  continue_on_error: false
  concurrency: 1

crawler:
  timeout_seconds: 30
  max_retries: 3
  delay_seconds: 1.0
  user_agent: "Mozilla/5.0"

paths:
  input_dir: "{input_dir}"
  output_dir: "{output_dir}"
  cache_dir: "{cache_dir}"
  logs_dir: "{logs_dir}"
  prompt_path: "{prompt_file}"
  glossary_path: "{glossary_file}"
"""
    settings_file.write_text(settings_yaml, encoding="utf-8")

    return AppConfig(project_root=proj_dir, settings_path=settings_file)


# =====================================================================
# 1. Dialog Tests
# =====================================================================

def test_settings_dialog_load_and_save(qapp, mock_config):
    """Test that SettingsDialog loads existing values and writes back changes."""
    dialog = SettingsDialog(mock_config)
    assert dialog.host_input.text() == "http://localhost:11434"
    assert dialog.model_input.text() == "translategemma:4b"
    assert dialog.chunk_size_input.value() == 1800

    # Modify values
    dialog.host_input.setText("http://127.0.0.1:11435")
    dialog.model_input.setText("custom-model:latest")
    dialog.chunk_size_input.setValue(2000)
    dialog.temperature_input.setValue(0.2)

    dialog._save_settings()

    assert mock_config.ollama_host == "http://127.0.0.1:11435"
    assert mock_config.ollama_model == "custom-model:latest"
    assert mock_config.chunk_size == 2000
    assert mock_config.temperature == 0.2
    assert mock_config.settings_path.exists()


def test_glossary_dialog_edit_and_filter(qapp, mock_config):
    """Test GlossaryDialog loading, searching, adding, and saving entries."""
    dialog = GlossaryDialog(mock_config)

    # Initially 2 entries
    assert dialog.table.rowCount() == 2

    # Test search filter
    dialog.search_input.setText("冒険者")
    assert not dialog.table.isRowHidden(0)
    assert dialog.table.isRowHidden(1)

    # Clear filter
    dialog.search_input.setText("")
    assert not dialog.table.isRowHidden(1)

    # Add a new row
    dialog._add_row()
    row_idx = dialog.table.rowCount() - 1
    dialog.table.item(row_idx, 0).setText("剣士")
    dialog.table.item(row_idx, 1).setText("kiếm sĩ")
    assert dialog.table.rowCount() == 3

    # Save
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        dialog._save_glossary()

    glossary_saved = mock_config.glossary_path.read_text(encoding="utf-8")
    assert "剣士 = kiếm sĩ" in glossary_saved
    assert "冒険者 = mạo hiểm giả" in glossary_saved


def test_prompt_dialog_validation(qapp, mock_config):
    """Test PromptDialog placeholder validation and save."""
    dialog = PromptDialog(mock_config)
    assert "{TEXT}" in dialog.editor.toPlainText()

    # Intentionally remove required placeholder
    dialog.editor.setPlainText("Invalid prompt without placeholders.")
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        dialog._save_prompt()
        mock_warn.assert_called_once()

    # Valid prompt
    valid_prompt = "Valid: {GLOSSARY} and {CONTEXT} and {TEXT}"
    dialog.editor.setPlainText(valid_prompt)
    with patch("PySide6.QtWidgets.QMessageBox.information"):
        dialog._save_prompt()
    assert mock_config.prompt_path.read_text(encoding="utf-8").strip() == valid_prompt


# =====================================================================
# 2. Custom Widgets Tests
# =====================================================================

def test_chapter_table_filtering(qapp):
    """Test ChapterTableWidget row population and status filter."""
    table = ChapterTableWidget()
    chapters = [
        {"index": 1, "title": "Ch 1", "crawled": True, "translated": True, "failed": False, "chunks": "3/3"},
        {"index": 2, "title": "Ch 2", "crawled": True, "translated": False, "failed": False, "chunks": "0/4"},
        {"index": 3, "title": "Ch 3", "crawled": True, "translated": False, "failed": True, "chunks": "1/3"},
    ]
    table.set_chapters(chapters)
    assert table.table.rowCount() == 3

    # Filter: Completed
    table.filter_combo.setCurrentText("Completed")
    assert table.table.rowCount() == 1
    assert table.table.item(0, 1).text() == "Ch 1"

    # Filter: Pending
    table.filter_combo.setCurrentText("Pending")
    assert table.table.rowCount() == 1
    assert table.table.item(0, 1).text() == "Ch 2"

    # Filter: Failed
    table.filter_combo.setCurrentText("Failed")
    assert table.table.rowCount() == 1
    assert table.table.item(0, 1).text() == "Ch 3"

    # Filter: All
    table.filter_combo.setCurrentText("All")
    assert table.table.rowCount() == 3


def test_recent_jobs_widget_refresh(qapp, mock_config):
    """Test RecentJobsWidget scanning cached novels and document jobs."""
    widget = RecentJobsWidget(cache_dir=mock_config.cache_dir, input_dir=mock_config.input_dir)

    # Create dummy novel in cache
    novel_cache = mock_config.cache_dir / "novels" / "n9999ab"
    novel_cache.mkdir(parents=True)
    manifest = {
        "ncode": "n9999ab",
        "title": "Test Novel",
        "total_chapters": 10,
        "translated_chapters": 5,
        "status": "in_progress",
        "updated_at": "2026-09-07T10:00:00"
    }
    (novel_cache / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    widget.refresh_jobs()
    assert widget.table.rowCount() == 1
    assert "Test Novel" in widget.table.item(0, 0).text()
    assert "Novel (n9999ab)" in widget.table.item(0, 1).text()
    assert "5 / 10 chapters" in widget.table.item(0, 2).text()


def test_log_viewer_widget(qapp):
    """Test LogViewerWidget appending logs with proper HTML formatting."""
    viewer = LogViewerWidget()
    viewer.append_log("INFO", "Test info message")
    viewer.append_log("WARNING", "Test warning message")
    viewer.append_log("ERROR", "Test error message")

    text = viewer.text_edit.toPlainText()
    assert "Test info message" in text
    assert "Test warning message" in text
    assert "Test error message" in text

    viewer.clear()
    assert viewer.text_edit.toPlainText() == ""


# =====================================================================
# 3. Main Window Tests
# =====================================================================

def test_main_window_init_and_local_selection(qapp, mock_config, tmp_path):
    """Test MainWindow initialization and target file selection."""
    with patch.object(MainWindow, "_check_ollama_status"):
        window = MainWindow(config=mock_config)
        assert "Local Japanese -> Vietnamese" in window.windowTitle()

        # Test selecting a single document file
        dummy_file = tmp_path / "test_doc.txt"
        dummy_file.write_text("これはテストです。", encoding="utf-8")

        window._on_local_file_selected(str(dummy_file))
        assert window.selected_target_path == dummy_file
        assert window.translate_file_btn.isEnabled()
        assert "test_doc.txt" in window.translate_file_btn.text()


# =====================================================================
# 4. Worker Flag & Control Tests
# =====================================================================

def test_novel_worker_pause_resume_cancel(qapp, mock_config):
    """Test safe pause, resume, and cancel flag toggles in NovelTranslationWorker."""
    worker = NovelTranslationWorker(ncode_or_dir="n1234ab", config=mock_config)
    assert not worker._pause_requested
    assert not worker._cancel_requested

    worker.pause()
    assert worker._pause_requested

    worker.resume_translation()
    assert not worker._pause_requested

    worker.cancel()
    assert worker._cancel_requested


def test_single_doc_worker_pause_resume_cancel(qapp, mock_config, tmp_path):
    """Test safe pause, resume, and cancel flag toggles in SingleDocTranslationWorker."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello", encoding="utf-8")

    worker = SingleDocTranslationWorker(file_path=test_file, config=mock_config)
    assert not worker._pause_requested
    assert not worker._cancel_requested

    worker.pause()
    assert worker._pause_requested

    worker.resume_translation()
    assert not worker._pause_requested

    worker.cancel()
    assert worker._cancel_requested


# =====================================================================
# 5. Document Reader: PDF Support Tests
# =====================================================================

def test_pdf_reader_factory():
    """Test get_reader factory for .pdf files."""
    reader = get_reader(Path("example.pdf"))
    assert isinstance(reader, PdfReader)


def test_pdf_reader_extraction(tmp_path):
    """Test PdfReader extracting text via mocked pypdf.PdfReader."""
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")

    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "第一章 始まり\nこれは日本語のテストです。"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "第二章 冒険\n次のページです。"

    with patch("pypdf.PdfReader") as mock_pdf_cls:
        mock_instance = MagicMock()
        mock_instance.pages = [mock_page1, mock_page2]
        mock_pdf_cls.return_value = mock_instance

        reader = PdfReader()
        content = reader.read(pdf_file)

        assert "第一章 始まり" in content
        assert "第二章 冒険" in content
        assert "次のページです。" in content


# =====================================================================
# 6. Chapter Range & Deletion Tests
# =====================================================================

def test_chapter_table_range_selection_and_signals(qapp):
    """Test range selection (start..end) and delete signals in ChapterTableWidget."""
    table = ChapterTableWidget()
    chapters = [
        {"index": i, "title": f"Ch {i}", "crawled": True, "translated": False, "failed": False, "chunks": "-"}
        for i in range(1, 6)
    ]
    table.set_chapters(chapters)
    assert table.table.rowCount() == 5

    # Select range 2..4
    table.range_start_spin.setValue(2)
    table.range_end_spin.setValue(4)
    table._select_range()

    selected = table._get_selected_indices()
    assert selected == [2, 3, 4]

    # Test delete signal emission
    received = []
    table.delete_chapters_requested.connect(lambda indices, mode: received.append((indices, mode)))
    table._on_delete_action("source_only")

    assert len(received) == 1
    assert received[0] == ([2, 3, 4], "source_only")


def test_main_window_delete_entire_novel(qapp, mock_config):
    """Test deleting entire novel removes folders from input, output, and cache."""
    ncode = "n8888xx"
    novel_in = mock_config.input_dir / ncode
    novel_out = mock_config.output_dir / ncode
    novel_cache = mock_config.cache_dir / "novels" / ncode

    (novel_in / "chapters").mkdir(parents=True)
    (novel_in / "novel.json").write_text('{"title": "Test"}', encoding="utf-8")
    (novel_in / "chapters" / "0001.txt").write_text("Ch 1 text", encoding="utf-8")

    (novel_out / "chapters").mkdir(parents=True)
    (novel_out / "chapters" / "0001.txt").write_text("Ch 1 vi", encoding="utf-8")

    novel_cache.mkdir(parents=True)
    (novel_cache / "manifest.json").write_text('{}', encoding="utf-8")

    with patch.object(MainWindow, "_check_ollama_status"):
        window = MainWindow(config=mock_config)
        window.current_novel_ncode = ncode

        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=pytest.importorskip("PySide6.QtWidgets").QMessageBox.Yes), \
             patch("PySide6.QtWidgets.QMessageBox.information"):
            window._delete_novel(ncode)

        # Assert all directories were deleted, especially the input folder
        assert not novel_in.exists()
        assert not novel_out.exists()
        assert not novel_cache.exists()
        assert window.current_novel_ncode is None


def test_main_window_delete_chapters(qapp, mock_config):
    """Test deleting specific chapters from input and output directories."""
    ncode = "n7777yy"
    novel_in = mock_config.input_dir / ncode / "chapters"
    novel_out = mock_config.output_dir / ncode / "chapters"
    novel_in.mkdir(parents=True)
    novel_out.mkdir(parents=True)

    # Chapters 1 and 2
    (novel_in / "0001.txt").write_text("Ch 1 ja", encoding="utf-8")
    (novel_in / "0002.txt").write_text("Ch 2 ja", encoding="utf-8")
    (novel_out / "0001.txt").write_text("Ch 1 vi", encoding="utf-8")
    (novel_out / "0002.txt").write_text("Ch 2 vi", encoding="utf-8")

    with patch.object(MainWindow, "_check_ollama_status"):
        window = MainWindow(config=mock_config)
        window.current_novel_ncode = ncode

        # 1. Delete chapter 1 translation only (keeps input file)
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=pytest.importorskip("PySide6.QtWidgets").QMessageBox.Yes), \
             patch("PySide6.QtWidgets.QMessageBox.information"):
            window._on_delete_chapters([1], mode="translation_only")

        assert (novel_in / "0001.txt").exists()  # Input preserved
        assert not (novel_out / "0001.txt").exists()  # Output deleted

        # 2. Delete chapter 2 completely (both input and output)
        with patch("PySide6.QtWidgets.QMessageBox.question", return_value=pytest.importorskip("PySide6.QtWidgets").QMessageBox.Yes), \
             patch("PySide6.QtWidgets.QMessageBox.information"):
            window._on_delete_chapters([2], mode="all")

        assert not (novel_in / "0002.txt").exists()  # Input deleted
        assert not (novel_out / "0002.txt").exists()  # Output deleted


def test_crawl_worker_range_filtering(qapp, mock_config):
    """Test CrawlWorker only downloads chapters within [start_chapter, end_chapter]."""
    from src.models import NovelMetadata, ChapterItem

    worker = CrawlWorker(
        url="https://ncode.syosetu.com/n1234ab/",
        config=mock_config,
        start_chapter=2,
        end_chapter=3
    )

    mock_meta = NovelMetadata(
        ncode="n1234ab",
        title="Range Test Novel",
        source_url="https://ncode.syosetu.com/n1234ab/",
        chapter_count=4,
        crawler="syosetu"
    )
    mock_items = [
        ChapterItem(index=i, title=f"Ch {i}", url=f"https://ncode.syosetu.com/n1234ab/{i}/")
        for i in range(1, 5)
    ]

    mock_crawler = MagicMock()
    mock_crawler.discover_chapters.return_value = (mock_meta, mock_items)
    mock_crawler.fetch_chapter.return_value = ("Ch Title", "Japanese Content")

    with patch("src.gui.workers.get_crawler_for_url", return_value=mock_crawler):
        worker.run()

    chapters_dir = mock_config.input_dir / "n1234ab" / "chapters"
    assert not (chapters_dir / "0001.txt").exists()
    assert (chapters_dir / "0002.txt").exists()
    assert (chapters_dir / "0003.txt").exists()
    assert not (chapters_dir / "0004.txt").exists()


def test_novel_worker_range_filtering(qapp, mock_config):
    """Test NovelTranslationWorker only translates chapters within [start_chapter, end_chapter]."""
    ncode = "n3333zz"
    in_chapters = mock_config.input_dir / ncode / "chapters"
    in_chapters.mkdir(parents=True)
    (mock_config.input_dir / ncode / "novel.json").write_text(
        json.dumps({"ncode": ncode, "title": "Test Range", "source_url": "", "chapter_count": 3, "crawler": "syosetu"}),
        encoding="utf-8"
    )

    for i in range(1, 4):
        (in_chapters / f"{i:04d}.txt").write_text(f"Chapter {i} Japanese text.", encoding="utf-8")

    worker = NovelTranslationWorker(
        ncode_or_dir=ncode,
        config=mock_config,
        start_chapter=2,
        end_chapter=2
    )

    with patch("src.gui.workers.OllamaClient") as mock_client_cls, \
         patch("src.gui.workers.Translator") as mock_trans_cls:
        mock_client = MagicMock()
        mock_client.model = "translategemma:4b"
        mock_client_cls.return_value = mock_client

        mock_translator = MagicMock()
        mock_translator.translate_chunk.return_value = ("Bản dịch tiếng Việt chương 2", [])
        mock_trans_cls.return_value = mock_translator

        worker.run()

    out_chapters = mock_config.output_dir / ncode / "chapters"
    assert not (out_chapters / "0001.txt").exists()
    assert (out_chapters / "0002.txt").exists()
    assert not (out_chapters / "0003.txt").exists()


