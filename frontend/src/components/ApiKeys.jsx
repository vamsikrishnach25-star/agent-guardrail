import { useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

// Week 6: lets a logged-in dashboard user mint/revoke agent API keys
// without touching the backend directly. The raw key is shown exactly
// once, right after creation - after that only a hash is stored, same as
// GitHub/Stripe API keys, so this screen genuinely can't show it again.
export default function ApiKeys() {
  const keys = usePolling(() => api.listKeys(), 5000);
  const [agentId, setAgentId] = useState("");
  const [label, setLabel] = useState("");
  const [justCreated, setJustCreated] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!agentId.trim()) return;
    setSubmitting(true);
    try {
      const created = await api.createKey(agentId.trim(), label.trim() || null);
      setJustCreated(created);
      setAgentId("");
      setLabel("");
      keys.refresh();
    } catch (err) {
      alert(`Failed to create key: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const revoke = async (k) => {
    if (!confirm(`Revoke the API key for agent "${k.agent_id}" (${k.key_preview})? This cannot be undone.`)) return;
    await api.revokeKey(k.id);
    keys.refresh();
  };

  if (keys.error) {
    return (
      <>
        <h2>API Keys</h2>
        <div className="error-banner">Can't reach the backend ({keys.error})</div>
      </>
    );
  }

  const rows = keys.data || [];

  return (
    <>
      <h2>API Keys</h2>
      <p className="page-subtitle">
        Credentials the Guardrail SDK uses to authenticate as a specific agent_id.
        A key can only report events under its own agent_id - see backend/app/routers/events.py.
      </p>

      {justCreated && (
        <div className="key-reveal">
          <strong>New key for "{justCreated.agent_id}" - copy it now, it won't be shown again:</strong>
          <code>{justCreated.raw_key}</code>
          <button className="btn" onClick={() => setJustCreated(null)}>Dismiss</button>
        </div>
      )}

      <form onSubmit={submit} className="form-row">
        <input placeholder="agent_id (e.g. finance-agent)" value={agentId} onChange={(e) => setAgentId(e.target.value)} required />
        <input placeholder="label (optional)" value={label} onChange={(e) => setLabel(e.target.value)} />
        <button className="btn" type="submit" disabled={submitting}>Create key</button>
      </form>

      {rows.length === 0 ? (
        <div className="empty-state">No API keys yet.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Agent</th><th>Label</th><th>Key</th><th>Created</th><th>Status</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((k) => (
              <tr key={k.id}>
                <td>{k.agent_id}</td>
                <td>{k.label || <span style={{ color: "var(--text-dim)" }}>—</span>}</td>
                <td><code>{k.key_preview}</code></td>
                <td>{k.created_at ? new Date(k.created_at).toLocaleString() : ""}</td>
                <td>{k.revoked_at ? <span className="badge badge-BLOCK">revoked</span> : <span className="badge badge-ALLOW">active</span>}</td>
                <td>{!k.revoked_at && <button className="btn btn-deny" onClick={() => revoke(k)}>Revoke</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
