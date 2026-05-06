export default function TimelinePanel({ transitions = [], traces = [], sources = [] }) {
  return (
    <div className="stack-column">
      <section className="panel inner-panel">
        <div className="section-head compact">
          <div>
            <p className="eyebrow">Transitions</p>
            <h2>Supervisor Decisions</h2>
          </div>
        </div>
        <div className="scroll-list">
          {transitions.length ? transitions.map((item, idx) => (
            <article className="timeline-item" key={`${item.to_route}-${idx}`}>
              <h4>{item.from_route || 'START'} → {item.to_route}</h4>
              <p>Reason: <strong>{item.reason}</strong></p>
              <p>Iteration: {item.iteration}</p>
            </article>
          )) : <p className="empty-text">No transitions yet.</p>}
        </div>
      </section>

      <section className="panel inner-panel">
        <div className="section-head compact">
          <div>
            <p className="eyebrow">Trace</p>
            <h2>Span Timeline</h2>
          </div>
        </div>
        <div className="scroll-list">
          {traces.length ? traces.map((item, idx) => (
            <article className="timeline-item" key={`${item.name}-${idx}`}>
              <h4>{item.name}</h4>
              <p>Started: {item.payload?.started_at || '—'}</p>
              <p>Duration: {item.payload?.duration_seconds || '—'}s</p>
            </article>
          )) : <p className="empty-text">No trace events yet.</p>}
        </div>
      </section>

      <section className="panel inner-panel">
        <div className="section-head compact">
          <div>
            <p className="eyebrow">Sources</p>
            <h2>Collected References</h2>
          </div>
        </div>
        <div className="scroll-list">
          {sources.length ? sources.map((source, idx) => (
            <article className="timeline-item" key={`${source.url || source.title}-${idx}`}>
              <h4>{source.title}</h4>
              <p>{source.url || 'No URL'}</p>
              <p>{source.snippet}</p>
            </article>
          )) : <p className="empty-text">No sources collected yet.</p>}
        </div>
      </section>
    </div>
  );
}
