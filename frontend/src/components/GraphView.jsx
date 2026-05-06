import { useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Handle, MiniMap, Position } from 'reactflow';

const KIND_META = {
  input: { label: 'INPUT', accent: '#2f6f73' },
  supervisor: { label: 'ROUTER', accent: '#2563eb' },
  agent: { label: 'AGENT', accent: '#7c3aed' },
  tool: { label: 'TOOL', accent: '#0f766e' },
  artifact: { label: 'DATA', accent: '#b45309' },
  terminal: { label: 'END', accent: '#15803d' },
};

const KIND_ORDER = { input: 0, supervisor: 1, agent: 2, tool: 3, artifact: 4, terminal: 5 };

function splitLabel(label = '') {
  const [title, ...rest] = String(label).split('\n');
  return { title, subtitle: rest.join(' ') };
}

function nodeDetail(data) {
  const metadata = data?.metadata || {};
  if (metadata.query) return metadata.query;
  if (metadata.route) return `routes to ${metadata.route}`;
  if (metadata.model_task) return metadata.model_task;
  if (metadata.count !== undefined) return `${metadata.count} collected`;
  if (metadata.sources_found !== undefined) return `${metadata.sources_found} sources`;
  if (metadata.description) return metadata.description;
  return data?.status || '';
}

function formatMetadata(metadata = {}) {
  return Object.entries(metadata)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([key, value]) => {
      const rendered = Array.isArray(value) ? value.join(', ') : String(value);
      return { key, value: rendered };
    });
}

function findAgentResult(payload, agent) {
  if (!agent) return null;
  const results = payload?.agent_results || [];
  return [...results].reverse().find((item) => item.agent === agent) || null;
}

function buildNodeIO(node, payload) {
  const data = node?.data || {};
  const metadata = data.metadata || {};
  const kind = data.kind;
  const agent = metadata.agent;
  const result = findAgentResult(payload, agent);

  if (kind === 'input') {
    return {
      input: payload?.query || data.label,
      output: `Audience: ${metadata.audience || 'technical learners'}`,
      process: 'User prompt enters the supervisor routing loop.',
    };
  }
  if (kind === 'supervisor') {
    return {
      input: `Current route history: ${(metadata.history || []).join(' -> ') || 'none'}`,
      output: `Next route: ${metadata.route || 'unknown'}\nReason: ${metadata.reason || 'n/a'}`,
      process: 'Supervisor inspects workflow state and chooses the next agent.',
    };
  }
  if (kind === 'agent') {
    if (agent === 'planner') {
      return {
        input: payload?.query || 'Original user query is not available yet.',
        output: `${payload?.planning_notes || 'Planning in progress.'}\n\n${(payload?.expanded_queries || []).map((query, index) => `${index + 1}. ${query}`).join('\n')}`,
        process: 'Planner decomposes the original prompt into broader, concrete search angles before Researcher runs.',
      };
    }
    return {
      input: `Agent: ${agent || 'unknown'}\nDescription: ${metadata.description || 'n/a'}`,
      output: result?.content || 'Agent output is not available yet.',
      process: `${metadata.description || nodeDetail(data)}\nTokens in: ${result?.metadata?.tokens_in ?? result?.metadata?.input_tokens ?? 'n/a'}\nTokens out: ${result?.metadata?.tokens_out ?? result?.metadata?.output_tokens ?? 'n/a'}`,
    };
  }
  if (kind === 'tool' && metadata.query) {
    const sources = (payload?.sources || []).slice(0, metadata.max_results || 5);
    return {
      input: `Search query:\n${metadata.query}`,
      output: sources.map((source, index) => `[${index + 1}] ${source.title}\n${source.url || ''}\n${source.snippet}`).join('\n\n') || 'No sources returned yet.',
      process: `SearchClient uses SearXNG when available, then normalizes results into SourceDocument objects.\nMode: ${metadata.mode || 'serial'}`,
    };
  }
  if (kind === 'tool') {
    return {
      input: `Model task: ${metadata.model_task || 'llm.complete'}\nAgent: ${agent || 'unknown'}`,
      output: result?.content || 'LLM output is not available yet.',
      process: 'LLMClient sends the agent prompt to the configured model and records token/cost metadata.',
    };
  }
  if (kind === 'artifact') {
    const label = String(data.label || '').toLowerCase();
    let output = '';
    if (label.includes('research')) output = payload?.research_notes;
    else if (label.includes('analysis')) output = payload?.analysis_notes;
    else if (label.includes('final')) output = payload?.final_answer;
    else if (label.includes('critique')) output = payload?.critique_notes;
    else if (label.includes('search')) output = (payload?.sources || []).map((source) => source.title).join('\n');
    return {
      input: `Artifact generated from parent node.`,
      output: output || nodeDetail(data) || 'Artifact content is not available yet.',
      process: 'The workflow stores this artifact in ResearchState for later agents and the UI.',
    };
  }
  return {
    input: nodeDetail(data),
    output: 'No detailed output captured.',
    process: nodeDetail(data) || 'No process detail captured.',
  };
}

