# Checklist Nộp Bài

> **Sinh viên:** 2A202600217 — Nguyễn Tiến Đạt  
> **Ngày:** 2026-05-06

## Đối Chiếu Yêu Cầu README

| Yêu cầu | Trạng thái | Minh chứng |
|---|---|---|
| Vai trò agent rõ ràng | Đã làm | `PlannerAgent`, `SupervisorAgent`, `ResearcherAgent`, `AnalystAgent`, `WriterAgent`, `CriticAgent` |
| Shared state đủ cho handoff | Đã làm | `ResearchState` chứa plan, expanded queries, sources, notes, answer, critique, trace, visual graph |
| Guardrail tối thiểu | Đã làm | max iterations, timeout, retry LLM, retry worker, fallback lỗi |
| Trace và giải thích luồng | Đã làm | realtime graph, `reports/trace.json`, `reports/trace_screenshot.md`, `reports/dashboard_latest.json` |
| Benchmark report | Đã làm | `reports/benchmark_report.md` |
| Dashboard trực quan | Đã làm | FastAPI backend + React chatbot dashboard + modal execution graph realtime |
| Search client | Đã làm | SearXNG JSON API, có fallback |
| Unit test | Đã làm | `13 passed`; giữ nguyên bộ test gốc |

## Tài Liệu Nộp

| Tài liệu | Trạng thái |
|---|---|
| GitHub repo cá nhân | Workspace hiện tại sẵn sàng nộp |
| Screenshot trace hoặc link trace | Langfuse Tracing project `day20-track3-multiagent-sys`; UI tại `http://127.0.0.1:5173` |
| `reports/benchmark_report.md` | Đã cập nhật tiếng Việt |
| Giải thích failure mode và cách fix | Có trong benchmark report và trace evidence |
| Peer review | `reports/peer_review_filled.md` |
| Design document | `reports/design_doc.md` |

## Run Log Hiện Tại

```text
Môi trường: E:\Anaconda\envs\VinUni-AgentAI
Backend: http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
SearXNG: http://localhost:8088

lint/typecheck/test:
  ruff check src tests -> All checks passed
  mypy src -> Success: no issues found in 36 source files
  pytest -> 13 passed in 0.16s

frontend:
  npm run build -> vite build succeeded

health:
  backend /api/health -> {"status":"ok"}
  searxng /healthz -> OK
  frontend -> 200 OK
```

## Ghi Chú Còn Lại

- `docs/lab_guide.md` vẫn chứa các marker `TODO(student)` vì đó là nội dung đề bài/lab guide, không phải phần source code chưa làm.
- UI hỗ trợ realtime graph qua `/api/run-stream`.
- OpenAI/Langfuse key thật được đọc từ `.env`; không hard-code và không in secret ra log/report.
