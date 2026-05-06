function MarkdownLike({ title, content }) {
  return (
    <section className="panel inner-panel">
      <div className="section-head compact">
        <div>
          <p className="eyebrow">Output</p>
          <h2>{title}</h2>
        </div>
      </div>
      <pre className="answer-block">{content || 'No content yet.'}</pre>
    </section>
  );
}

export default function AnswerPanel({ payload }) {
  return (
    <div className="stack-column">
      <MarkdownLike title="Final Answer" content={payload?.final_answer} />
      <MarkdownLike title="Research Notes" content={payload?.research_notes} />
      <MarkdownLike title="Analysis Notes" content={payload?.analysis_notes} />
      <MarkdownLike title="Critique Notes" content={payload?.critique_notes} />
    </div>
  );
}
