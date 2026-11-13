# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

## Bài làm của học viên (Nguyễn Thành Danh — 2A202603493)

- **Corpus và manifest**: Em chọn tài liệu `starter/data/NIST_AI_RMF_1.0.pdf` (42 trang nội dung hợp lệ từ trang vật lý 6 đến 47), thông số nguồn và quy tắc tính trang ghi tại [data/manifest.json](data/manifest.json).
- **Benchmark**: 20 câu hỏi (15 `dev`, 5 `test`, trong đó 4 câu kiểm tra lọc `section`) tại [benchmark/questions.json](benchmark/questions.json).
- **Pipeline**: Cài đặt hoàn chỉnh các module `ingestion.py`, `chunking.py`, `embeddings.py`, `store.py`, `evaluation.py`, `run.py` trong `starter/src/`, sử dụng OpenAI `text-embedding-3-small` (`1536` chiều) và PostgreSQL 16 + `pgvector 0.8.7` (`127.0.0.1:55433`).
- **Cách tái lập nhanh**:
  1. Khởi động container PostgreSQL + pgvector trong `starter/` (`docker compose -p day6_student_starter up -d --wait`) và điền `OPENAI_API_KEY` vào `starter/.env`.
  2. Kiểm tra hạ tầng: `starter\.venv\Scripts\python.exe starter\scripts\check_setup.py`
  3. Chạy toàn bộ pipeline và đánh giá: `starter\.venv\Scripts\python.exe starter\src\run.py` (hoặc từ thư mục `starter/`: `.\.venv\Scripts\python.exe -m src.run`)
- **Kết quả và báo cáo**:
  - Thống kê chỉ số & trace: [results/metrics_summary.json](results/metrics_summary.json), [results/strategy_stats.json](results/strategy_stats.json), [results/traces.json](results/traces.json)
  - Nhật ký chấm thủ công: [results/manual_audit.md](results/manual_audit.md)
  - Nhật ký thí nghiệm: [artifacts/experiment_log.csv](artifacts/experiment_log.csv)
  - Báo cáo cá nhân: [report/individual/2A202603493_NguyenThanhDanh.md](report/individual/2A202603493_NguyenThanhDanh.md)
