function metric(value, fallback = '—') {
  return value === null || value === undefined || value === '' ? fallback : value;
}

export default function SummaryCards({ summary, qualityScore, status, routes }) {
  const cards = [
    { title: 'Status', value: metric(status) },
    { title: 'Iterations', value: metric(summary?.iterations) },
    { title: 'Quality Score', value: metric(qualityScore) },
    { title: 'Sources', value: metric(summary?.sources) },
    { title: 'Input Tokens', value: metric(summary?.input_tokens) },
    { title: 'Output Tokens', value: metric(summary?.output_tokens) },
  ];

  return (
    <section className="summary-grid">
      {cards.map((card) => (
        <article className="summary-card" key={card.title}>
          <span>{card.title}</span>
          <strong>{card.value}</strong>
        </article>
      ))}
      <article className="summary-card route-card">
        <span>Route History</span>
        <strong>{routes?.length ? routes.join(' → ') : '—'}</strong>
      </article>
    </section>
  );
}
