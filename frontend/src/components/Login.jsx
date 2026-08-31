import { useState } from "react";
import { api } from "../api.js";

export default function Login({ onLoggedIn }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.login(username, password);
      onLoggedIn();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={submit}>
        <h1>Agent Guardrail</h1>
        <p className="subtitle">Sign in to view the dashboard</p>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <label>Password</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="error-banner">{error}</div>}
        <button className="btn btn-approve" type="submit" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
        <p className="login-hint">
          First run? Check the backend's console output on startup for the
          seeded admin username/password.
        </p>
      </form>
    </div>
  );
}
