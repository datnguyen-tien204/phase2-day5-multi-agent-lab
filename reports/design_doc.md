# Tài Liệu Thiết Kế — Hệ Thống Nghiên Cứu Đa Tác Tử

> **Sinh viên:** 2A202600217 — Nguyễn Tiến Đạt

## Bài Toán

Xây dựng một trợ lý nghiên cứu có thể xử lý câu hỏi nhiều bước: phân rã truy vấn, tìm nguồn, phân tích bằng chứng, viết câu trả lời cuối cùng, và kiểm tra chất lượng. Hệ thống cần có trace rõ ràng để giải thích agent nào làm gì, dùng công cụ nào, tốn bao nhiêu token, và tạo ra artifact nào.

## Vì Sao Dùng Multi-Agent?

Một prompt đơn lẻ khó tối ưu đồng thời cho nhiều mục tiêu: mở rộng truy vấn, tìm nguồn rộng, phân tích nghiêm ngặt, viết mạch lạc, và fact-check. Multi-agent tách các trách nhiệm này thành từng vai trò chuyên biệt, giúp dễ kiểm soát chất lượng và dễ debug hơn.

## Vai Trò Agent

| Agent | Trách nhiệm | Đầu vào | Đầu ra |
|---|---|---|---|
| Planner | Phân rã câu hỏi, mở rộng góc tìm kiếm | Câu hỏi gốc | `planning_notes`, `expanded_queries` |
| Supervisor | Điều phối route và guardrail | Toàn bộ `ResearchState` | Route kế tiếp |
| Researcher | Tìm nguồn bằng SearXNG và tổng hợp notes | Query đã mở rộng | `sources`, `research_notes` |
| Analyst | Phân tích claim, độ mạnh bằng chứng, khoảng trống | `research_notes` | `analysis_notes` |
| Writer | Viết câu trả lời cuối cùng có citation | Notes + analysis + sources | `final_answer` |
| Critic | Kiểm tra factuality, citation, chất lượng | Final answer + sources | `critique_notes`, `quality_score` |

## Shared State

`ResearchState` là nơi handoff giữa các agent. Các trường chính:

| Trường | Mục đích |
|---|---|
| `request` | Câu hỏi gốc, audience, max sources |
| `planning_notes`, `expanded_queries` | Kế hoạch nghiên cứu trước khi search |
| `sources` | Tài liệu thu thập được |
| `research_notes`, `analysis_notes`, `final_answer`, `critique_notes` | Artifact chính của các agent |
| `route_history`, `transitions` | Lịch sử điều phối |
| `token_usage` | Theo dõi token/cost theo agent |
| `visual_nodes`, `visual_edges` | Dữ liệu graph realtime cho frontend |
| `trace`, `errors` | Quan sát và xử lý lỗi |

## Luồng Điều Phối

```text
User Prompt
  -> PlannerAgent
  -> SupervisorAgent
  -> ResearcherAgent
       -> SearchClient.search qua SearXNG
       -> LLMClient.complete để tổng hợp research notes
  -> AnalystAgent
  -> WriterAgent
  -> CriticAgent
  -> done hoặc revision loop
```

## Guardrails

- Giới hạn vòng lặp bằng `MAX_ITERATIONS`.
- Timeout workflow bằng `TIMEOUT_SECONDS`.
- Retry LLM bằng `tenacity`.
- Retry worker một lần trong `_safe_run`.
- Nếu SearXNG lỗi, `SearchClient` fallback để workflow không chết.
- Pydantic schema kiểm soát input/output chính.
- Output được yêu cầu cùng ngôn ngữ với query của người dùng.

## Dashboard

Frontend React hiển thị dạng chatbot, có dock bên trái để mở modal:

- Execution Graph realtime
- Planning
- Final Answer
- Research Notes
- Analysis Notes
- Critique
- Sources
- Agent Runs

Backend stream graph qua `/api/run-stream`, giúp người dùng quan sát node sinh ra khi agent đang chạy.
