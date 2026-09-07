# Local Japanese → Vietnamese Document & Web Novel Translation Pipeline

Hệ thống dịch thuật tài liệu và tiểu thuyết mạng tiếng Nhật (Syosetu) sang tiếng Việt cục bộ (Local Translation Pipeline) chất lượng cao, chạy hoàn toàn offline trên Windows sử dụng **Ollama** và mô hình chuyên dụng **TranslateGemma 4B** của Google.

Không giới hạn số lượng ký tự, không phụ thuộc bất kỳ dịch vụ cloud API nào (OpenAI, Google Cloud, DeepL), bảo vệ toàn vẹn quyền riêng tư dữ liệu và được tối ưu hóa đặc biệt cho máy tính CPU-only với 16 GB RAM.

---

## 1. Tính năng nổi bật

### Giai đoạn 1 (Phase 1): Dịch tài liệu đơn lẻ
- **Chạy hoàn toàn cục bộ (100% Offline/Local)**: Kết nối Ollama HTTP API trên máy cá nhân, không tốn chi phí token, không rò rỉ dữ liệu.
- **Dịch tài liệu dài không giới hạn**: Tự động chia nhỏ tài liệu theo cấu trúc đoạn văn bản và câu tiếng Nhật (`。`, `！`, `？`, `\n\n`), không bao giờ cắt đôi từ vựng.
- **Bộ nhớ đệm thông minh & Tự động Resume**: Mỗi chunk sau khi dịch được lưu ngay lập tức vào ổ đĩa kèm mã băm SHA-256. Nếu quá trình dịch bị gián đoạn (mất điện, tắt máy, lỗi mạng), chạy lại sẽ tự động tiếp tục từ chunk chưa dịch.
- **Bảo toàn ngữ cảnh liền mạch (Context Continuity)**: Tự động truyền một đoạn ngữ cảnh ngắn (mặc định 600 ký tự tiếng Việt vừa dịch) sang chunk kế tiếp để duy trì sự nhất quán về đại từ nhân xưng, tên riêng và văn phong.
- **Bảng thuật ngữ chuyên ngành (Glossary)**: Tùy biến từ điển đối chiếu Nhật - Việt trong `config/glossary.txt`.
- **Kiểm soát chất lượng bản dịch (Quality Safeguards)**: Tự động phát hiện và loại bỏ code fences thừa (````vietnamese ... ````), tiền tố đàm thoại ("Dưới đây là bản dịch:"), cảnh báo lặp từ vô tận hoặc bản dịch rỗng.
- **Hỗ trợ đa định dạng**: Đọc/ghi cả văn bản thuần `.txt`, `.md` và tài liệu Word `.docx`.

### Giai đoạn 2 (Phase 2): Crawler tiểu thuyết mạng & Pipeline theo Chương/Chunk
- **Crawl tự động từ Syosetu (ncode.syosetu.com)**: Tự động nhận diện tiêu đề, danh sách chương (bao gồm cả phân trang nhiều trang `?p=1`, `?p=2` và truyện ngắn tanpen 1 chương).
- **Trích xuất văn bản sạch sẽ**: Tự động gỡ bỏ thẻ chú âm furigana (`<rp>`, `<rt>`) để giữ kanji nguyên bản, loại bỏ mã HTML, chỉ giữ lại văn bản tiếng Nhật sạch.
- **Thu thập lịch sự & có trách nhiệm (Polite Rate Limiting)**: Khoảng nghỉ có thể tùy biến (mặc định 1.0 giây) giữa các yêu cầu, kèm cơ chế thử lại hàm mũ (exponential backoff retry).
- **Cấu trúc dữ liệu 3 cấp**: `Novel` $\to$ `Chapter` $\to$ `Chunk`.
- **Cơ chế Resume 2 cấp độ**:
  - **Cấp độ Crawl**: Không tải lại các chương đã tải đầy đủ và toàn vẹn.
  - **Cấp độ Dịch**: Nếu dịch đến Chương 25 Chunk 17 bị lỗi, khi chạy lại chương trình sẽ tự động bỏ qua toàn bộ Chương 1 đến 24 và Chương 25 Chunk 1 đến 16, tiếp tục dịch chính xác từ Chương 25 Chunk 17.
