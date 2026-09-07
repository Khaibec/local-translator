# Local Japanese → Vietnamese Document & Web Novel Translation Pipeline

Hệ thống dịch thuật tài liệu và tiểu thuyết mạng tiếng Nhật (Syosetu) sang tiếng Việt cục bộ (Local Translation Pipeline) chất lượng cao, chạy hoàn toàn offline trên Windows sử dụng **Ollama** và mô hình chuyên dụng **TranslateGemma 4B** của Google.

Hệ thống cung cấp cả giao diện đồ họa trực quan **PySide6 Desktop GUI** lẫn **CLI dòng lệnh** mạnh mẽ, không giới hạn số lượng ký tự, không phụ thuộc bất kỳ dịch vụ cloud API nào (OpenAI, Google Cloud, DeepL), bảo vệ toàn vẹn quyền riêng tư dữ liệu và được tối ưu hóa đặc biệt cho máy tính CPU-only với 16 GB RAM.

---

## 1. Tính năng nổi bật

### Giai đoạn 1 (Phase 1): Dịch tài liệu đơn lẻ
- **Chạy hoàn toàn cục bộ (100% Offline/Local)**: Kết nối Ollama HTTP API trên máy cá nhân, không tốn chi phí token, không rò rỉ dữ liệu.
- **Dịch tài liệu dài không giới hạn**: Tự động chia nhỏ tài liệu theo cấu trúc đoạn văn bản và câu tiếng Nhật (`。`, `！`, `？`, `\n\n`), không bao giờ cắt đôi từ vựng.
- **Bộ nhớ đệm thông minh & Tự động Resume**: Mỗi chunk sau khi dịch được lưu ngay lập tức vào ổ đĩa kèm mã băm SHA-256. Nếu quá trình dịch bị gián đoạn (mất điện, tắt máy, lỗi mạng), chạy lại sẽ tự động tiếp tục từ chunk chưa dịch.
- **Bảo toàn ngữ cảnh liền mạch (Context Continuity)**: Tự động truyền một đoạn ngữ cảnh ngắn (mặc định 600 ký tự tiếng Việt vừa dịch) sang chunk kế tiếp để duy trì sự nhất quán về đại từ nhân xưng, tên riêng và văn phong.
- **Bảng thuật ngữ chuyên ngành (Glossary)**: Tùy biến từ điển đối chiếu Nhật - Việt trong `config/glossary.txt`.
- **Kiểm soát chất lượng bản dịch (Quality Safeguards)**: Tự động phát hiện và loại bỏ code fences thừa (````vietnamese ... ````), tiền tố đàm thoại ("Dưới đây là bản dịch:"), cảnh báo lặp từ vô tận hoặc bản dịch rỗng.
- **Hỗ trợ đa định dạng**: Đọc/ghi cả văn bản thuần `.txt`, `.md`, tài liệu Word `.docx`, và tài liệu PDF `.pdf` (text-based).

### Giai đoạn 2 (Phase 2): Crawler tiểu thuyết mạng & Pipeline theo Chương/Chunk
- **Crawl tự động từ Syosetu (ncode.syosetu.com)**: Tự động nhận diện tiêu đề, danh sách chương (bao gồm cả phân trang nhiều trang `?p=1`, `?p=2` và truyện ngắn tanpen 1 chương).
- **Trích xuất văn bản sạch sẽ**: Tự động gỡ bỏ thẻ chú âm furigana (`<rp>`, `<rt>`) để giữ kanji nguyên bản, loại bỏ mã HTML, chỉ giữ lại văn bản tiếng Nhật sạch.
- **Thu thập lịch sự & có trách nhiệm (Polite Rate Limiting)**: Khoảng nghỉ có thể tùy biến (mặc định 1.0 giây) giữa các yêu cầu, kèm cơ chế thử lại hàm mũ (exponential backoff retry).
- **Cấu trúc dữ liệu 3 cấp**: `Novel` → `Chapter` → `Chunk`.
- **Cơ chế Resume 2 cấp độ**:
  - **Cấp độ Crawl**: Không tải lại các chương đã tải đầy đủ và toàn vẹn.
  - **Cấp độ Dịch**: Nếu dịch đến Chương 25 Chunk 17 bị lỗi, khi chạy lại chương trình sẽ tự động bỏ qua toàn bộ Chương 1 đến 24 và Chương 25 Chunk 1 đến 16, tiếp tục dịch chính xác từ Chương 25 Chunk 17.
