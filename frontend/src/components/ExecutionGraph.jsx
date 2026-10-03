import { useMemo } from "react";
import ReactFlow, { Background, Handle, Position } from "reactflow";
import "reactflow/dist/style.css";

// Week 13: the React Flow graph TraceViewer.jsx's own comment flagged as a
// "nicer upgrade later" back when the timeline view was built. Deliberately
// built as a second view of the *same* session data, not a new screen - no
// new backend endpoint, same principle as the rest of this dashboard (see
// README's "the dashboard needed zero new backend endpoints" design note).
//
// Layout is a plain left-to-right chain, not an auto-layout algorithm
// (e.g. dagre) - because the data genuinely is a chain: `steps` is one
// session's events in chronological order, and nothing in this system
// currently records branching or parallel tool calls within a session.
// Reaching for a layout engine to arrange a line would be solving a
// problem this data doesn't have; if agents ever call tools concurrently,
// this is the first place that would need to change.

const DECISION_COLOR = {
  ALLOW: "var(--green)",
  BLOCK: "var(--red)",
  REQUIRE_APPROVAL: "var(--amber)",
};

function EventNode({ data }) {
  const { event, isFirst, isLast } = data;
  const color = DECISION_COLOR[event.decision] || "var(--border)";
  const anomalous = event.anomaly_score != null && event.anomaly_score > 0;

  return (
    <div
      style={{
        background: "var(--surface)",
        border: `1.5px solid ${color}`,
        borderRadius: 10,
        padding: "10px 14px",
        width: 210,
        fontSize: 12,
        boxShadow: anomalous ? `0 0 0 2px rgba(240,169,58,0.35)` : "none",
      }}
    >
      {!isFirst && <Handle type="target" position={Position.Left} style={{ background: color }} />}
      <div style={{ fontFamily: "Cascadia Code, Consolas, monospace", fontWeight: 600, fontSize: 13 }}>
        {event.tool_name}
      </div>
      <div style={{ color: "var(--text-dim)", margin: "4px 0", wordBreak: "break-all" }}>
        {JSON.stringify(event.arguments)}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
        <span className={`badge badge-${event.decision}`}>{event.decision}</span>
        <span className={`badge badge-${event.execution_status}`}>{event.execution_status}</span>
        {anomalous && (
          <span className="badge badge-REQUIRE_APPROVAL" title={event.anomaly_reason || ""}>
            anomaly {event.anomaly_score}
          </span>
        )}
      </div>
      {event.risk_score != null && (
        <div style={{ color: "var(--text-dim)", marginTop: 4 }}>
          risk: {event.risk_score}/100 ({event.risk_level})
        </div>
      )}
      {!isLast && <Handle type="source" position={Position.Right} style={{ background: color }} />}
    </div>
  );
}

const nodeTypes = { event: EventNode };

export default function ExecutionGraph({ steps }) {
  const { nodes, edges } = useMemo(() => {
    const nodes = steps.map((event, i) => ({
      id: event.event_id,
      type: "event",
      position: { x: i * 260, y: (i % 2) * 90 },
      data: { event, isFirst: i === 0, isLast: i === steps.length - 1 },
      draggable: false,
    }));

    const edges = steps.slice(1).map((event, i) => ({
      id: `${steps[i].event_id}->${event.event_id}`,
      source: steps[i].event_id,
      target: event.event_id,
      animated: event.execution_status === "PENDING",
      style: { stroke: "var(--border)" },
    }));

    return { nodes, edges };
  }, [steps]);

  return (
    <div style={{ height: 420, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="var(--border)" gap={24} />
      </ReactFlow>
    </div>
  );
}
