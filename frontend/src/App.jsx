import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import GraphView from './components/GraphView';
import SummaryCards from './components/SummaryCards';

const defaultPrompt = 'Research GraphRAG state-of-the-art and write a 500-word summary';

const DOCK_ITEMS = [
  { key: 'execution_graph', label: 'Execution Graph' },
  { key: 'planning_notes', label: 'Planning' },
  { key: 'final_answer', label: 'Final Answer' },
  { key: 'research_notes', label: 'Research Notes' },
  { key: 'analysis_notes', label: 'Analysis Notes' },
  { key: 'critique_notes', label: 'Critique' },
  { key: 'sources', label: 'Sources' },
  { key: 'agent_results', label: 'Agent Runs' },
];

function routeLabel(route) {
  if (!route) return 'Ready';
  return route.charAt(0).toUpperCase() + route.slice(1);
}

function MarkdownText({ content }) {
  const normalizeMarkdown = (raw) => {
    const headings = [
      'Executive Summary',
      'Overview of GraphRAG',
      'Performance Evaluation',
      'Applications and Efficiency Improvements',
      'Best Practices for Optimization',
      'Conflicting or Uncertain Information',
      'Actionable Insights',
      'Conclusion',
      'References',
      'Tài liệu tham khảo',
    ];
    let normalized = raw || '';
    for (const heading of headings) {
      normalized = normalized.replace(new RegExp(`(^|\\n)${heading}\\s*\\n?`, 'g'), `$1## ${heading}\n`);
    }
    normalized = normalized.replace(/\s+(?=\[\d+\]\s)/g, '\n');
    normalized = normalized.replace(/(^|\n)(\*\*[^*\n]+?\*\*:\s*)/g, '$1- $2');
    normalized = normalized.replace(/\s+(?=\d+\.\s+[A-ZÀ-Ỹa-zà-ỹ])/g, '\n');
    normalized = normalized.replace(/\s+(?=###\s+)/g, '\n\n');
    return normalized;
  };

  const text = normalizeMarkdown(content);
  const renderReferences = (raw, key) => {
    const refs = raw
      .replace(/^references\s*/i, '')
      .split(/\s*(?=\[\d+\]\s)/)
      .map((item) => item.trim())
      .filter(Boolean);
    return (
      <div key={key}>
        <h2>Tài liệu tham khảo</h2>
        <ul className="reference-list">
          {refs.map((ref, i) => {
            const match = ref.match(/^(\[\d+\])\s*(.*?)\s+(?:[—-]|URL:)\s*(https?:\/\/\S+)$/i)
              || ref.match(/^(\[\d+\])\s*(.*?)\.\s*URL:\s*(https?:\/\/\S+)$/i);
            if (!match) return <li key={i}>{ref}</li>;
            const [, num, title, url] = match;
            return (
              <li key={i}>
                <span className="ref-index">{num}</span>{' '}
                <a href={url} target="_blank" rel="noreferrer">{title}</a>
              </li>
            );
          })}
        </ul>
      </div>
    );
  };

  if (/(references|tài liệu tham khảo)\s*\n?\[\d+\]/i.test(text)) {
    const [beforeRefs, ...rest] = text.split(/##\s+(?:References|Tài liệu tham khảo)/i);
    const refsText = rest.join('## References').trim();
    return (
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{beforeRefs}</ReactMarkdown>
        {refsText ? renderReferences(refsText, 'refs') : null}
      </div>
    );
  }

  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

function DockModal({ type, payload, onClose }) {
  if (!type) return null;
  const title = DOCK_ITEMS.find((item) => item.key === type)?.label || 'Detail';
  if (type === 'execution_graph') {
    return (
      <div className="modal-backdrop" onClick={onClose}>
        <section className="node-modal graph-modal" onClick={(event) => event.stopPropagation()}>
          <div className="modal-head">
            <div>
              <p className="eyebrow">Execution Graph</p>
              <h2>Agent Call Tree</h2>
            </div>
            <button className="icon-button" type="button" onClick={onClose}>x</button>
          </div>
          <div className="modal-graph-wrap">
            <GraphView graph={payload?.graph} payload={payload} loading={false} />
          </div>
        </section>
      </div>
    );
  }
  let content = payload?.[type] || '';

  if (type === 'sources') {
    content = (payload?.sources || [])
      .map((source, index) => `[${index + 1}] ${source.title}\n${source.url || 'No URL'}\n${source.snippet}`)
      .join('\n\n');
  }
  if (type === 'agent_results') {
    content = (payload?.agent_results || [])
      .map((item, index) => {
        const meta = Object.entries(item.metadata || {}).map(([k, v]) => `${k}: ${v}`).join('\n');
        return `[${index + 1}] ${item.agent}\n${meta}\n\n${item.content}`;
      })
      .join('\n\n---\n\n');
  }
  if (type === 'planning_notes') {
    content = `${payload?.planning_notes || 'No planning notes yet.'}\n\nExpanded queries:\n${(payload?.expanded_queries || []).map((query, index) => `${index + 1}. ${query}`).join('\n')}`;
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section className="node-modal dock-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Workspace</p>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>x</button>
        </div>
        <div className="modal-pre"><MarkdownText content={content || 'No content yet.'} /></div>
      </section>
    </div>
  );
}

export default function App() {
  const [prompt, setPrompt] = useState(defaultPrompt);
  const [audience, setAudience] = useState('technical learners');
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dockModal, setDockModal] = useState(null);

  useEffect(() => {
    fetch('/api/sample')
      .then((res) => res.json())
      .then((data) => setPayload(data))
      .catch(() => {});
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/run-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, audience, max_sources: 5 }),
      });
      if (!res.ok) throw new Error('API request failed');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finalPayload = null;
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() || '';
        for (const chunk of chunks) {
          const eventLine = chunk.split('\n').find((line) => line.startsWith('event:'));
          const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'));
          if (!dataLine) continue;
          const data = JSON.parse(dataLine.slice(5).trim());
          if (eventLine?.includes('error')) throw new Error(data.error || 'Workflow failed');
          setPayload(data);
          if (eventLine?.includes('final')) finalPayload = data;
        }
      }
      if (finalPayload) setPayload(finalPayload);
    } catch (err) {
      setError(err.message || 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  function handleNewChat() {
    setPrompt('');
    setPayload(null);
    setError('');
    setDockModal(null);
  }

  const latestRoute = payload?.route_history?.at(-1);
  const assistantText = payload?.final_answer || 'Nhập câu hỏi để agent bắt đầu nghiên cứu.';
  const dockEnabled = useMemo(() => Boolean(payload) || loading, [payload, loading]);

  return (
    <div className="app-shell">
      <aside className="left-rail">
        <div className="brand-block">
          <div className="brand-mark">AI</div>
          <div>
            <p className="eyebrow">Research Console</p>
            <h1>Agent Chat</h1>
          </div>
        </div>

        <SummaryCards
          summary={payload?.summary}
          qualityScore={payload?.quality_score}
          status={loading ? 'running' : payload?.status}
          routes={payload?.route_history}
        />

        <div className="rail-panel compact-route">
          <p className="eyebrow">Current Route</p>
          <h2>{loading ? 'Thinking' : routeLabel(latestRoute)}</h2>
        </div>

        <nav className="dock-bar side-dock">
          {DOCK_ITEMS.map((item) => (
            <button
              key={item.key}
              type="button"
              className="dock-button"
              disabled={!dockEnabled}
              onClick={() => setDockModal(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <main className="chat-workspace">
        <section className="chat-panel">
          <div className="chat-header">
            <div>
              <p className="eyebrow">Conversation</p>
              <h2>AI Agent</h2>
            </div>
            <div className="chat-actions">
              <button type="button" className="secondary-button" onClick={handleNewChat}>New Chat</button>
              <div className={`status-pill ${loading ? 'is-running' : ''}`}>
                {loading ? 'Running' : payload?.status || 'Ready'}
              </div>
            </div>
          </div>

          <div className="message-list">
            <article className="message-row user-message">
              <div className="avatar">U</div>
              <div className="message-bubble">
                <p>{payload?.query || prompt}</p>
              </div>
            </article>

            <article className="message-row assistant-message">
              <div className="avatar assistant-avatar">A</div>
              {loading ? (
                <div className="message-bubble thinking-bubble">
                  <span />
                  <span />
                  <span />
                </div>
              ) : (
                <div className="message-bubble answer-message">
                  <MarkdownText content={assistantText} />
                </div>
              )}
            </article>
          </div>

          <form onSubmit={handleSubmit} className="composer">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Nhập câu hỏi nghiên cứu..."
            />
            <div className="composer-bar">
              <button type="submit" disabled={loading}>
                {loading ? 'Running...' : 'Send'}
              </button>
            </div>
            {error && <p className="error-text">{error}</p>}
          </form>
        </section>

      </main>

      <DockModal type={dockModal} payload={payload} onClose={() => setDockModal(null)} />
    </div>
  );
}
