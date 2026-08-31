import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

export default function Overview() {
  const events = usePolling(() => api.listEvents(500), 3000);
  const approvals = usePolling(() => api.listApprovals(), 3000);

  if (events.error || approvals.error) {
    return (
      <>
        <h2>Overview</h2>
        <div className="error-banner">
          Can't reach the backend at http://localhost:8000 - is `python
          scripts/start_dev.py` running? ({events.error || approvals.error})
        </div>
      </>
    );
  }

  if (events.loading || approvals.loading) {
    return (
      <>
        <h2>Overview</h2>
        <p className="page-subtitle">Loading…</p>
      </>
    );
  }

  const ev = events.data || [];
  const ap = approvals.data || [];

  const stats = {
    total: ev.length,
    allowed: ev.filter((e) => e.decision === "ALLOW").length,
    blocked: ev.filter((e) => e.decision === "BLOCK").length,
    pendingApproval: ap.filter((a) => a.status === "PENDING").length,
    approved: ap.filter((a) => a.status === "APPROVED").length,
    denied: ap.filter((a) => a.status === "DENIED").length,
  };

  const recent = ev.slice(0, 10);

  return (
    <>
      <h2>Overview</h2>
      <p className="page-subtitle">Last {ev.length} logged tool calls, refreshed every 3s</p>

      <div className="card-grid">
        <div className="card"><div className="value">{stats.total}</div><div className="label">Total actions</div></div>
        <div className="card"><div className="value">{stats.allowed}</div><div className="label">Allowed</div></div>
        <div className="card"><div className="value">{stats.blocked}</div><div className="label">Blocked</div></div>
        <div className="card"><div className="value">{stats.pendingApproval}</div><div className="label">Pending approval</div></div>
        <div className="card"><div className="value">{stats.approved}</div><div className="label">Approved</div></div>
        <div className="card"><div className="value">{stats.denied}</div><div className="label">Denied</div></div>
      </div>

      <h2 style={{ fontSize: 16 }}>Recent activity</h2>
      {recent.length === 0 ? (
        <div className="empty-state">No events yet - run the demo agent to generate some.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Tool</th><th>Agent</th><th>Decision</th><th>Risk</th><th>Status</th><th>Time</th></tr>
          </thead>
          <tbody>
            {recent.map((e) => (
              <tr key={e.event_id}>
                <td>{e.tool_name}</td>
                <td>{e.agent_id}</td>
                <td><span className={`badge badge-${e.decision}`}>{e.decision}</span></td>
                <td>{e.risk_score != null ? `${e.risk_score}/100 (${e.risk_level})` : "-"}</td>
                <td><span className={`badge badge-${e.execution_status}`}>{e.execution_status}</span></td>
                <td>{new Date(e.created_at).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
