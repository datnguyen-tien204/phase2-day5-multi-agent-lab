# React Dashboard

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

## Run backend API

From the project root:

```bash
pip install -e .[api]
malab serve-api --host 127.0.0.1 --port 8000
```

Then open the Vite URL (normally `http://127.0.0.1:5173`).

The UI lets you:
- enter a prompt
- run the workflow
- see agent/tool calls on a graph
- inspect transitions, trace events, sources, and the final answer
