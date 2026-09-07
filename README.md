# Local Japanese → Vietnamese Document Translation Pipeline

Hệ thống dịch thuật tài liệu tiếng Nhật sang tiếng Việt cục bộ (Local Translation Pipeline) chất lượng cao, chạy hoàn toàn offline trên Windows sử dụng **Ollama** và mô hình chuyên dụng **TranslateGemma 4B** của Google.

Không giới hạn số lượng ký tự per-request, không phụ thuộc cloud API (OpenAI, Google Cloud, DeepL), bảo vệ toàn vẹn quyền riêng tư dữ liệu và được tối ưu hóa đặc biệt cho máy tính CPU-only với 16 GB RAM.

---

## 1. Tính năng nổi bật

- **Chạy hoàn toàn cục bộ (100% Offline/Local)**: Sử dụng Ollama HTTP API trên máy cá nhân, không tốn chi phí API, không rò rỉ dữ liệu.
- **Dịch tài liệu dài không giới hạn**: Tự động chia nhỏ tài liệu theo cấu trúc đoạn văn bản và câu tiếng Nhật (`。`, `！`, `？`, `\n\n`), không cắt ngang câu.
- **Bộ nhớ đệm thông minh & Tự động Resume**: Mỗi chunk sau khi dịch được lưu ngay lập tức vào ổ đĩa. Nếu quá trình dịch bị gián đoạn (tắt máy, lỗi mạng, crash), chương trình sẽ tự động tiếp tục từ chunk chưa hoàn thành mà không dịch lại các phần trước.
- **Bảo toàn ngữ cảnh liền mạch (Context Continuity)**: Tự động truyền một đoạn ngữ cảnh ngắn (mặc định 600 ký tự tiếng Việt vừa dịch) sang chunk kế tiếp để đảm bảo tính nhất quán về đại từ nhân xưng, danh từ riêng và văn phong.
- **Bảng thuật ngữ chuyên ngành (Glossary)**: Tùy biến từ điển đối chiếu Nhật - Việt trong `config/glossary.txt` để chuẩn hóa các thuật ngữ kỹ thuật trong toàn bộ tài liệu.
- **Tùy chỉnh Prompt linh hoạt**: Mẫu prompt tại `config/prompt.txt` giúp định hình phong cách dịch tự nhiên, chuẩn mực.
- **Kiểm soát chất lượng bản dịch (Quality Safeguards)**: Tự động phát hiện và loại bỏ code fences thừa (````vietnamese ... ````), tiền tố đàm thoại ("Dưới đây là bản dịch:"), cảnh báo khi độ dài bất thường hoặc lặp từ vô tận.
- **Bảo toàn định dạng đặc biệt**: Giữ nguyên cấu trúc tiêu đề Markdown, danh sách, khối mã nguồn (code blocks), liên kết URL, email và số liệu.
- **Tối ưu hóa cho máy 16GB RAM & CPU**: Xử lý tuần tự từng chunk (`concurrency: 1`), giải phóng bộ nhớ liên tục, tránh nghẽn CPU và tràn RAM.

---

## 2. Cấu trúc thư mục dự án