- **Tự động ghép chương (Chapter Merge)**: Ghép các chunk của từng chương thành file chương hoàn chỉnh trong thư mục đầu ra `output/<ncode>/chapters/0001.txt`.

### Giai đoạn 3 (Phase 3): Desktop GUI & Novel Manager (PySide6)
- **Giao diện đồ họa máy tính hiện đại**: Xây dựng trên nền tảng PySide6 (Qt6) phong cách Fusion mượt mà, hỗ trợ giao diện độ phân giải cao High-DPI trên Windows 10/11.
- **Hai chế độ đầu vào linh hoạt**:
  - Nhập trực tiếp URL truyện Syosetu (hoặc mã ncode như `n0983ms`, `n1234ab`).
  - Kéo-thả (Drag & Drop) hoặc duyệt file tài liệu cục bộ (`.txt`, `.docx`, `.pdf`, `.md`).
- **Trình đọc PDF tích hợp (`pypdf`)**: Trích xuất văn bản từ tài liệu PDF tiếng Nhật nhiều trang và tự động dịch xuất ra file văn bản tiếng Việt.
- **Theo dõi trạng thái Ollama trực tiếp (Real-time Status)**: Hiển thị ngay trạng thái kết nối Ollama và kiểm tra xem model `translategemma:4b` đã được cài đặt sẵn sàng chưa.
- **Điều khiển an toàn Non-destructive (Pause / Resume / Cancel)**:
  - **Pause**: Tạm dừng an toàn ngay sau khi hoàn thành chunk hiện tại (không làm hỏng request đang chạy, không mất dữ liệu).
  - **Resume**: Tiếp tục dịch ngay lập tức từ chunk kế tiếp.
  - **Cancel**: Dừng tiến trình nhưng **giữ nguyên 100% cache** các chunk và chương đã dịch xong.
- **Quản lý Tiểu thuyết & Chương (Novel & Chapter Manager)**:
  - Bảng danh sách chương hiển thị chi tiết: số thứ tự, tên chương, trạng thái tải (✓ Crawled), trạng thái dịch (✓ Completed / ✗ Failed / Pending), và tiến độ chunk (ví dụ `3/3`).
  - Bộ lọc trạng thái: **All** / **Completed** / **Pending** / **Failed**.
  - Tùy chọn dịch chọn lọc: Chọn một hoặc nhiều chương bất kỳ và nhấn "Translate Selected Chapter(s)".
- **Quản lý Lịch sử Tác vụ (Recent Jobs)**:
  - Tự động quét thư mục bộ nhớ đệm `cache/` và `cache/novels/` để hiển thị tất cả các tác vụ dịch novel và tài liệu gần đây.
  - Nhấp đúp chuột để tải ngay novel hoặc tài liệu vào giao diện làm việc.
- **Nhật ký Trực tiếp (Live Logs)**:
  - Khung hiển thị log phong cách console với mã màu trực quan (Xanh: INFO, Vàng: WARNING, Đỏ: ERROR).
  - Tự động cuộn trang (Auto-scroll), nút xóa log và nút xuất log ra file `.log`.
- **Hộp thoại Cấu hình Trực quan**:
  - **Settings Dialog**: Cấu hình Ollama host, model name, timeout, chunk size, context tail, delay.
  - **Glossary Dialog**: Trình chỉnh sửa từ điển đối chiếu Nhật - Việt dạng bảng, hỗ trợ tìm kiếm/lọc từ khóa, thêm/xóa dòng, và lưu trực tiếp vào `config/glossary.txt`.
  - **Prompt Template Dialog**: Chỉnh sửa prompt dịch thuật với tính năng kiểm tra tự động các placeholder bắt buộc (`{GLOSSARY}`, `{CONTEXT}`, `{TEXT}`) và khôi phục prompt mặc định.

