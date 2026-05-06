# Workflow Visualisation

## What was added

- `visual_nodes` and `visual_edges` inside `ResearchState`
- graph payload builder in `services/visualization.py`
- FastAPI backend in `src/multi_agent_research_lab/api/app.py`
- React dashboard in `frontend/`
- draw.io architecture file in `docs/architecture.drawio`

## Run the dashboard

### Backend

```bash
pip install -e .[api]
malab serve-api --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL, enter a prompt, then inspect:
- the execution graph
- supervisor transitions
- trace spans
- collected sources
- final answer / intermediate artifacts

## Export graph data without the UI

```bash
malab visualize -q "Research GraphRAG state-of-the-art and write a 500-word summary"
```

This writes `reports/dashboard_latest.json`, which the frontend can load as sample data.
