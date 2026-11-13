# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang**:
   Chọn tài liệu **NIST Artificial Intelligence Risk Management Framework (AI RMF 1.0)** (`NIST AI 100-1`, bản tháng 1/2023) tại [NIST_AI_RMF_1.0.pdf](../../starter/data/NIST_AI_RMF_1.0.pdf), liên kết chính thức `https://doi.org/10.6028/NIST.AI.100-1`. Đây là ấn phẩm của chính phủ Hoa Kỳ (NIST), phát hành miễn phí và thuộc phạm vi public domain tại Mỹ (17 U.S.C. § 105), không có rủi ro bản quyền hay dữ liệu mật. Trong tổng số 48 trang vật lý, em đã loại bỏ 6 trang không chứa nội dung thân bài gồm trang 1 (bìa), trang 2 (thông tin xuất bản/DOI), trang 3 (disclaimer/lời cảm ơn), trang 4 (mục lục), trang 5 (danh sách hình) và trang 48 (bìa sau). Số trang nội dung hợp lệ còn lại là **42 trang** (trang vật lý `6–47`, tương ứng trang tài liệu `1–42`, tổng `101,495` ký tự trước chuẩn hóa, toàn bộ thông số được ghi lại trong [data/manifest.json](../../data/manifest.json)).

- **Chuẩn hóa, lỗi và giới hạn**:
  Khi đọc PDF bằng `pypdf`, em thấy một số lỗi định dạng do PDF xuất từ LaTeX: từ bị ngắt gạch nối qua dòng (ví dụ `recommenda-\ntion`), tiêu đề lặp lại ở đầu mỗi trang (`NIST AI 100-1 AI RMF 1.0`) và số trang ở cuối trang (`Page 8` hoặc `1`, `23`). Em thiết lập `normalize_text` trong [starter/src/ingestion.py](../../starter/src/ingestion.py) để chuẩn hóa Unicode `NFC`, nối các từ ngắt gạch nối cuối dòng, xóa header/footer lặp và gom các dòng cùng đoạn thành đoạn văn hoàn chỉnh trong khi vẫn giữ ranh giới các tiêu đề mục (`Part`, `Appendix`, `GOVERN X.Y:`, `MEASURE X.Y:`, `MANAGE X.Y:`). Trong 42 trang nội dung không có trang nào rỗng hoặc cần OCR (đã ghi log tại [results/ingestion_log.json](../../results/ingestion_log.json)), tuy nhiên các trang có hình sơ đồ như trang 15 (`Fig. 2`) hoặc trang 16 (`Fig. 3`) vẫn còn lẫn chữ nhãn từ hình vẽ vào dòng văn bản, và PDF không đánh dấu ranh giới đoạn nối tiếp qua trang (ví dụ cuối trang 7 sang đầu trang 8).

- **Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí**:
  Em sử dụng model `text-embedding-3-small` của OpenAI (`1536` chiều) qua API `https://api.openai.com/v1/embeddings` trong [starter/src/embeddings.py](../../starter/src/embeddings.py), chuẩn hóa ký tự xuống dòng thành khoảng trắng cho cả document và query. Vector store là **PostgreSQL 16 + pgvector 0.8.7** chạy cục bộ qua Docker (`127.0.0.1:55433`, database `day6_lab`, bảng `rag_chunks`), truy xuất exact sequential scan theo cosine distance (`embedding <=> query_vector`). Để kiểm chứng nạp lại không trùng, em chạy `upsert` hai lần liên tiếp cho chiến lược A: số dòng giữ nguyên `235 == 235` (kèm cơ chế xóa chunk cũ nếu tài liệu thay đổi trong [starter/src/store.py](../../starter/src/store.py)). Lệnh chạy toàn bộ pipeline từ root: `starter\.venv\Scripts\python.exe starter\src\run.py`. Tổng token API thực tế là `39,758` tokens (`20,316` cho A + `18,274` cho B/C + `1,168` cho 20 query), tổng chi phí là **`$0.000795`** (mức giá `$0.02 / 1M tokens`).
  - **Lần chạy pipeline mới nhất** bắt đầu `2026-11-13T19:00:26+07:00`, kết thúc `2026-11-13T19:00:52+07:00`. Runtime được ghi trong [results/strategy_stats.json](../../results/strategy_stats.json): Python `3.12.4`, `pypdf 6.21.4`, `psycopg 3.3.8`, `python-dotenv 1.2.4`; image Docker `pgvector/pgvector:0.8.7-pg16`.

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn**:
  Mỗi chunk lưu đầy đủ `document_id`, `source`, `page` (số trang vật lý), kèm `document_page`, `year` (`2023`), `version` (`"1.0"`) và trường lọc bổ sung **`section`** (`TEXT`, index trên `(strategy, section)`). Giá trị `section` gồm 4 nhóm phân biệt rõ được suy ra tất định từ mục lục và dải trang vật lý: `executive_summary` (`6–8`), `part_1_foundational` (`9–24`), `part_2_core_profiles` (`25–39`) và `appendix` (`40–47`). Em chọn `section` vì các câu hỏi về khung NIST AI RMF thường nhắm vào đúng phạm vi phần nền tảng, phần Core (GOVERN/MAP/MEASURE/MANAGE) hay các phụ lục kỹ thuật (Appendix A–D), giúp thu hẹp không gian tìm kiếm mà không cần suy đoán giá trị.