---

## 2. Cấu trúc thư mục dự án

```text
local-translator/
│
├── README.md                  # Tài liệu hướng dẫn sử dụng (tiếng Việt)
├── requirements.txt           # requests, pyyaml, tqdm, python-docx, beautifulsoup4, pytest, PySide6, pypdf
├── .gitignore                 # Cấu hình bỏ qua cache, log, input và output
│
├── config/
│   ├── settings.yaml          # Cấu hình hệ thống (Ollama, translation, crawler)
│   ├── prompt.txt             # Mẫu prompt dịch thuật với các placeholder
│   └── glossary.txt           # Bảng thuật ngữ chuyên ngành (Nhật = Việt)
│
├── input/                     # Chứa tài liệu đơn lẻ hoặc tiểu thuyết đã crawl
│   ├── sample_ja.txt          # Văn bản mẫu thử nghiệm
│   └── <ncode>/               # Thư mục tiểu thuyết (ví dụ n0983ms)
│       ├── novel.json         # Metadata tiểu thuyết (tiêu đề, số chương, nguồn)
│       └── chapters/          # Văn bản gốc từng chương (0001.txt, 0002.txt...)
│
├── output/                    # Chứa văn bản tiếng Việt sau khi dịch
│   ├── sample_vi.txt
│   └── <ncode>/
│       ├── novel.json
│       └── chapters/          # Bản dịch tiếng Việt từng chương (0001.txt...)
│
├── cache/                     # Cache lưu trạng thái và bản dịch từng chunk
│   ├── <job_id>/              # Cache cho tài liệu đơn lẻ (Phase 1)
│   └── novels/                # Cache phân cấp cho tiểu thuyết (Phase 2 & 3)
│       └── <ncode>/
│           ├── manifest.json  # Tiến độ chung của novel
│           └── chapters/
│               └── 0001/
│                   ├── manifest.json
│                   └── chunks/
│                       ├── 0001.json
│                       └── ...
│
├── logs/                      # Nhật ký hoạt động chi tiết (translator, crawler)
│
├── src/
│   ├── __init__.py
│   ├── main.py                # Điểm khởi chạy chính CLI & GUI (gui, check, crawl, translate, crawl-translate)
│   ├── config.py              # Xử lý cấu hình và kiểm tra hash toàn vẹn
│   ├── models.py              # Các cấu trúc dữ liệu (Novel, Chapter, Chunk, Manifest)
│   │
│   ├── gui/                   # Module Giao diện Desktop PySide6 (Phase 3)
│   │   ├── __init__.py        # Hàm run_gui() và xuất các module GUI
│   │   ├── __main__.py        # Điểm chạy trực tiếp `python -m src.gui`
│   │   ├── main_window.py     # Cửa sổ chính MainWindow
│   │   ├── widgets.py         # DropAreaWidget, ChapterTableWidget, RecentJobsWidget, LogViewerWidget
│   │   ├── dialogs.py         # SettingsDialog, GlossaryDialog, PromptDialog
│   │   └── workers.py         # QThread workers: CrawlWorker, NovelTranslationWorker, SingleDocTranslationWorker
│   │
│   ├── crawler/               # Module Crawler (Phase 2)
│   │   ├── __init__.py
│   │   ├── base.py            # BaseCrawler trừu tượng & Rate Limiting
│   │   └── syosetu.py         # SyosetuCrawler chuyên dụng cho ncode.syosetu.com
│   │
│   ├── document/              # Xử lý tài liệu (Phase 1 & 3)
│   │   ├── reader.py          # Trình đọc tài liệu (TXT, DOCX, PDF với pypdf)
│   │   ├── chunker.py         # Phân tách câu/đoạn tiếng Nhật thông minh
│   │   └── writer.py          # Trình ghi tài liệu đầu ra (TXT, DOCX)
│   │
│   ├── translation/           # Module Dịch thuật
│   │   ├── ollama_client.py   # Client kết nối Ollama HTTP API với Retry
│   │   ├── prompt_builder.py  # Ghép nối Prompt, Glossary và Context
│   │   └── translator.py      # Điều phối dịch và kiểm tra chất lượng
│   │
│   ├── cache/                 # Module Cache
│   │   ├── cache_manager.py   # Quản lý cache tài liệu đơn lẻ
│   │   └── novel_cache_manager.py # Quản lý cache phân cấp Novel/Chapter/Chunk
│   │
│   ├── pipeline/              # Module Pipeline
│   │   ├── translation_pipeline.py # Pipeline dịch file đơn lẻ
│   │   └── novel_pipeline.py  # Pipeline dịch tiểu thuyết theo chương/chunk
│   │
│   └── utils/
│       ├── logger.py          # Ghi nhật ký console và file
│       ├── text_utils.py      # Tiện ích chuẩn hóa chuỗi và tách câu tiếng Nhật
│       └── validator.py       # Bộ lọc kiểm tra chất lượng bản dịch
│
└── tests/                     # 69 bài kiểm thử đơn vị tự động (100% PASS)
    ├── test_gui.py            # Kiểm thử giao diện headless, widgets, dialogs, PDF reader, workers
    ├── test_syosetu.py        # Kiểm thử crawler, phân trang, sanitization, retry, resume
    ├── test_novel_pipeline.py # Kiểm thử cache phân cấp, novel pipeline, chunk-level resume
    ├── test_chunker.py        # Kiểm thử phân đoạn tiếng Nhật
    ├── test_prompt_builder.py # Kiểm thử prompt, glossary, context
    ├── test_cache.py          # Kiểm thử cache file đơn lẻ
    ├── test_text_utils.py     # Kiểm thử tiện ích câu và hash
    ├── test_validator.py      # Kiểm thử bộ lọc chất lượng
    ├── test_document.py       # Kiểm thử đọc/ghi TXT, DOCX và kiểm tra định dạng
    └── test_pipeline.py       # Kiểm thử pipeline file đơn lẻ
```