```text
local-translator/
│
├── README.md                  # Tài liệu hướng dẫn sử dụng (tiếng Việt)
├── requirements.txt           # Danh sách thư viện phụ thuộc
├── .gitignore                 # Cấu hình bỏ qua cache, log và output
│
├── config/
│   ├── settings.yaml          # Cấu hình hệ thống (host, model, chunk_size, retry)
│   ├── prompt.txt             # Mẫu prompt dịch thuật với các placeholder
│   └── glossary.txt           # Bảng thuật ngữ chuyên ngành (Nhật = Việt)
│
├── input/
│   └── sample_ja.txt          # File văn bản tiếng Nhật mẫu để thử nghiệm
│
├── output/                    # Nơi lưu trữ văn bản tiếng Việt sau khi dịch
│   └── sample_vi.txt
│
├── cache/                     # Cache lưu trạng thái và bản dịch từng chunk
│   └── <job_id>/
│       ├── manifest.json      # Metadata và tiến độ của tác vụ dịch
│       └── chunks/            # Bản ghi JSON của từng chunk (000001.json, ...)
│
├── logs/                      # Nhật ký hoạt động chi tiết của chương trình
│
├── src/
│   ├── __init__.py
│   ├── main.py                # Điểm khởi chạy CLI (lệnh check và translate)
│   ├── config.py              # Xử lý cấu hình và kiểm tra hash toàn vẹn
│   ├── models.py              # Các cấu trúc dữ liệu (Chunk, Manifest, Record)
│   ├── document/
│   │   ├── reader.py          # Trình đọc tài liệu (hỗ trợ UTF-8, BOM, DOCX)
│   │   ├── chunker.py         # Bộ phân tách câu/đoạn tiếng Nhật thông minh
│   │   └── writer.py          # Trình ghi tài liệu đầu ra (TXT, DOCX)
│   ├── translation/
│   │   ├── ollama_client.py   # Client kết nối Ollama HTTP API với Retry
│   │   ├── prompt_builder.py  # Ghép nối Prompt, Glossary và Context
│   │   └── translator.py      # Điều phối dịch thuật và kiểm tra chất lượng
│   ├── cache/
│   │   └── cache_manager.py   # Quản lý lưu trữ/khôi phục cache từng chunk
│   ├── pipeline/
│   │   └── translation_pipeline.py  # Luồng xử lý tổng thể end-to-end
│   └── utils/
│       ├── logger.py          # Cấu hình ghi nhật ký console và file
│       ├── text_utils.py      # Tiện ích chuẩn hóa chuỗi và tách câu tiếng Nhật
│       └── validator.py       # Bộ lọc kiểm tra chất lượng bản dịch
│
└── tests/                     # Bộ kiểm thử đơn vị tự động (42 tests)
    ├── test_chunker.py
    ├── test_prompt_builder.py
    ├── test_cache.py
    ├── test_text_utils.py
    ├── test_validator.py
    ├── test_document.py
    └── test_pipeline.py
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
  - Python 3.10 trở lên (khuyên dùng Python 3.11 hoặc 3.12).
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
   Bạn sẽ thấy `translategemma:4b` xuất hiện trong danh sách.

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

[3] Configuration Files:
    - Settings: OK (D:\local-translator\config\settings.yaml)
    - Prompt Template: OK (D:\local-translator\config\prompt.txt)
    - Glossary: OK (D:\local-translator\config\glossary.txt)

[4] Ollama Service & Model Diagnostics:
    - Ollama Host: http://localhost:11434
    - Target Model: translategemma:4b
    - Ollama Connectivity: REACHABLE
    - Installed models (3): translategemma:4b, ...
    - Target model 'translategemma:4b': INSTALLED (Ready to use)
============================================================
  STATUS: ALL CHECKS PASSED. Ready to translate documents!
============================================================
```

---

## 6. Hướng dẫn sử dụng

### 6.1. Dịch tài liệu cơ bản

Đặt file tiếng Nhật dạng `.txt` vào thư mục `input/` (ví dụ `input/sample_ja.txt`), sau đó chạy:

```powershell
python -m src.main translate input/sample_ja.txt
```

File dịch tiếng Việt sẽ tự động xuất hiện tại `output/sample_ja_vi.txt`.

### 6.2. Chỉ định file đầu ra tùy ý

```powershell
python -m src.main translate input/sach_tieng_nhat.txt -o output/sach_dich_tieng_viet.txt
```

### 6.3. Tùy chỉnh kích thước Chunk và Ngữ cảnh

- `--chunk-size`: Số ký tự tiếng Nhật mục tiêu cho mỗi phần dịch (mặc định: `1800`).
- `--context-size`: Số ký tự tiếng Việt của phần dịch trước làm ngữ cảnh (mặc định: `600`).

```powershell
python -m src.main translate input/sample_ja.txt --chunk-size 1500 --context-size 500
```

### 6.4. Tùy chỉnh nhiệt độ sáng tạo (Temperature)

Mặc định `temperature = 0.1` để đảm bảo tính nhất quán tối đa và dịch chính xác. Nếu muốn văn phong biến hóa hơn:

```powershell
python -m src.main translate input/sample_ja.txt --temperature 0.2
```

### 6.5. Tự động Resume sau sự cố (Gián đoạn / Mất điện)

Nếu máy tính bị tắt đột ngột hoặc bạn nhấn `Ctrl + C` để dừng tiến trình khi đang dịch ở chunk 318 / 500:
Bạn **chỉ cần chạy lại đúng câu lệnh ban đầu**:

```powershell
python -m src.main translate input/sample_ja.txt
```

Hệ thống sẽ:
1. Đọc cache trong thư mục `cache/`.
2. Bỏ qua ngay lập tức chunk 1 đến 317 (tốc độ đọc cache ~300 chunk/giây).
3. Tiếp tục gọi Ollama để dịch từ chunk 318 trở đi.

### 6.6. Bắt buộc dịch lại từ đầu (Bỏ qua Cache)

Nếu bạn vừa chỉnh sửa file gốc hoặc đổi bảng thuật ngữ và muốn dịch lại toàn bộ từ đầu, thêm cờ `--force`:

```powershell
python -m src.main translate input/sample_ja.txt --force
```

### 6.7. Tiếp tục dịch khi có lỗi ở một chunk

