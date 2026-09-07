"""Tests for document readers and writers."""

import tempfile
import unittest
from pathlib import Path
from src.document.reader import TxtReader, DocxReader, get_reader
from src.document.writer import TxtWriter, DocxWriter, get_writer


class TestDocumentIO(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_txt_reader_and_writer(self):
        file_path = self.dir_path / "sample.txt"
        writer = TxtWriter()
        content = "段落一\n\n段落二"
        writer.write(file_path, content)

        self.assertTrue(file_path.exists())
        reader = TxtReader()
        read_back = reader.read(file_path)
        self.assertEqual(read_back, content)

    def test_docx_reader_and_writer(self):
        docx_path = self.dir_path / "sample.docx"
        writer = DocxWriter()
        content = "段落一：人工知能の発展\n\n段落二：機械学習の応用"
        writer.write(docx_path, content)

        self.assertTrue(docx_path.exists())
        reader = DocxReader()
        read_back = reader.read(docx_path)
        self.assertIn("段落一：人工知能の発展", read_back)
        self.assertIn("段落二：機械学習の応用", read_back)

    def test_get_reader_and_writer_factories(self):
        txt_p = Path("test.txt")
        docx_p = Path("test.docx")
        md_p = Path("test.md")

        self.assertIsInstance(get_reader(txt_p), TxtReader)
        self.assertIsInstance(get_reader(docx_p), DocxReader)
        self.assertIsInstance(get_reader(md_p), TxtReader)

        self.assertIsInstance(get_writer(txt_p), TxtWriter)
        self.assertIsInstance(get_writer(docx_p), DocxWriter)

    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            get_reader(Path("test.pdf"))


if __name__ == "__main__":
    unittest.main()
