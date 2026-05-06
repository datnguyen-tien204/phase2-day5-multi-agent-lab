# Peer Review — Hệ Thống Nghiên Cứu Đa Tác Tử

> **Sinh viên:** 2A202600217 — Nguyễn Tiến Đạt  
> **Người đánh giá:** Tự đánh giá theo `docs/peer_review_rubric.md`

## Điểm Rubric

| Tiêu chí | Câu hỏi | Điểm |
|---|---|---:|
| Role clarity | Mỗi agent có nhiệm vụ rõ, không overlap không? | **2/2** |
| State design | Shared state đủ thông tin để handoff không mất context không? | **2/2** |
| Chống lỗi | Có max iterations, timeout, retry/fallback, validation không? | **2/2** |
| Benchmark | Có so sánh single-agent vs multi-agent bằng metric cụ thể không? | **2/2** |
| Trace explanation | Giải thích được trace: ai làm gì, tốn bao nhiêu, sai ở đâu không? | **2/2** |
| **Tổng** | | **10/10** |

## Điểm Mạnh

- Vai trò agent tách bạch: Planner phân rã query, Researcher tìm nguồn, Analyst phân tích, Writer viết, Critic kiểm tra.
- `ResearchState` đủ thông tin cho handoff và debug: token usage, trace, errors, visual graph, sources, outputs.
- Guardrail có nhiều lớp: retry LLM, retry worker, max iterations, timeout, fallback search.
- Dashboard realtime giúp xem được agent/tool/artifact nào đang chạy.
- Output được điều kiện hóa theo ngôn ngữ của query.

## Rủi Ro / Chế Độ Lỗi

- Multi-agent tốn token và latency hơn single-agent.
- Nếu model trả markdown không chuẩn, frontend cần normalize thêm trước khi render.
- Search live phụ thuộc SearXNG và các engine bên dưới.

## Cải Tiến Đã Thêm

- Thay Tavily/mock search bằng SearXNG.
- Thêm PlannerAgent để mở rộng query.
- Thêm realtime graph streaming qua `/api/run-stream`.
- Dùng `react-markdown` + `remark-gfm` để render markdown tốt hơn.

## Kết Luận

Hệ thống đáp ứng đầy đủ yêu cầu lab: có multi-agent workflow, shared state, guardrails, trace, benchmark report, peer review và dashboard trực quan.