- **Tự động ghép chương (Chapter Merge)**: Ghép các chunk của từng chương thành file chương hoàn chỉnh trong thư mục đầu ra `output/<ncode>/chapters/0001.txt`.

---

## 2. Cấu trúc thư mục dự án

```text
local-translator/
│
├── README.md                  # Tài liệu hướng dẫn sử dụng (tiếng Việt)
├── requirements.txt           # requests, pyyaml, tqdm, python-docx, beautifulsoup4, pytest
├── .gitignore                 # Cấu hình bỏ qua cache, log, input và output
│
├── config/
│   ├── settings.yaml          # Cấu hình hệ thống (Ollama, translation, crawler)
│   ├── prompt.txt             # Mẫu prompt dịch thuật với các placeholder
│   └── glossary.txt           # Bảng thuật ngữ chuyên ngành (Nhật = Việt)
│
├── input/                     # Chứa tài liệu đơn lẻ hoặc tiểu thuyết đã crawl
│   ├── sample_ja.txt          # Văn bản mẫu thử nghiệm Phase 1
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
│   └── novels/                # Cache phân cấp cho tiểu thuyết (Phase 2)
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
│   ├── main.py                # Điểm khởi chạy CLI (check, crawl, translate, crawl-translate)
│   ├── config.py              # Xử lý cấu hình và kiểm tra hash toàn vẹn
│   ├── models.py              # Các cấu trúc dữ liệu (Novel, Chapter, Chunk, Manifest)
│   │
│   ├── crawler/               # Module Crawler (Phase 2)
│   │   ├── __init__.py
│   │   ├── base.py            # BaseCrawler trừu tượng & Rate Limiting
│   │   └── syosetu.py         # SyosetuCrawler chuyên dụng cho ncode.syosetu.com
│   │
│   ├── document/              # Xử lý tài liệu (Phase 1)
│   │   ├── reader.py          # Trình đọc tài liệu (UTF-8, UTF-8-BOM, DOCX)
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
└── tests/                     # 58 bài kiểm thử đơn vị tự động (100% pass)
    ├── test_syosetu.py        # Kiểm thử crawler, phân trang, sanitization, retry, resume
    ├── test_novel_pipeline.py # Kiểm thử cache phân cấp, novel pipeline, chunk-level resume
    ├── test_chunker.py        # Kiểm thử phân đoạn tiếng Nhật
    ├── test_prompt_builder.py # Kiểm thử prompt, glossary, context
    ├── test_cache.py          # Kiểm thử cache file đơn lẻ
    ├── test_text_utils.py     # Kiểm thử tiện ích câu và hash
    ├── test_validator.py      # Kiểm thử bộ lọc chất lượng
    ├── test_document.py       # Kiểm thử đọc/ghi TXT và DOCX
    └── test_pipeline.py       # Kiểm thử pipeline file đơn lẻ
```

---

## 3. Yêu cầu hệ thống

- **Hệ điều hành**: Windows 10 hoặc Windows 11 (64-bit).
- **Phần cứng đề xuất**:
  - **RAM**: Tối thiểu 16 GB (DDR4 / DDR5).
  - **CPU**: Intel Core i5 thế hệ 11 trở lên (hoặc AMD Ryzen 5 tương đương).
  - **GPU**: Không bắt buộc (chạy hoàn toàn trên CPU với đồ họa tích hợp Intel UHD/Iris Xe).
  - **Ổ cứng**: Trống ít nhất 5 GB để cài đặt Ollama và model `translategemma:4b` (~2.8 GB).
