import { useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

const EMPTY_FORM = {
  name: "",
  tool_name: "",
  condition: "",
  conditionDsl: "", // kept as raw text here; parsed to JSON only on submit
  action: "REQUIRE_APPROVAL",
  priority: 100,
  description: "",
};

const EMPTY_SIM = { tool_name: "", agent_id: "simulated-agent", arguments: "{}" };

function ConditionCell({ policy }) {
  if (policy.condition_dsl) {
    return (
      <details>
        <summary style={{ cursor: "pointer", color: "var(--text)" }}>DSL</summary>
        <pre style={{ margin: "6px 0 0", fontSize: 11, whiteSpace: "pre-wrap" }}>
          {JSON.stringify(policy.condition_dsl, null, 2)}
        </pre>
      </details>
    );
  }
  if (policy.condition) return <code>{policy.condition}</code>;
  return <span style={{ color: "var(--text-dim)" }}>always</span>;
}

export default function Policies() {
  const policies = usePolling(() => api.listPolicies(), 5000);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const [sim, setSim] = useState(EMPTY_SIM);
  const [simResult, setSimResult] = useState(null);
  const [simError, setSimError] = useState(null);
  const [simRunning, setSimRunning] = useState(false);

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

    let conditionDsl = null;
    if (form.conditionDsl.trim()) {
      try {
        conditionDsl = JSON.parse(form.conditionDsl);
      } catch (err) {
        alert(`condition_dsl isn't valid JSON: ${err.message}`);
        return;
      }
    }

    setSubmitting(true);
    try {
      await api.createPolicy({
        name: form.name,
        tool_name: form.tool_name,
        condition: form.condition.trim() || null,
        condition_dsl: conditionDsl,
        action: form.action,
        priority: Number(form.priority) || 100,
        description: form.description || null,
      });
      setForm(EMPTY_FORM);
      policies.refresh();
    } catch (err) {
      alert(`Failed to create policy: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const runSimulation = async (e) => {
    e.preventDefault();
    setSimError(null);
    setSimResult(null);

    let args;
    try {
      args = JSON.parse(sim.arguments || "{}");
    } catch (err) {
      setSimError(`arguments isn't valid JSON: ${err.message}`);
      return;
    }

    setSimRunning(true);
    try {
      const result = await api.simulatePolicy({
        tool_name: sim.tool_name,
        agent_id: sim.agent_id || "simulated-agent",
        arguments: args,
      });
      setSimResult(result);
    } catch (err) {
      setSimError(err.message);
    } finally {
      setSimRunning(false);
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
        deploy needed to add, edit, or disable one. Use either a legacy <code>condition</code> string
        (simpleeval, e.g. <code>amount &gt; 5000</code>) or the structured <code>condition_dsl</code> below -
        not both are required, and existing policies using the string form keep working unchanged.
      </p>

      <form onSubmit={submit} className="form-row" style={{ flexWrap: "wrap" }}>
        <input placeholder="name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input placeholder="tool_name" value={form.tool_name} onChange={(e) => setForm({ ...form, tool_name: e.target.value })} required />
        <input placeholder="condition (legacy, e.g. amount > 5000)" value={form.condition} onChange={(e) => setForm({ ...form, condition: e.target.value })} style={{ minWidth: 220 }} />
        <select value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })}>
          <option value="ALLOW">ALLOW</option>
          <option value="BLOCK">BLOCK</option>
          <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
        </select>
        <input type="number" placeholder="priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} style={{ width: 80 }} />
        <button className="btn" type="submit" disabled={submitting}>Add policy</button>

        <textarea
          placeholder={'condition_dsl (JSON, optional) - e.g. {"field": "arguments.amount", "op": "gt", "value": 5000}'}
          value={form.conditionDsl}
          onChange={(e) => setForm({ ...form, conditionDsl: e.target.value })}
          rows={2}
          style={{ width: "100%", fontFamily: "monospace", fontSize: 12, marginTop: 8 }}
        />
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
                <td><ConditionCell policy={p} /></td>
                <td><span className={`badge badge-${p.action}`}>{p.action}</span></td>
                <td>{p.priority}</td>
                <td><button className="btn" onClick={() => remove(p)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="card" style={{ marginTop: 28 }}>
        <h3 style={{ marginTop: 0 }}>Test a call against the live policy set</h3>
        <p className="page-subtitle" style={{ marginBottom: 14 }}>
          Dry-run - runs the same policy/risk/decision pipeline as a real event, but nothing is saved.
          Useful for checking a new or edited policy before agents start hitting it for real.
        </p>
        <form onSubmit={runSimulation} className="form-row" style={{ flexWrap: "wrap" }}>
          <input
            placeholder="tool_name"
            value={sim.tool_name}
            onChange={(e) => setSim({ ...sim, tool_name: e.target.value })}
            required
          />
          <input
            placeholder="agent_id (optional)"
            value={sim.agent_id}
            onChange={(e) => setSim({ ...sim, agent_id: e.target.value })}
          />
          <button className="btn" type="submit" disabled={simRunning}>
            {simRunning ? "Running..." : "Run simulation"}
          </button>
          <textarea
            placeholder='arguments (JSON) - e.g. {"amount": 25000, "account": "ACC1234"}'
            value={sim.arguments}
            onChange={(e) => setSim({ ...sim, arguments: e.target.value })}
            rows={2}
            style={{ width: "100%", fontFamily: "monospace", fontSize: 12, marginTop: 8 }}
          />
        </form>

        {simError && <div className="error-banner" style={{ marginTop: 12 }}>{simError}</div>}

        {simResult && (
          <div style={{ marginTop: 14 }}>
            <span className={`badge badge-${simResult.decision}`}>{simResult.decision}</span>
            {simResult.risk_level && (
              <span className={`badge badge-${simResult.risk_level}`} style={{ marginLeft: 8 }}>
                risk: {simResult.risk_level} ({simResult.risk_score}/100)
              </span>
            )}
            <div style={{ marginTop: 8, fontSize: 13 }}>
              <div><strong>reason:</strong> {simResult.reason || "-"}</div>
              <div>
                <strong>matched policies:</strong>{" "}
                {simResult.matched_policies.length ? simResult.matched_policies.join(", ") : "none"}
              </div>
              {simResult.risk_factors.length > 0 && (
                <div><strong>risk factors:</strong> {simResult.risk_factors.join("; ")}</div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
