# Lab Guide: Multi-Agent Research System

## Scenario

Bạn cần xây dựng một research assistant có thể nhận câu hỏi dài, tìm thông tin, phân tích và viết câu trả lời cuối cùng. Lab yêu cầu so sánh hai cách làm:

1. **Single-agent baseline**: một agent làm toàn bộ.
2. **Multi-agent workflow**: Supervisor điều phối Researcher, Analyst, Writer.

## Quy tắc quan trọng

- Không thêm agent nếu không có lý do rõ ràng.
- Mỗi agent phải có responsibility riêng.
- Shared state phải đủ rõ để debug.
- Phải có trace hoặc log cho từng bước.
- Phải benchmark, không chỉ nhìn output bằng cảm tính.

## Milestone 1: Baseline

File gợi ý:

- `src/multi_agent_research_lab/cli.py`
- `src/multi_agent_research_lab/services/llm_client.py`

TODO(student): thay baseline placeholder bằng một call LLM thật.

## Milestone 2: Supervisor

File gợi ý:

- `src/multi_agent_research_lab/agents/supervisor.py`
- `src/multi_agent_research_lab/graph/workflow.py`

TODO(student): implement routing policy.

Gợi ý câu hỏi thiết kế:

- Khi nào gọi Researcher?
- Khi nào gọi Analyst?
- Khi nào gọi Writer?
- Khi nào stop?
- Nếu agent fail thì retry hay fallback?

## Milestone 3: Worker agents

File gợi ý:

- `src/multi_agent_research_lab/agents/researcher.py`
- `src/multi_agent_research_lab/agents/analyst.py`
- `src/multi_agent_research_lab/agents/writer.py`

TODO(student): implement từng worker.

## Milestone 4: Trace và benchmark

File gợi ý:

- `src/multi_agent_research_lab/observability/tracing.py`
- `src/multi_agent_research_lab/evaluation/benchmark.py`
- `src/multi_agent_research_lab/evaluation/report.py`

Benchmark tối thiểu:

| Metric | Cách đo gợi ý |
|---|---|
| Latency | wall-clock time |
| Cost | token usage hoặc provider usage |
| Quality | rubric 0-10 do peer review |
| Citation coverage | số claims có source / tổng claims chính |
| Failure rate | số query fail / tổng query |

## Troubleshooting

### macOS: lỗi SSL certificate khi gọi API qua HTTPS (Tavily, OpenAI, ...)

Triệu chứng: khi implement `SearchClient` (hoặc bất kỳ HTTPS call nào) trên macOS, bạn có thể gặp lỗi kiểu:

```
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
unable to get local issuer certificate
```

Nguyên nhân: Python cài từ python.org trên macOS **không dùng** certificate store của hệ điều hành, nên không tìm thấy CA bundle hợp lệ. Đây là lỗi môi trường, **không phải** do API key sai.

Cách khắc phục (chọn 1 trong 3):

1. **Chạy script cài certificate đi kèm Python** (nhanh nhất):

   ```bash
   /Applications/Python\ 3.12/Install\ Certificates.command
   ```

   (thay `3.12` bằng version Python của bạn)

2. **Dùng `certifi` trong code** — thêm `certifi` vào dependencies, rồi tạo SSL context khi gọi HTTPS:

   ```python
   import certifi
   import ssl
   from urllib.request import urlopen

   ssl_context = ssl.create_default_context(cafile=certifi.where())
   urlopen(request, timeout=timeout, context=ssl_context)
   ```

3. **Set biến môi trường** trỏ tới CA bundle của certifi (không cần đổi code):

   ```bash
   export SSL_CERT_FILE=$(python -m certifi)
   ```

## Exit ticket

Mỗi nhóm trả lời 2 câu:

1. **Case nào nên dùng multi-agent? Vì sao?**
   - **Khi nào nên dùng:**
     - Các tác vụ nghiên cứu sâu, phức tạp (Deep Research, Fact-Checking) đòi hỏi nhiều giai đoạn tách biệt: tìm kiếm thông tin bên ngoài -> lọc và đối chiếu dữ liệu -> viết báo cáo tổng hợp.
     - Các hệ thống cần kiểm toán (Auditability) và debug từng khâu trung gian minh bạch thay vì một hộp đen (black box).
     - Tác vụ cần kết hợp nhiều công cụ hoặc role chuyên biệt (ví dụ: Researcher dùng Search API, Analyst đánh giá logic, Critic kiểm tra trích dẫn).
   - **Vì sao:** Phân chia trách nhiệm (Separation of Concerns) giúp giảm hiện tượng ảo giác (hallucination), tận dụng tối đa context window hiệu quả cho từng role và nâng cao độ chính xác của câu trả lời.

2. **Case nào không nên dùng multi-agent? Vì sao?**
   - **Khi nào không nên dùng:**
     - Các truy vấn đơn giản, câu hỏi tra cứu thông tin trực tiếp (Q&A cơ bản, dịch thuật, tóm tắt văn bản ngắn).
     - Các ứng dụng yêu cầu thời gian phản hồi cực nhanh (Real-time latency < 2s).
     - Các hệ thống bị giới hạn nghiêm ngặt về ngân sách / chi phí Token API.
   - **Vì sao:** Multi-agent làm tăng độ trễ (latency cao gấp 2-3 lần) và chi phí token do phải luân chuyển shared state qua nhiều agent và supervisor. Với các tác vụ đơn giản, single-agent với zero-shot / few-shot prompting vừa nhanh, vừa tiết kiệm và đã đủ đáp ứng yêu cầu.