Nếu một chunk bị lỗi và bạn không muốn dừng toàn bộ quá trình, sử dụng cờ `--continue-on-error`:

```powershell
python -m src.main translate input/sample_ja.txt --continue-on-error
```

---

## 7. Cấu hình Bảng thuật ngữ (Glossary) & Prompt

### 7.1. Bảng thuật ngữ (`config/glossary.txt`)

Mỗi dòng định nghĩa một cặp từ khóa: `<Thuật ngữ tiếng Nhật> = <Bản dịch tiếng Việt>`:

```text
# Bảng thuật ngữ chuyên ngành
機械学習 = học máy
深層学習 = học sâu
人工知能 = trí tuệ nhân tạo
ニューラルネットワーク = mạng nơ-ron
データセット = tập dữ liệu
アルゴリズム = thuật toán
```

### 7.2. Tùy biến Prompt (`config/prompt.txt`)

File prompt hỗ trợ 3 placeholder chính:
- `{GLOSSARY}`: Vị trí chèn tự động các từ khóa trong bảng thuật ngữ.
- `{CONTEXT}`: Vị trí chèn đuôi bản dịch tiếng Việt của chunk liền trước.
- `{TEXT}`: Đoạn văn bản tiếng Nhật cần dịch trong chunk hiện tại.

---

## 8. Chạy kiểm thử tự động (Unit Tests)

Dự án đi kèm bộ test toàn diện kiểm tra tất cả các trường hợp biên của văn bản tiếng Nhật, xử lý Unicode, cơ chế cache, prompt builder và mock pipeline:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

*Toàn bộ 42 bài kiểm tra được thiết kế chạy độc lập, không yêu cầu Ollama phải chạy ngầm.*

---

## 9. Kinh nghiệm tối ưu hóa trên máy 16GB RAM & CPU

1. **Giữ nguyên Concurrency = 1**: Không nên chạy song song nhiều chunk cùng lúc trên CPU vì TranslateGemma 4B sẽ cạnh tranh nhân CPU và làm máy bị quá nhiệt / chậm tiến độ.
2. **Đóng các ứng dụng ngốn RAM nặng**: Trước khi dịch sách dài (hàng trăm nghìn từ), hãy đóng các tab trình duyệt Chrome/Edge không cần thiết để nhường ít nhất 6 GB RAM trống cho Ollama.
3. **Kích thước chunk lý tưởng**: Khoảng 1,500 – 1,800 ký tự tiếng Nhật là điểm cân bằng tối ưu giữa khả năng ghi nhớ ngữ cảnh của model 4B và tốc độ sinh từ trên CPU.
4. **Tốc độ ước tính**: Trên CPU Intel Core i5 thế hệ 13 (di động), tốc độ sinh từ trung bình đạt khoảng 10 - 20 tokens/giây, một chunk 1000 ký tự mất khoảng 60 - 90 giây.

---

## 10. Xử lý sự cố thường gặp (Troubleshooting)

| Sự cố | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| `Cannot connect to Ollama at http://localhost:11434` | Dịch vụ Ollama chưa được bật. | Chạy ứng dụng Ollama hoặc gõ `ollama serve` trong PowerShell. |
| `Model 'translategemma:4b' was not found` | Chưa tải mô hình về máy. | Chạy lệnh: `ollama pull translategemma:4b`. |
| `UnicodeDecodeError` khi đọc file TXT | File lưu dưới bảng mã lạ (Shift-JIS, EUC-JP). | Chương trình tự động phát hiện UTF-8, UTF-8-BOM và Shift-JIS. Nếu vẫn lỗi, mở file bằng Notepad và chọn `Save As` với Encoding là `UTF-8`. |
| `Request timed out` | Máy quá tải hoặc chunk quá dài. | Tăng `timeout_seconds` trong `config/settings.yaml` (ví dụ 1200 giây) hoặc giảm `--chunk-size` xuống `1200`. |

---

## 11. Lộ trình phát triển tương lai

- [x] **Giai đoạn 1**: Hoàn thiện lõi dịch thuật TXT, cơ chế Chunking thông minh, Cache & Resume, Glossary, CLI diagnostics.
- [x] **Giai đoạn 2**: Đã tích hợp sẵn kiến trúc `DocxReader` và `DocxWriter` (hỗ trợ file Word `.docx`).
- [ ] **Giai đoạn 3**: Hỗ trợ trích xuất và dịch tài liệu PDF dạng văn bản (text-based PDF).
- [ ] **Giai đoạn 4**: Tích hợp OCR tiếng Nhật cho tài liệu PDF dạng scan/ảnh chụp (Manga, sách scan).
- [ ] **Giai đoạn 5**: Giao diện người dùng đồ họa (Desktop GUI) thân thiện với thanh kéo thả tệp và xem tiến độ trực quan.
