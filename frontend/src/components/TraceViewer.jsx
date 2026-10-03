import { useEffect, useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";
import ExecutionGraph from "./ExecutionGraph.jsx";

// Groups the flat event log into per-session traces. Week 13 added a
// React Flow graph as a second view of the same data - a toggle, not a
// separate screen, since both views answer the same question ("what did
// this session do") and a chronological timeline already tells that story
// perfectly well on its own; the graph is a visual nicety on top of it,
// not a replacement for it.
function groupBySession(events) {
  const sessions = {};
  for (const e of events) {
    if (!sessions[e.session_id]) sessions[e.session_id] = [];
    sessions[e.session_id].push(e);
  }
  for (const sid in sessions) {
    sessions[sid].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }
  return sessions;
}

export default function TraceViewer() {
  const events = usePolling(() => api.listEvents(500), 4000);
  const [selectedSession, setSelectedSession] = useState(null);
  const [view, setView] = useState("timeline"); // "timeline" | "graph"

  const sessions = events.data ? groupBySession(events.data) : {};
  const sessionIds = Object.keys(sessions).sort((a, b) => {
    const aTime = new Date(sessions[a][sessions[a].length - 1].created_at);
    const bTime = new Date(sessions[b][sessions[b].length - 1].created_at);
    return bTime - aTime;
  });

  useEffect(() => {
    if (!selectedSession && sessionIds.length > 0) setSelectedSession(sessionIds[0]);
  }, [sessionIds.join(",")]);

  if (events.error) {
    return (
      <>
        <h2>Trace Viewer</h2>
        <div className="error-banner">Can't reach the backend at http://localhost:8000 ({events.error})</div>
      </>
    );
  }

  if (sessionIds.length === 0) {
    return (
      <>
        <h2>Trace Viewer</h2>
        <div className="empty-state">No sessions yet - run the demo agent to generate one.</div>
      </>
    );
  }

  const steps = sessions[selectedSession] || [];

  return (
    <>
      <h2>Trace Viewer</h2>
      <p className="page-subtitle">Chronological execution trace per agent session</p>

      <div className="session-list">
        {sessionIds.slice(0, 15).map((sid) => (
          <button
            key={sid}
            className={`session-chip ${sid === selectedSession ? "active" : ""}`}
            onClick={() => setSelectedSession(sid)}
          >
            {sid} ({sessions[sid].length})
          </button>
        ))}
      </div>

      <div className="toolbar">
        <button
          className={`btn ${view === "timeline" ? "toggle-active" : ""}`}
          onClick={() => setView("timeline")}
        >
          Timeline
        </button>
        <button
          className={`btn ${view === "graph" ? "toggle-active" : ""}`}
          onClick={() => setView("graph")}
        >
          Graph
        </button>
      </div>

      {view === "graph" ? (
        <ExecutionGraph steps={steps} />
      ) : (
        <div className="trace">
          {steps.map((e) => (
            <div className="trace-step" key={e.event_id}>
              <div className="dot" />
              <div>
                <div className="tool-name">{e.tool_name}({JSON.stringify(e.arguments)})</div>
                <div className="details">
                  <span className={`badge badge-${e.decision}`}>{e.decision}</span>{" "}
                  {e.policy_result && <>· policy: {e.policy_result}</>}{" "}
                  {e.risk_score != null && <>· risk: {e.risk_score}/100 ({e.risk_level})</>}
                  {e.anomaly_score != null && e.anomaly_score > 0 && (
                    <>{" "}· anomaly: {e.anomaly_score}/100{e.anomaly_reason && ` (${e.anomaly_reason})`}</>
                  )}
                  <br />
                  status: <span className={`badge badge-${e.execution_status}`}>{e.execution_status}</span>
                  {e.result && <>{" "}· result: {JSON.stringify(e.result)}</>}
                  {e.error && <>{" "}· error: {e.error}</>}
                  <br />
                  {new Date(e.created_at).toLocaleString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