- **Phần mềm**:
  - Python 3.10 trở lên (khuyên dùng Python 3.11, 3.12, hoặc 3.14).
  - Ollama cho Windows.

---

## 4. Hướng dẫn cài đặt từng bước

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

## 5. Kiểm tra sức khỏe hệ thống (System Health Check)

Trước khi dịch tài liệu, chạy lệnh sau để kiểm tra toàn bộ môi trường:

```powershell
python -m src.main check
```

**Kết quả mẫu thành công:**
```text
============================================================
  Local Japanese -> Vietnamese Translator: System Diagnostics
============================================================

[1] Python Environment: 3.14.7 (win32)
    -> OK (Python 3.10+ requirement satisfied)

[2] Required Python Packages:
    - requests: OK
    - pyyaml: OK
    - tqdm: OK
    - python-docx: OK
    - beautifulsoup4: OK

[3] Configuration Files:
    - Settings: OK (D:\local-translator\config\settings.yaml)
    - Prompt Template: OK (D:\local-translator\config\prompt.txt)
    - Glossary: OK (D:\local-translator\config\glossary.txt)

[4] Ollama Service & Model Diagnostics:
    - Ollama Host: http://localhost:11434
    - Target Model: translategemma:4b
    - Ollama Connectivity: REACHABLE
    - Installed models (2): translategemma:4b, ...
    - Target model 'translategemma:4b': INSTALLED (Ready to use)
============================================================
  STATUS: ALL CHECKS PASSED. Ready to translate documents!
============================================================
```

---

## 6. Hướng dẫn sử dụng chi tiết

### 6.1. Crawl tiểu thuyết từ Syosetu (`crawl`)

Để tải một bộ truyện từ ncode.syosetu.com về máy:

```powershell
python -m src.main crawl https://ncode.syosetu.com/n0983ms/
```

- Truyện sẽ được lưu vào `input/<ncode>/` gồm file metadata `novel.json` và các chương nguồn `chapters/0001.txt`, `chapters/0002.txt`...
- **Tùy chỉnh khoảng nghỉ (Polite Delay)**:
  ```powershell
  python -m src.main crawl https://ncode.syosetu.com/n1234ab/ --delay 1.5
  ```
- **Tự động Resume khi crawl**: Nếu đang tải 500 chương mà bị đứt mạng ở chương 318, chạy lại lệnh sẽ tự động nhận biết chương 1–317 đã xong và chỉ tải tiếp từ chương 318.

---

### 6.2. Dịch tiểu thuyết đã crawl (`translate`)

Sau khi đã crawl truyện về `input/<ncode>`, bạn có thể dịch bằng cách truyền mã `ncode` hoặc đường dẫn thư mục:

```powershell
python -m src.main translate n0983ms
```
hoặc:
```powershell
python -m src.main translate input/n0983ms
```

**Dịch một khoảng chương cụ thể (ví dụ chương 1 đến 5):**
```powershell
python -m src.main translate n0983ms --start-chapter 1 --end-chapter 5
```

**Cơ chế Resume cấp độ Chapter & Chunk:**
- Nếu bạn dừng tiến trình hoặc gặp lỗi ở **Chương 25 Chunk 17**:
  - Khi chạy lại lệnh `python -m src.main translate n0983ms`, hệ thống sẽ:
    - Bỏ qua toàn bộ Chương 1 đến 24 (đã hoàn thành).
    - Đọc cache của Chương 25, bỏ qua Chunk 1 đến 16.
    - Tiếp tục gọi Ollama để dịch từ **Chương 25 Chunk 17**.

---

### 6.3. Crawl và Dịch trong một câu lệnh duy nhất (`crawl-translate`)

Thực hiện toàn bộ quy trình: phát hiện chương $\to$ tải các chương còn thiếu $\to$ dịch các chương/chunk còn thiếu $\to$ ghép chương tiếng Việt:

```powershell
python -m src.main crawl-translate https://ncode.syosetu.com/n0983ms/
```

Giới hạn số chương cần dịch thử:
```powershell
python -m src.main crawl-translate https://ncode.syosetu.com/n1234ab/ --start-chapter 1 --end-chapter 3
```

---

### 6.4. Dịch tài liệu đơn lẻ (Phase 1 Backward Compatible)

Dịch một file văn bản `.txt`, `.md` hoặc `.docx` độc lập:

```powershell
python -m src.main translate input/sample_ja.txt
```

Chỉ định file đầu ra:
```powershell
python -m src.main translate input/sample_ja.txt -o output/sample_vi.txt
```

---

### 6.5. Các tùy chọn dòng lệnh nâng cao

| Tùy chọn | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
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

## 7. Cấu hình Bảng thuật ngữ (Glossary) & Prompt

### 7.1. Bảng thuật ngữ (`config/glossary.txt`)

Mỗi dòng định nghĩa một cặp từ khóa: `<Thuật ngữ tiếng Nhật> = <Bản dịch tiếng Việt>`:

```text
# Bảng thuật ngữ chuyên ngành
機械学習 = học máy
深層学習 = học sâu
人工知能 = trí tuệ nhân tạo
勇者 = dũng giả
魔王 = ma vương
スキル = kỹ năng
ステータス = chỉ số
悪役令嬢 = tiểu thư phản diện
```

### 7.2. Tùy biến Prompt (`config/prompt.txt`)

File prompt hỗ trợ 3 placeholder chính:
- `{GLOSSARY}`: Vị trí chèn tự động các từ khóa trong bảng thuật ngữ.
- `{CONTEXT}`: Vị trí chèn đuôi bản dịch tiếng Việt của chunk liền trước.
- `{TEXT}`: Đoạn văn bản tiếng Nhật cần dịch trong chunk hiện tại.

---

## 8. Chạy kiểm thử tự động (Unit Tests)

Dự án có bộ test toàn diện 58 tests bao quát từ crawler, regex, ncode parser, sanitization, chunking, caching, prompt builder, mock pipeline:

```powershell
python -m pytest -v
```

**Kết quả kiểm thử:**
```text
============================= 58 passed in 3.38s ==============================
```
*Tất cả bài kiểm tra đều sử dụng Mock HTTP và Mock Ollama, không phụ thuộc kết nối Internet và không yêu cầu Ollama phải chạy.*

---

## 9. Xử lý sự cố thường gặp (Troubleshooting)

| Sự cố | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `Cannot connect to Ollama at http://localhost:11434` | Dịch vụ Ollama chưa được bật. | Khởi chạy ứng dụng Ollama hoặc gõ `ollama serve` trong PowerShell. |
| `Model 'translategemma:4b' was not found` | Chưa tải mô hình về máy. | Chạy lệnh: `ollama pull translategemma:4b`. |
| `HTTP 404: Page not found` khi crawl | Sai mã ncode hoặc truyện đã bị xóa trên Syosetu. | Kiểm tra lại URL trên trình duyệt xem truyện còn tồn tại không. |
| `HTTP 403: Access forbidden` khi crawl | Syosetu chặn IP hoặc yêu cầu xác thực. | Tăng `--delay` lên `2.0` hoặc kiểm tra kết nối mạng/proxy. |
| `Novel translation halted at Chapter X Chunk Y` | Lỗi timeout hoặc crash Ollama giữa chừng. | Chạy lại đúng câu lệnh cũ. Hệ thống sẽ tự động resume từ đúng Chunk Y của Chương X. |
| Ký tự tiếng Việt bị lỗi hiển thị trên PowerShell cũ | Console Windows đang ở chế độ ASCII/cp1252. | Chương trình đã tự động kích hoạt `reconfigure(encoding='utf-8')`. Nếu cần, gõ lệnh `chcp 65001` trước khi chạy. |