## Cấu hình và benchmark

- **A / B / C (tham số cụ thể, khác biệt duy nhất B–C)**:
  - **Chiến lược A**: `fixed_size(size=500, overlap=50)`, giữ metadata nhưng không lọc (`filters=None`), tạo ra `235` chunks (trung vị `500`, trung bình `466.3` ký tự).
  - **Chiến lược B**: `by_paragraph(max_size=800)`, tách theo tiêu đề/đoạn/tiểu mục và tách theo câu nếu đoạn vượt `800` ký tự, không lọc (`filters=None`), tạo ra `173` chunks (trung vị `622`, p90 `763`, max `797` ký tự). So với A, B chỉ thay đổi chiến lược chunking.
  - **Chiến lược C**: Dùng chung hoàn toàn tập `173` chunks và vector của B, khác biệt duy nhất so với B là bật lọc `WHERE section = %s` trong SQL cho các câu hỏi có yêu cầu phạm vi (`question["filter"]`).

- **>= 20 câu: phân chia >= 15 dev / >= 5 test, câu metadata filter và cách kiểm chứng evidence**:
  Em đã xây dựng **20 câu hỏi** tiếng Việt đối chiếu với nguồn tiếng Anh tại [benchmark/questions.json](../../benchmark/questions.json), chia cố định **15 câu `dev`** (`q01`–`q15`) và **5 câu `test`** (`q16`–`q20`) trước khi chạy pipeline. Bộ câu hỏi phủ đủ 4 dạng: trực tiếp (`9` câu), diễn đạt lại (`3` câu), điều kiện/ngoại lệ (`4` câu) và kiểm tra metadata filter (`4` câu: `q09`, `q12`, `q15` ở `dev` và `q19` ở `test`). Kiểm tra tự động xác nhận `evidence_quote` và mọi `supporting_evidence` đều xuất hiện trên `gold_page` sau chuẩn hóa; `evidence_required_phrases` yêu cầu chunk truy xuất chứa đủ các ý cốt lõi. Bằng chứng bổ sung đã được ghi cho q09, q11, q13, q15, q19 và q20 để bao phủ các phần đáp án trước đây chưa được quote chính hỗ trợ đầy đủ.

- **Tiêu chí chọn chiến lược đã chốt trước khi xem test**:
  Nếu các mục tiêu xung đột, em ưu tiên theo thứ tự sau: (1) đạt **Evidence Hit@3** cao nhất và tuân thủ filter tuyệt đối trên tập `dev`, (2) đạt **Grounding Quality** và **Chunk Coherence** tốt hơn để tránh cắt cụt ngữ cảnh điều kiện, (3) tối ưu số lượng chunk và chi phí embedding.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---:|---:|---:|---:|---:|
