import { useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

const EMPTY_FORM = { name: "", tool_name: "", condition: "", action: "REQUIRE_APPROVAL", priority: 100, description: "" };

export default function Policies() {
  const policies = usePolling(() => api.listPolicies(), 5000);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const toggle = async (p) => {
    await api.updatePolicy(p.id, { ...p, enabled: !p.enabled });
    policies.refresh();
  };

  const remove = async (p) => {
    if (!confirm(`Delete policy "${p.name}"?`)) return;
    await api.deletePolicy(p.id);
    policies.refresh();
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.tool_name || !form.action) return;
    setSubmitting(true);
    try {
      await api.createPolicy({
        ...form,
        condition: form.condition.trim() || null,
        priority: Number(form.priority) || 100,
      });
      setForm(EMPTY_FORM);
      policies.refresh();
    } catch (err) {
      alert(`Failed to create policy: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (policies.error) {
    return (
      <>
        <h2>Policies</h2>
        <div className="error-banner">Can't reach the backend at http://localhost:8000 ({policies.error})</div>
      </>
    );
  }

  const rows = policies.data || [];

  return (
    <>
      <h2>Policies</h2>
      <p className="page-subtitle">
        Configurable rules the Policy Engine evaluates against every tool call - no code change or
        deploy needed to add, edit, or disable one.
      </p>

      <form onSubmit={submit} className="form-row">
        <input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="tool_name" value={form.tool_name} onChange={(e) => setForm({ ...form, tool_name: e.target.value })} required />
        <input placeholder="condition (e.g. amount > 5000)" value={form.condition} onChange={(e) => setForm({ ...form, condition: e.target.value })} style={{ minWidth: 200 }} />
        <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
          <option value="ALLOW">ALLOW</option>
          <option value="BLOCK">BLOCK</option>
          <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
        </select>
        <input type="number" placeholder="priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} style={{ width: 80 }} />
        <button className="btn" type="submit" disabled={submitting}>Add policy</button>
      </form>

      {rows.length === 0 ? (
        <div className="empty-state">No policies yet.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Enabled</th><th>Name</th><th>Tool</th><th>Condition</th><th>Action</th><th>Priority</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>
                  <input type="checkbox" className="toggle" checked={p.enabled} onChange={() => toggle(p)} />
                </td>
                <td>{p.name}</td>
                <td>{p.tool_name}</td>
                <td>{p.condition || <span style={{ color: "var(--text-dim)" }}>always</span>}</td>
                <td><span className={`badge badge-${p.action}`}>{p.action}</span></td>
                <td>{p.priority}</td>
                <td><button className="btn" onClick={() => remove(p)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
