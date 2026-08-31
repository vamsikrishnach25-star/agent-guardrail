import { useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

export default function ApprovalQueue() {
  const [decidedBy, setDecidedBy] = useState(() => localStorage.getItem("guardrail_approver") || "");
  const [busyId, setBusyId] = useState(null);
  const pending = usePolling(() => api.listApprovals("PENDING"), 2500);

  const remember = (name) => {
    setDecidedBy(name);
    localStorage.setItem("guardrail_approver", name);
  };

  const act = async (approvalId, action) => {
    if (!decidedBy.trim()) {
      alert("Enter your name first so the audit trail knows who decided this.");
      return;
    }
    const reason = prompt(`Optional reason for ${action === "approve" ? "approving" : "denying"}:`) || undefined;
    setBusyId(approvalId);
    try {
      if (action === "approve") await api.approveApproval(approvalId, decidedBy, reason);
      else await api.denyApproval(approvalId, decidedBy, reason);
      await pending.refresh();
    } catch (e) {
      alert(`Failed: ${e.message}`);
    } finally {
      setBusyId(null);
    }
  };

  if (pending.error) {
    return (
      <>
        <h2>Approval Queue</h2>
        <div className="error-banner">Can't reach the backend at http://localhost:8000 ({pending.error})</div>
      </>
    );
  }

  const items = pending.data || [];

  return (
    <>
      <h2>Approval Queue</h2>
      <p className="page-subtitle">
        Actions the Decision Engine paused for human sign-off. Refreshes every ~2.5s -
        the waiting agent resumes within a few seconds of your decision here.
      </p>

      <div className="toolbar">
        <label style={{ fontSize: 13, color: "var(--text-dim)" }}>Approving as:</label>
        <input
          placeholder="your name"
          value={decidedBy}
          onChange={(e) => remember(e.target.value)}
        />
      </div>

      {items.length === 0 ? (
        <div className="empty-state">Nothing pending. Try a transfer over ₹5,000 in the demo agent.</div>
      ) : (
        items.map((a) => (
          <div className="approval-card" key={a.id}>
            <div className="row1">
              <div>
                <div className="tool-call">{a.tool_name}({JSON.stringify(a.arguments)})</div>
                <div className="meta">agent: {a.agent_id} · session: {a.session_id}</div>
                <div className="meta">
                  risk: {a.risk_score}/100 <span className={`badge badge-${a.risk_level}`}>{a.risk_level}</span>
                  {"  ·  "}policy: {a.policy_result || "none (risk-based)"}
                </div>
                <div className="meta">reason: {a.reason}</div>
              </div>
            </div>
            <div className="approval-actions">
              <button className="btn btn-approve" disabled={busyId === a.id} onClick={() => act(a.id, "approve")}>
                Approve
              </button>
              <button className="btn btn-deny" disabled={busyId === a.id} onClick={() => act(a.id, "deny")}>
                Deny
              </button>
            </div>
          </div>
        ))
      )}
    </>
  );
}