| A | dev | 6/15 (40.00%) | 9/15 (60.00%) | 235 | 9.254s | $0.000406 |
| A | test | 3/5 (60.00%) | 4/5 (80.00%) | 235 | 9.254s | $0.000406 |
| B | dev | 10/15 (66.67%) | 12/15 (80.00%) | 173 | 3.511s | $0.000365 |
| B | test | 3/5 (60.00%) | 4/5 (80.00%) | 173 | 3.511s | $0.000365 |
| C | dev | 10/15 (66.67%) | 12/15 (80.00%) | 173 | 3.511s + 0.229s DB | $0.000365 (dùng chung B) |
| C | test | 3/5 (60.00%) | 5/5 (100.00%) | 173 | 3.511s + 0.229s DB | $0.000365 (dùng chung B) |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---:|---:|---:|---|
| A | 0.00 / 2 (n=10) | 15/15 (100%) | dev: 1/3, test: 0/1 | 0: 1, 1: 0, 2: 4 — trung bình 1.60 / 2 |
| B | 1.80 / 2 (n=10) | 15/15 (100%) | dev: 1/3, test: 0/1 | 0: 1, 1: 0, 2: 4 — trung bình 1.60 / 2 |
| C | 1.80 / 2 (n=10) | 15/15 (100%) | dev: 3/3, test: 1/1 | 0: 0, 1: 0, 2: 5 — trung bình 2.00 / 2 |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Toàn bộ top-3 trace và điểm số: [results/traces.json](../../results/traces.json)
- Thống kê tổng hợp tự động: [results/metrics_summary.json](../../results/metrics_summary.json) và [results/strategy_stats.json](../../results/strategy_stats.json)
- Bảng chấm thủ công chi tiết và mẫu 10 vị trí đầu tiên (`p06`–`p15` theo số trang tăng dần): [results/manual_audit.md](../../results/manual_audit.md), [results/manual_audit.json](../../results/manual_audit.json) và [results/coherence_samples.json](../../results/coherence_samples.json)

## Phân tích và kết luận

- **So sánh A–B và B–C, 2 ví dụ sai có ID câu và nguồn**:
  - **So sánh A và B (tác động của chunking)**: Chuyển từ cắt cứng `500` ký tự (A) sang nhóm đoạn `max_size=800` (B) giúp giảm số chunk từ `235` xuống `173` (ít hơn 26.4%), giảm thời gian ingest trong lần chạy mới nhất từ `9.254s` xuống `3.511s` và giảm chi phí embedding. Trên tập `dev`, sau khi siết kiểm tra để yêu cầu đủ mọi ý cốt lõi trong bằng chứng, `Hit@1` tăng từ `6/15` lên `10/15` (+26.67 điểm %) và `Hit@3` tăng từ `9/15` lên `12/15`. Sự cải thiện rõ nhất nằm ở **Chunk Coherence**: A đạt `0.00/2` vì cắt ngang giữa từ và câu ở mọi vị trí kiểm tra (`p06`–`p15`), trong khi B đạt `1.80/2` vì giữ trọn đoạn văn và tiêu đề mục.
    - *Ví dụ lỗi 1 (`q08`, `dev`, nguồn trang 17)*: Ở chiến lược A, câu hỏi liệt kê 7 đặc tính trustworthy AI không đạt `Hit@3` dù tìm đúng trang 17 (`p17-fix-00` và `p17-fix-04` nằm trong top-3), vì đoạn văn liệt kê 7 đặc tính bị cắt làm đôi ngay giữa ranh giới ký tự 500 của `p17-fix-00` và `p17-fix-01`. Khi sang chiến lược B (`p17-par-00`), toàn bộ đoạn mở đầu mục 3 và danh sách 7 đặc tính nằm gọn trong một chunk, giúp B trả lời đúng ngay tại rank #1.
  - **So sánh B và C (tác động của metadata filter)**: Giữ nguyên chunking của B và bật lọc `section` khi câu hỏi có ngữ cảnh phạm vi giúp tỷ lệ tuân thủ filter tăng từ `1/3` (`dev`) và `0/1` (`test`) lên **100%** (`3/3` ở `dev`, `1/1` ở `test`). Quan trọng hơn, lọc giúp loại bỏ các chunk nhiễu ngữ nghĩa ở những chương khác.
    - *Ví dụ lỗi 2 (`q19`, `test`, nguồn trang 43 — `Appendix B`)*: Khi hỏi về tính năng AI vừa gây rủi ro vừa giúp tăng độ chính xác và khả năng phục hồi trong `Appendix B` (`pre-trained models and transfer learning`), cả A và B đều thất bại hoàn toàn (`Hit@3 = False`, Grounding `0/2`) vì top-3 bị kéo sang các đoạn nói chung về context và độ chính xác ở `part_1_foundational` (`p19`, `p22`) hoặc `part_2_core_profiles` (`p30`). Khi bật `filter={"section": "appendix"}` ở chiến lược C, các trang ngoài phụ lục bị loại bỏ ngay trong câu lệnh SQL, đưa `p43-par-00` vào vị trí `#2` (score `0.38714`), nâng `Hit@3` của tập `test` lên `5/5` và Grounding lên `2.00/2`.
  - Ngoài ra, cả B và C vẫn bỏ lỡ `3` câu ở `dev` (`q04`, `q05`, `q14`) do truy vấn tiếng Việt ngắn gặp khó khi khớp với đoạn văn chuyên sâu tiếng Anh dài (ví dụ `q14` hỏi tổng quan mục `5.3 Measure` ở trang 33 nhưng top-3 lại kéo sang `Table 3` trang 34–35 vì mật độ từ khóa `MEASURE` cao hơn).