---

## 3. Yêu cầu hệ thống

- **Hệ điều hành**: Windows 10 hoặc Windows 11 (64-bit).
- **Phần cứng đề xuất**:
  - **RAM**: Tối thiểu 16 GB (DDR4 / DDR5).
  - **CPU**: Intel Core i5 thế hệ 11 trở lên (hoặc AMD Ryzen 5 tương đương).
  - **GPU**: Không bắt buộc (chạy mượt mà trên CPU với đồ họa tích hợp Intel UHD/Iris Xe).
  - **Ổ cứng**: Trống ít nhất 5 GB để cài đặt Ollama và model `translategemma:4b` (~2.8 GB).
- **Phần mềm**:
  - Python 3.10 trở lên (khuyên dùng Python 3.11, 3.12, hoặc 3.14).
  - Ollama cho Windows.

---

## 4. Hướng dẫn cài đặt từng bước

Có thể chạy ứng dụng tại dist/LocalTranslator.exe hoặc dùng cách sau: 

### Bước 1: Cài đặt Ollama và tải mô hình TranslateGemma 4B

1. Tải và cài đặt Ollama cho Windows từ trang chủ: [https://ollama.com/download](https://ollama.com/download).
2. Sau khi cài đặt xong, mở **PowerShell** và tải mô hình TranslateGemma 4B:
   ```powershell
   ollama pull translategemma:4b
   ```
3. Kiểm tra xem mô hình đã sẵn sàng chưa:
   ```powershell
   ollama list
   ```

### Bước 2: Chuẩn bị môi trường Python

1. Mở PowerShell và di chuyển vào thư mục dự án:
   ```powershell
   cd d:\local-translator
   ```
2. Tạo môi trường ảo Python (Virtual Environment):
   ```powershell
   python -m venv venv
   ```
3. Kích hoạt môi trường ảo:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(Nếu PowerShell báo lỗi execution policy, chạy: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

4. Cài đặt các thư viện phụ thuộc:
   ```powershell
   pip install -r requirements.txt
   ```

---

## 5. Khởi chạy Giao diện Đồ họa Desktop GUI (Phase 3)

Bạn có thể mở giao diện đồ họa bằng bất kỳ cách nào sau đây:

### Cách 1: Sử dụng lệnh `gui`
```powershell
python -m src.main gui
```

### Cách 2: Chạy trực tiếp qua module `src.gui`
```powershell
python -m src.gui
```

### Cách 3: Chạy không kèm tham số (mặc định mở GUI)
```powershell
python -m src.main
```

### Các thao tác trên giao diện:
1. **Dịch Tiểu thuyết Syosetu**:
   - Dán URL truyện (ví dụ `https://ncode.syosetu.com/n0983ms/`) hoặc mã `n0983ms` vào ô URL.
   - Bấm **Crawl Only** để tải danh sách chương về máy, hoặc bấm **Crawl + Translate** để tự động tải và dịch toàn bộ truyện.
2. **Dịch Tài liệu Cục bộ**:
   - Kéo-thả file `.txt`, `.docx`, `.pdf`, `.md` vào khung kéo-thả, hoặc bấm vào khung để chọn file từ máy tính.
   - Nhấn **Translate Selected Document**.
3. **Quản lý Chương & Dịch Chọn Lọc**:
   - Chuyển sang tab **Novel & Chapter Manager**.
   - Xem danh sách chương kèm số chunk đã dịch.
   - Sử dụng bộ lọc **Completed**, **Pending**, **Failed** để dễ theo dõi.
   - Chọn một hoặc nhiều chương cần dịch rồi bấm **Translate Selected Chapter(s)**.
4. **Tạm dừng, Tiếp tục & Hủy an toàn**:
   - Bấm **⏸ Pause**: Hệ thống hoàn tất chunk đang dịch và tạm dừng an toàn.
   - Bấm **▶ Resume**: Tiếp tục công việc từ chunk kế tiếp.
   - Bấm **⏹ Cancel**: Hủy tác vụ hiện tại mà không làm mất các chunk/chương đã dịch.
5. **Chỉnh sửa Thuật ngữ & Prompt**:
   - Bấm nút **📖 Glossary** trên thanh công cụ để tra cứu, thêm hoặc xóa thuật ngữ Nhật - Việt.
   - Bấm nút **📝 Prompt** để điều chỉnh lời nhắc hoặc khôi phục về mặc định.
   - Bấm nút **⚙ Settings** để thay đổi địa chỉ Ollama, kích thước chunk hoặc delay.

---

## 6. Sử dụng CLI Dòng Lệnh (Phase 1 & Phase 2)

Hệ thống CLI tiếp tục hoạt động đầy đủ và độc lập với GUI:

### 6.1. Kiểm tra chẩn đoán hệ thống (`check`)
```powershell
python -m src.main check
```

### 6.2. Crawl tiểu thuyết từ Syosetu (`crawl`)
```powershell
python -m src.main crawl https://ncode.syosetu.com/n0983ms/
```
Tùy chỉnh khoảng nghỉ (Polite Delay):
```powershell
python -m src.main crawl https://ncode.syosetu.com/n1234ab/ --delay 1.5
```

### 6.3. Dịch tiểu thuyết đã crawl (`translate`)
```powershell
python -m src.main translate n0983ms
```
Dịch một khoảng chương cụ thể (ví dụ chương 1 đến 5):
```powershell
python -m src.main translate n0983ms --start-chapter 1 --end-chapter 5
```

### 6.4. Crawl và Dịch trong một câu lệnh duy nhất (`crawl-translate`)
```powershell
python -m src.main crawl-translate https://ncode.syosetu.com/n0983ms/
```

### 6.5. Dịch tài liệu đơn lẻ (.txt, .docx, .pdf)
```powershell
python -m src.main translate input/sample_ja.txt
python -m src.main translate input/sample_ja.txt -o output/sample_vi.txt
```

---

## 7. Bảng Tùy chọn Dòng lệnh Nâng cao

| Tùy chọn | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| `gui` | Khởi chạy giao diện đồ họa Desktop GUI | N/A |
| `--chunk-size` | Kích thước ký tự tiếng Nhật tối đa cho mỗi chunk | `1800` |
| `--context-size` | Kích thước ngữ cảnh tiếng Việt chunk trước truyền sang | `600` |
| `--temperature` | Độ sáng tạo của mô hình (thấp để tăng tính ổn định) | `0.1` |
| `--force` | Bắt buộc dịch lại/crawl lại từ đầu (bỏ qua cache) | `False` |
| `--continue-on-error` | Bỏ qua lỗi và tiếp tục các phần còn lại | `False` |
| `--model` | Chỉ định mô hình Ollama khác (nếu có) | `translategemma:4b` |
| `--delay` | Thời gian nghỉ giữa các lượt HTTP request khi crawl (giây) | `1.0` |
| `--start-chapter` | Chương bắt đầu dịch (dành cho novel) | Chương đầu tiên |
| `--end-chapter` | Chương kết thúc dịch (dành cho novel) | Chương cuối cùng |

---

## 8. Đóng gói ứng dụng thành file .EXE (PyInstaller)

Để đóng gói ứng dụng thành file thực thi chạy trực tiếp trên Windows mà không cần mở console:

1. Cài đặt PyInstaller:
   ```powershell
   pip install pyinstaller
   ```
2. Chạy lệnh đóng gói:
   ```powershell
   pyinstaller --noconfirm --onedir --windowed `
       --name "LocalTranslator" `
       --add-data "config;config" `
       --add-data "input;input" `
       src/gui/__main__.py
   ```
3. Thư mục file thực thi hoàn chỉnh sẽ nằm trong `dist/LocalTranslator/LocalTranslator.exe`.

---

## 9. Chạy kiểm thử tự động (Unit Tests)

Dự án sở hữu bộ test toàn diện **69 tests** bao quát từ GUI, dialogs, PDF reader, workers, crawler, sanitization, chunking, caching, prompt builder, đến pipeline:

```powershell
python -m pytest -v
```

**Kết quả kiểm thử:**
```text
============================= 69 passed in 5.39s ==============================
```
*Tất cả bài kiểm tra đều sử dụng Mock HTTP, Mock Ollama và headless offscreen Qt platform, chạy hoàn toàn offline và không phụ thuộc mạng hay màn hình hiển thị.*

---

## 10. Xử lý sự cố thường gặp (Troubleshooting)

| Sự cố | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `Cannot connect to Ollama at http://localhost:11434` | Dịch vụ Ollama chưa được bật. | Khởi chạy ứng dụng Ollama hoặc gõ `ollama serve` trong PowerShell. Kiểm tra nút trạng thái Ollama trên GUI. |
| `Model 'translategemma:4b' was not found` | Chưa tải mô hình về máy. | Chạy lệnh: `ollama pull translategemma:4b`. |
| `pypdf is required to read PDF files` | Chưa cài thư viện đọc PDF. | Chạy lệnh: `pip install pypdf`. |
| `HTTP 404: Page not found` khi crawl | Sai mã ncode hoặc truyện đã bị xóa trên Syosetu. | Kiểm tra lại URL trên trình duyệt xem truyện còn tồn tại không. |
| `HTTP 403: Access forbidden` khi crawl | Syosetu chặn IP hoặc gửi request quá nhanh. | Tăng `--delay` lên `2.0` hoặc cấu hình trong hộp thoại Settings của GUI. |
| `Novel translation halted at Chapter X Chunk Y` | Lỗi timeout hoặc crash giữa chừng. | Chạy lại lệnh hoặc bấm Resume trên GUI; hệ thống tự động tiếp tục chính xác từ Chunk Y của Chương X. |
| Ký tự tiếng Việt bị lỗi font trên console cũ | Console Windows đang ở chế độ mã hóa cũ (cp1252). | Chương trình đã tự động kích hoạt UTF-8 stdout. Hoặc gõ lệnh `chcp 65001` trước khi chạy. |
