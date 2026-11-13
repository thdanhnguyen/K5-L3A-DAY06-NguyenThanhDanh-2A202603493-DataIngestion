# Nhật ký chấm thủ công (Manual Audit)
 
Lưu ý: Em tự chấm trên dữ liệu đầu ra nên có thể bị ảnh hưởng bởi việc biết trước cấu hình nào đang được đánh giá; để giảm nhiễu, em cố định trước 10 vị trí chấm coherence (`p06` đến `p15`) và đối chiếu nguyên văn từng đoạn chunk trong `results/traces.json`.

## 1. Chunk Coherence (10 vị trí nguồn đầu tiên: trang vật lý 6–15)

| Trang | Đoạn nguồn mục tiêu | Chiến lược A | Điểm A | Chiến lược B & C | Điểm B & C |
|---|---|---|---:|---|---:|
| 6 | Mở đầu Executive Summary | `p06-fix-00` cắt giữa danh sách; `p06-fix-01` cắt đầu từ `nizations...` | 0 | `p06-par-00` giữ trọn đoạn mở đầu; `p06-par-01` giữ trọn định nghĩa AI system | 2 |
| 7 | Social responsibility và Sustainability | `p07-fix-00` cắt giữa từ `to r`; `p07-fix-01` mất đầu trích dẫn ISO | 0 | `p07-par-00` và `p07-par-01` giữ trọn câu trích dẫn ISO | 2 |
| 8 | Bảy đặc tính và Governance | `p08-fix-00` cắt ngang từ `AI risk manag` | 0 | `p08-par-00` không cắt từ nhưng đầu trang vốn nối tiếp câu từ trang 7 | 1 |
| 9 | Part 1 — Framing Risk | `p09-fix-00` cắt giữa từ `composite m` ngay trong định nghĩa risk | 0 | `p09-par-00` giữ trọn mục 1 và dừng trước mục 1.1 | 2 |
| 10 | Risk Measurement Challenges | `p10-fix-00` cắt ngang từ `measure qua` | 0 | `p10-par-00` giữ trọn phần dẫn mục 1.2 và 1.2.1 | 2 |
| 11 | Impact assessment và Metrics | `p11-fix-00` cắt dở câu giữa từ `may` | 0 | `p11-par-00` giữ trọn hai đoạn liên quan tới đánh giá tác động và metrics | 2 |
| 12 | 1.2.2 Risk Tolerance | `p12-fix-00` cắt ngang `Risk tole`; `p12-fix-01` cắt ngang `conti` | 0 | `p12-par-00` giữ trọn vẹn cả mục 1.2.2 | 2 |
| 13 | Ưu tiên rủi ro và điều kiện dừng | `p13-fix-00` cắt ngang `sufficien` | 0 | `p13-par-00` giữ trọn vẹn đoạn quy định điều kiện dừng triển khai an toàn | 2 |
| 14 | Accountability và SME | `p14-fix-00` cắt ngang `managing AI r` | 0 | `p14-par-00` giữ trọn đoạn về trách nhiệm giải trình và doanh nghiệp nhỏ | 2 |
| 15 | Chú thích Fig. 2 AI Lifecycle | `p15-fix-00` cắt ngang `civil society o` | 0 | `p15-par-00` không cắt ngang từ nhưng văn bản quanh sơ đồ bị lẫn nhãn hình vẽ | 1 |

- **Điểm trung bình A**: `0.00 / 2` (0: 10, 1: 0, 2: 0)
- **Điểm trung bình B & C**: `1.80 / 2` (0: 0, 1: 2, 2: 8)

## 2. Metadata Usefulness (5 câu test × top-3 = 15 bản ghi mỗi chiến lược)

- **Độ chính xác `source`, `page`, `section`**: A đạt `15/15`, B đạt `15/15`, C đạt `15/15`.
- **Tuân thủ filter (`section`)**:
  - Tập `dev` (3 câu `q09`, `q12`, `q15`): A `1/3`, B `1/3`, C `3/3`.
  - Tập `test` (1 câu `q19`): A `0/1`, B `0/1`, C `1/1`.

## 3. Grounding Quality (5 câu test `q16`–`q20`)

| Câu hỏi | Chiến lược A | Điểm A | Chiến lược B | Điểm B | Chiến lược C | Điểm C |
|---|---|---:|---|---:|---|---:|
| `q16` (`GOVERN 4.3`) | Hit #2 chứa đủ câu `GOVERN 4.3` tại trang 29 | 2 | Hit #2 chứa đủ câu `GOVERN 4.3` kèm ngữ cảnh `GOVERN 4` | 2 | Giống B | 2 |
| `q17` (`MEASURE 3.3`) | Hit #1 chứa trọn câu `MEASURE 3.3` tại trang 36 | 2 | Hit #1 chứa trọn câu `MEASURE 3.3` và mục `MEASURE 4` | 2 | Giống B | 2 |
| `q18` (`MANAGE 4.1`) | Hit #1 chứa trọn câu `MANAGE 4.1` tại trang 38 | 2 | Hit #1 chứa trọn `MANAGE 4`, `4.1`, `4.2` | 2 | Giống B | 2 |
| `q19` (`Appendix B`, filter) | Cả 3 hits sai nguồn (`p45`, `p30`, `p22`), không có bằng chứng | 0 | Cả 3 hits sai nguồn (`p45`, `p19`, `p30`), không có bằng chứng | 0 | Hit #2 (`p43-par-00`) trả về đúng đoạn Appendix B nói về `pre-trained models` và `transfer learning` | 2 |
| `q20` (`Appendix C`) | Hit #1 (`p45-fix-01`) đủ câu trả lời dù bị cắt đầu đoạn | 2 | Hit #1 (`p45-par-01`) chứa trọn cả đoạn mở đầu phân tích | 2 | Giống B | 2 |

- **Grounding A**: phân bố `0/1/2` = `1 / 0 / 4`, trung bình `1.60 / 2`
- **Grounding B**: phân bố `0/1/2` = `1 / 0 / 4`, trung bình `1.60 / 2`
- **Grounding C**: phân bố `0/1/2` = `0 / 0 / 5`, trung bình `2.00 / 2`
