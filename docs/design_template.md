# Design Document: Multi-Agent Research System

## 1. Problem

Hệ thống cần tự động xử lý các truy vấn nghiên cứu chuyên sâu (complex research queries), tìm kiếm dữ liệu thực tế từ các nguồn bên ngoài, phân tích và đối chiếu thông tin đa chiều, sau đó tổng hợp thành báo cáo kỹ thuật hoàn chỉnh có trích dẫn nguồn kiểm chứng rõ ràng.

---

## 2. Why Multi-Agent?

Mô hình Single-Agent thông thường không đáp ứng tối ưu cho tác vụ nghiên cứu chuyên sâu vì các lý do:
1. **Hallucination & Lack of Grounding**: Single-agent chỉ dựa vào bộ nhớ tham số (parametric memory) của LLM, không tra cứu tài liệu mới nhất hoặc tự bịa ra dữ kiện/nguồn trích dẫn.
2. **Context Pollution & Cognitive Load**: Một prompt đơn lẻ phải gánh cùng lúc việc tìm kiếm, đọc hiểu tài liệu thô, phân tích mâu thuẫn và định dạng văn bản khiến chất lượng từng phần bị suy giảm.
3. **Observability & Debuggability**: Khó kiểm tra và can thiệp vào các bước trung gian khi có lỗi phát sinh.

Hệ thống Multi-Agent giải quyết vấn đề bằng cách **phân rã trách nhiệm (Separation of Concerns)** theo từng vai trò chuyên biệt, giao tiếp qua một **trạng thái chia sẻ (Shared State)** minh bạch.

---

## 3. Agent Roles

| Agent | Responsibility | Input | Output | Failure Mode & Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| **Supervisor** | Điều phối luồng thực thi, quyết định worker tiếp theo và kiểm soát điều kiện dừng | `ResearchState` | `next_route` (`researcher`, `analyst`, `writer`, `done`) | **Lặp vô hạn**: Áp dụng guardrail `max_iterations` và kiểm tra trường dữ liệu còn thiếu. |
| **Researcher** | Tìm kiếm tài liệu ngoài (Tavily/offline corpus) và trích xuất nguồn | `state.request.query` | `state.sources`, `state.research_notes` | **Tìm kiếm lỗi / Không có mạng**: Fallback tự động sang offline knowledge corpus. |
| **Analyst** | Đọc dữ liệu thô, phân tích độ tin cậy, đối chiếu các quan điểm | `state.research_notes` | `state.analysis_notes` | **Bỏ sót luận điểm**: Ép cấu trúc output theo các tiêu chí (themes, trade-offs, evidence strength). |
| **Writer** | Tổng hợp thành bài viết học thuật hoàn chỉnh kèm trích dẫn | `state.research_notes`, `state.analysis_notes` | `state.final_answer` | **Trích dẫn ảo**: Ép buộc cú pháp `[i]` trỏ chính xác về nguồn trong `sources`. |
| **Critic (Bonus)**| Kiểm định chất lượng và độ phủ trích dẫn (citation audit) | `state.sources`, `state.final_answer` | `citation_coverage` metadata | **Thiếu nguồn**: Cảnh báo tỷ lệ trích dẫn đạt dưới 80%. |

---

## 4. Shared State (`ResearchState`)

Các trường dữ liệu trong `ResearchState`:
- `request: ResearchQuery`: Truy vấn gốc, số lượng nguồn tối đa, đối tượng độc giả.
- `iteration: int`: Số vòng lặp đã chạy (dùng cho guardrail chống lặp).
- `route_history: list[str]`: Lịch sử các bước routing đã đi qua (`['researcher', 'analyst', 'writer', 'done']`).
- `sources: list[SourceDocument]`: Danh sách các tài liệu tìm kiếm được (title, URL, snippet).
- `research_notes: str | None`: Ghi chú tổng hợp dữ liệu thô từ Researcher.
- `analysis_notes: str | None`: Bản phân tích đối chiếu chuyên sâu từ Analyst.
- `final_answer: str | None`: Báo cáo hoàn chỉnh cuối cùng từ Writer.
- `agent_results: list[AgentResult]`: Lịch sử kết quả và token usage của từng agent.
- `trace: list[dict]`: Nhật ký sự kiện chi tiết của toàn bộ quy trình.
- `errors: list[str]`: Danh sách các lỗi nếu có.

---

## 5. Routing Policy & Graph Workflow

```text
       [ START ]
           │
           ▼
     ┌───────────┐
 ┌───│Supervisor │◄────────────────────────┐
 │   └─────┬─────┘                         │
 │         │                               │
 │         ├─────────► [Researcher] ───────┤
 │         ├─────────► [Analyst]    ───────┤
 │         └─────────► [Writer]     ───────┘
 │ (done / max_iter)
 ▼
[ END ]
```

- Nếu chưa có `sources` $\rightarrow$ chuyển đến `Researcher`.
- Đã có `sources`, chưa có `analysis_notes` $\rightarrow$ chuyển đến `Analyst`.
- Đã có `analysis_notes`, chưa có `final_answer` $\rightarrow$ chuyển đến `Writer`.
- Đã có `final_answer` hoặc `iteration >= max_iterations` $\rightarrow$ kết thúc (`done` $\rightarrow$ `END`).

---

## 6. Guardrails & Reliability

- **Max Iterations**: Giới hạn tối đa 6 vòng lặp (cấu hình trong `.env`).
- **Timeout**: Timeout 60 giây cho mỗi lượt gọi mạng / LLM.
- **Retry**: Sử dụng `tenacity` với Exponential Backoff tự động retry 3 lần cho các lỗi mạng / rate limit / API timeout.
- **Fallback**: Tự động chuyển sang tìm kiếm trong bộ dữ liệu ngoại tuyến (`ai_agent_offline_research_corpus_v2`) nếu không có Tavily API key hoặc lỗi mạng.
- **Validation**: Kiểm tra kiểu dữ liệu đầu vào / đầu ra bằng Pydantic schemas.

---

## 7. Benchmark Plan

- **Queries**: `"Research GraphRAG state-of-the-art"`, các câu hỏi so sánh kiến trúc AI Agent.
- **Metrics đo lường**:
  1. *Latency (wall-clock time)*.
  2. *Token Usage & Cost (USD)*.
  3. *Citation Coverage* (Tỷ lệ nguồn được trích dẫn thực tế trong báo cáo).
  4. *Quality Score* (Độ sâu phân tích, cấu trúc và tính khoa học).
