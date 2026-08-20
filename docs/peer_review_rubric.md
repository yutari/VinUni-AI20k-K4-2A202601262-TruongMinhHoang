# Peer Review Rubric & Self-Evaluation

Mỗi nhóm review repo/trace của một nhóm khác trong 8 phút theo 5 tiêu chí:

| Tiêu chí | Câu hỏi đánh giá | Đánh giá chi tiết của dự án | Điểm |
|---|---|---|:---:|
| **1. Role clarity** | Mỗi agent có nhiệm vụ rõ, không overlap quá nhiều không? | Phân tách rõ 4 role: **Supervisor** (điều phối routing), **Researcher** (thu thập tài liệu), **Analyst** (tổng hợp & phân tích quan điểm), **Writer** (viết báo cáo Markdown có trích dẫn `[i]`). Không bị chồng chéo nhiệm vụ. | **2/2** |
| **2. State design** | Shared state có đủ thông tin để handoff mà không mất context không? | `ResearchState` lưu trữ toàn diện: `request`, `sources`, `research_notes`, `analysis_notes`, `final_answer`, `agent_results` (token, cost), `trace`, `errors`. Handoff đầy đủ context giữa các node. | **2/2** |
| **3. Failure guard** | Có max iterations, timeout, retry/fallback, validation không? | Đầy đủ: Guardrail `max_iterations = 6`, `timeout_seconds = 60`, `tenacity` retry exponential backoff cho API LLM, fallback sang offline corpus cho Search, validation bằng Pydantic schemas. | **2/2** |
| **4. Benchmark** | Có so sánh single vs multi-agent bằng metric cụ thể không? | Đã chạy benchmark thực tế đo 5 metrics: `Latency` (8.78s vs 24.76s), `Cost` ($0.00046 vs $0.0016), `Quality` (5.0 vs 9.4), `Citation Coverage` (0% vs 100%), `Failure Rate` (0%). Báo cáo lưu tại `reports/benchmark_report.md`. | **2/2** |
| **5. Trace explanation** | Nhóm giải thích được trace: ai làm gì, tốn bao nhiêu, sai ở đâu không? | Tích hợp **LangSmith Tracing** ghi nhận đầy đủ timeline từng span (`supervisor` -> `researcher` -> `analyst` -> `writer`), đo token và chi phí từng agent, có ảnh chụp bằng chứng UI rõ ràng. | **2/2** |
| **TỔNG ĐIỂM** | | **Đạt chuẩn tối đa** | **10/10** |

---

## Feedback Chi Tiết

```text
Strength:
- Kiến trúc hệ thống phân tách role rất rõ ràng, state đầy đủ dữ liệu trung gian giúp việc audit và debug dễ dàng.
- Tích hợp LangSmith và bộ công cụ benchmark tự động đo đạc latency, chi phí token và độ phủ trích dẫn thực tế rất ấn tượng.
- Hệ thống guardrail chống lặp vô hạn và fallback offline hoạt động tốt, đảm bảo độ tin cậy cao.

Risk / failure mode:
- Phụ thuộc vào tốc độ mạng và thời gian phản hồi của LLM khi chạy nhiều bước tuần tự (latency ~24.7s).
- Nếu Search API trả về nguồn kém chất lượng thì Analyst và Writer có thể bị ảnh hưởng theo hiệu ứng dây chuyền (cascade error).

One concrete improvement:
- Có thể thêm cơ chế chạy song song (Parallel execution) khi Researcher tìm kiếm nhiều sub-queries cùng lúc để giảm thời gian phản hồi (latency).
- Thêm node Critic tự động yêu cầu Researcher tìm kiếm bổ sung nếu `citation_coverage` hoặc số lượng nguồn chưa đạt yêu cầu trước khi chuyển sang Writer.

Score: 10/10 (Xuất sắc)
```