function AgentNode({ data }) {
  const kind = data.kind || 'agent';
  const meta = KIND_META[kind] || KIND_META.agent;
  const { title, subtitle } = splitLabel(data.label);
  const detail = nodeDetail(data);

  return (
    <div className={`flow-node flow-node-${kind}`} style={{ '--accent': meta.accent }}>
      <Handle type="target" position={Position.Top} />
      <div className="node-topline">
        <span className="node-kind">{meta.label}</span>
        {data.iteration ? <span className="node-iteration">#{data.iteration}</span> : null}
      </div>
      <h3>{title}</h3>
      {subtitle && <p className="node-subtitle">{subtitle}</p>}
      {detail && <p className="node-detail">{detail}</p>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

function layoutNodes(nodes = [], edges = []) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const children = new Map();
  const incomingCount = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of edges) {
    if (!nodeById.has(edge.source) || !nodeById.has(edge.target)) continue;
    children.set(edge.source, [...(children.get(edge.source) || []), edge.target]);
    incomingCount.set(edge.target, (incomingCount.get(edge.target) || 0) + 1);
  }

  for (const [id, ids] of children.entries()) {
    children.set(
      id,
      [...new Set(ids)].sort((a, b) => {
        const ak = KIND_ORDER[nodeById.get(a)?.data?.kind] ?? 9;
        const bk = KIND_ORDER[nodeById.get(b)?.data?.kind] ?? 9;
        if (ak !== bk) return ak - bk;
        return String(a).localeCompare(String(b));
      }),
    );
  }

  const roots = nodes.filter((node) => (incomingCount.get(node.id) || 0) === 0);
  const rootIds = (roots.length ? roots : nodes.slice(0, 1)).map((node) => node.id);
  const depth = new Map();
  const parent = new Map();
  const queue = rootIds.map((id) => ({ id, depth: 0 }));
  while (queue.length) {
    const item = queue.shift();
    if (!item || depth.has(item.id)) continue;
    depth.set(item.id, item.depth);
    for (const child of children.get(item.id) || []) {
      if (!parent.has(child)) parent.set(child, item.id);
      queue.push({ id: child, depth: item.depth + 1 });
    }
  }

  nodes.forEach((node) => {
    if (!depth.has(node.id)) depth.set(node.id, 0);
  });

  const treeChildren = new Map(nodes.map((node) => [node.id, []]));
  for (const [child, p] of parent.entries()) {
    treeChildren.get(p)?.push(child);
  }

  let leafCursor = 0;
  const xById = new Map();
  const placed = new Set();
  function assignX(id) {
    if (placed.has(id)) return xById.get(id);
    placed.add(id);
    const kids = treeChildren.get(id) || [];
    if (!kids.length) {
      const x = leafCursor * 300;
      leafCursor += 1;
      xById.set(id, x);
      return x;
    }
    const childXs = kids.map(assignX);
    const min = Math.min(...childXs);
    const max = Math.max(...childXs);
    const x = (min + max) / 2;
    xById.set(id, x);
    return x;
  }
  rootIds.forEach(assignX);
  nodes.forEach((node) => {
    if (!xById.has(node.id)) assignX(node.id);
  });

  const minX = Math.min(...Array.from(xById.values()), 0);
  const maxDepth = Math.max(...Array.from(depth.values()), 0);

  return nodes.map((node, index) => {
    const kind = node.data?.kind || 'agent';
    const sequence = node.data?.metadata?.sequence || node.data?.iteration || index + 1;
    const x = 80 + (xById.get(node.id) || 0) - minX;
    const y = 48 + (depth.get(node.id) || 0) * 185;
    return {
      ...node,
      type: 'agentNode',
      position: { x, y },
      draggable: true,
      style: undefined,
      data: {
        ...node.data,
        metadata: { ...(node.data?.metadata || {}), sequence },
        maxDepth,
      },
    };
  });
}

function styleEdges(edges = []) {
  return edges.map((edge) => ({
    ...edge,
    type: 'smoothstep',
    sourceHandle: null,
    targetHandle: null,
    animated: edge.animated || edge.kind !== 'flow',
    markerEnd: { type: 'arrowclosed', color: '#64748b' },
    style: { stroke: '#64748b', strokeWidth: 2 },
    labelBgStyle: { fill: '#ffffff', fillOpacity: 0.9 },
    labelStyle: { fill: '#334155', fontSize: 11, fontWeight: 700 },
  }));
}

function NodeModal({ node, payload, onClose }) {
  const [showProcess, setShowProcess] = useState(false);
  if (!node) return null;
  const { title, subtitle } = splitLabel(node.data?.label);
  const metadata = formatMetadata(node.data?.metadata);
  const io = buildNodeIO(node, payload);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section className="node-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <p className="eyebrow">Node Detail</p>
            <h2>{title}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose}>x</button>
        </div>
        {subtitle && <p className="modal-subtitle">{subtitle}</p>}
        <div className="modal-actions">
          <button type="button" onClick={() => setShowProcess((value) => !value)}>
            {showProcess ? 'Ẩn quá trình suy luận' : 'Xem quá trình suy luận'}
          </button>
        </div>
        <div className="io-grid">
          <section className="io-card">
            <h3>Input</h3>
            <pre>{io.input || 'No input captured.'}</pre>
          </section>
          <section className="io-card">
            <h3>Output</h3>
            <pre>{io.output || 'No output captured.'}</pre>
          </section>
        </div>
        {showProcess && (
          <div className="reasoning-box">
            <h3>Quá trình node này</h3>
            <pre>{io.process || 'Node này chưa có trace chi tiết riêng.'}</pre>
          </div>
        )}
        <div className="metadata-grid">
          {metadata.length ? metadata.map((item) => (
            <div className="metadata-row" key={item.key}>
              <span>{item.key}</span>
              <strong>{item.value}</strong>
            </div>
          )) : <p className="empty-text">No metadata captured.</p>}
        </div>
      </section>
    </div>
  );
}

export default function GraphView({ graph, payload, loading }) {
  const [selectedNode, setSelectedNode] = useState(null);
  const nodes = useMemo(() => layoutNodes(graph?.nodes || [], graph?.edges || []), [graph]);
  const edges = useMemo(() => styleEdges(graph?.edges || []), [graph]);

  if (loading && !nodes.length) {
    return (
      <div className="graph-canvas graph-loading">
        <div className="pulse-node">Reasoning...</div>
      </div>
    );
  }

  if (!nodes.length) {
    return <div className="empty-state">Send a prompt to build the agent call graph.</div>;
  }

  return (
    <div className="graph-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.25}
        onNodeClick={(_, node) => setSelectedNode(node)}
      >
        <MiniMap pannable zoomable nodeColor={(node) => KIND_META[node.data?.kind]?.accent || '#94a3b8'} />
        <Controls />
        <Background color="#d8dee8" gap={22} />
      </ReactFlow>
      <NodeModal node={selectedNode} payload={payload} onClose={() => setSelectedNode(null)} />
    </div>
  );
}
