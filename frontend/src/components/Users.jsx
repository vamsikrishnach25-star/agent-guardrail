import { useState } from "react";
import { api } from "../api.js";
import { usePolling } from "../usePolling.js";

const EMPTY_FORM = { username: "", password: "", role: "VIEWER" };

// Week 11: admin-only screen (App.jsx only shows this tab for role ===
// "ADMIN", and the backend enforces the same thing independently via
// require_admin - this screen isn't the only thing standing between a
// non-admin and these actions). Provisions accounts; there's no
// self-registration anywhere in this app.
export default function Users({ currentUser }) {
  const users = usePolling(() => api.listUsers(), 5000);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.username || !form.password) return;
    setSubmitting(true);
    try {
      await api.createUser(form.username, form.password, form.role);
      setForm(EMPTY_FORM);
      users.refresh();
    } catch (err) {
      alert(`Failed to create user: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const changeRole = async (u, role) => {
    try {
      await api.updateUserRole(u.id, role);
      users.refresh();
    } catch (err) {
      alert(`Failed to change role: ${err.message}`);
    }
  };

  const remove = async (u) => {
    if (!confirm(`Delete user "${u.username}"? This cannot be undone.`)) return;
    try {
      await api.deleteUser(u.id);
      users.refresh();
    } catch (err) {
      alert(`Failed to delete user: ${err.message}`);
    }
  };

  if (users.error) {
    return (
      <>
        <h2>Users</h2>
        <div className="error-banner">Can't reach the backend ({users.error})</div>
      </>
    );
  }

  const rows = users.data || [];

  return (
    <>
      <h2>Users</h2>
      <p className="page-subtitle">
        ADMIN can manage policies, API keys, and other users' accounts. APPROVER can additionally
        approve/deny (on top of read access). VIEWER is read-only everywhere. There's no
        self-registration - accounts are created here, by an admin.
      </p>

      <form onSubmit={submit} className="form-row">
        <input placeholder="username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
        <input placeholder="password" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
          <option value="VIEWER">VIEWER</option>
          <option value="APPROVER">APPROVER</option>
          <option value="ADMIN">ADMIN</option>
        </select>
        <button className="btn" type="submit" disabled={submitting}>Create user</button>
      </form>

      {rows.length === 0 ? (
        <div className="empty-state">No users yet.</div>
      ) : (
        <table>
          <thead>
            <tr><th>Username</th><th>Role</th><th></th></tr>
          </thead>
          <tbody>
            {rows.map((u) => {
              const isSelf = u.id === currentUser?.id;
              return (
                <tr key={u.id}>
                  <td>{u.username}{isSelf && <span style={{ color: "var(--text-dim)" }}> (you)</span>}</td>
                  <td>
                    <select value={u.role} onChange={(e) => changeRole(u, e.target.value)}>
                      <option value="VIEWER">VIEWER</option>
                      <option value="APPROVER">APPROVER</option>
                      <option value="ADMIN">ADMIN</option>
                    </select>
                  </td>
                  <td>
                    {!isSelf && <button className="btn btn-deny" onClick={() => remove(u)}>Delete</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </>
  );
}