- **Chiến lược chọn, đánh đổi, điều kiện áp dụng**:
  Em chọn **Chiến lược C (`by_paragraph`, `max_size=800`, kèm lọc SQL theo `section`)** vì nó đồng thời đạt `Hit@3` cao nhất (`12/15` ở `dev`, `5/5` ở `test`), coherence `1.80/2`, grounding `2.00/2` trên tập `test`, tuân thủ filter `100%` và dùng ít chunk/chi phí hơn A. Đánh đổi của C là phụ thuộc vào việc phía gọi hệ thống (hoặc người dùng) phải cung cấp giá trị `section` hợp lệ trước khi truy xuất, nếu chọn sai `section`, bộ lọc cứng `WHERE section = %s` sẽ loại nhầm tài liệu đúng. Chiến lược C phù hợp nhất với các tài liệu chuẩn hóa có cấu trúc phân chương/phụ lục rõ ràng như NIST AI RMF 1.0 hoặc tài liệu kỹ thuật/chính sách nội bộ.

- **Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí**:
  Tập `test` chỉ có `5` câu (trong đó chỉ có `1` câu filter) nên kết quả `5/5 (100%)` chỉ mang tính minh họa trên mẫu nhỏ, không thể suy rộng rằng C luôn đạt 100% ở mọi bộ câu hỏi. Điểm chấm coherence và grounding do chính em thực hiện sau khi biết kết quả hệ thống nên có thể tồn tại thiên lệch chủ quan. Thời gian ingest phụ thuộc vào độ trễ mạng khi gọi OpenAI API; bảng trên báo cáo một lần đo của lần chạy mới nhất, không phải trung bình nhiều lần. Chiến lược C tái sử dụng vector đã embed từ B nên chỉ đo thêm thời gian `upsert` vào PostgreSQL (`0.229s`).

- **Nếu làm lại hoặc mở rộng, cải tiến gì?**:
  Nếu có thêm thời gian, em sẽ cải tiến ở một vài chỗ như: (1) gắn thêm tiêu đề mục cha (`parent_heading`, ví dụ `1.2.1 Risk Measurement`) vào đầu mỗi chunk để giữ ngữ cảnh khi một mục kéo dài qua nhiều trang, (2) hợp nhất đoạn bị ngắt qua ranh giới hai trang liên tiếp (như cuối trang 7 sang đầu trang 8), và (3) thử nghiệm **hybrid retrieval** (kết hợp cosine similarity với BM25/Postgres `tsvector`) để cải thiện những câu như `q04`, `q05`, `q14` vốn có từ khóa chuyên ngành chính xác nhưng bị nhiễu ngữ nghĩa khi truy vấn xuyên ngôn ngữ Việt–Anh.

- **Công cụ AI hỗ trợ và cách kiểm chứng**:
  Trong quá trình làm bài, em có sử dụng **GitHub Copilot** và **Antigravity** để hỗ trợ tác vụ viết mã nguồn các module pipeline, tạo script kiểm tra tự động và rà soát phần phân tích. Toàn bộ mã nguồn và kết quả đều được em tự kiểm chứng trực tiếp bằng cách: (1) chạy kiểm tra tự động xác nhận `20/20` `evidence_quote` khớp nguyên văn trên văn bản PDF đã chuẩn hóa, (2) chạy thực tế `starter\.venv\Scripts\python.exe starter\src\run.py` kết nối với PostgreSQL + `pgvector` và OpenAI API (`EMBEDDING_MODEL=text-embedding-3-small` trong `starter/.env`), (3) kiểm tra nạp lại hai lần trên chiến lược A (`235 == 235` bản ghi), và (4) tự đối chiếu thủ công `10` mẫu coherence (`p06`–`p15`) cùng `5` câu `test` (`q16`–`q20`) trong [results/traces.json](../../results/traces.json).
