// Thin fetch wrapper around the Guardrail backend. Deliberately no state
// management library here - four screens polling a REST API don't need
// one, and pulling in Redux/Zustand would be complexity for its own sake.
//
// VITE_API_URL is baked in at build time (see frontend/.env.example and
// docker-compose.yml). Falls back to localhost:8000 for plain `npm run dev`.
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Week 6: every dashboard screen now requires a logged-in session. The JWT
// lives in localStorage (this is a real deployed app running in the user's
// own browser, not an in-conversation preview, so localStorage is the
// right place for it) and is attached to every request. A 401 anywhere
// means the session expired or was never established - `auth.js`-equivalent
// logic below clears it and lets App.jsx fall back to the login screen.
const TOKEN_KEY = "guardrail_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

class UnauthorizedError extends Error {}

async function request(path, options = {}) {
  const token = getToken();
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  });
  if (resp.status === 401) {
    clearToken();
    throw new UnauthorizedError("session expired - please log in again");
  }
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  health: () => request("/health"),

  login: async (username, password) => {
    const resp = await fetch(`${BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `login failed (${resp.status})`);
    }
    const data = await resp.json();
    setToken(data.access_token);
    return data;
  },

  listEvents: (limit = 200) => request(`/api/v1/events?limit=${limit}`),

  listApprovals: (status) =>
    request(`/api/v1/approvals${status ? `?status=${status}` : ""}`),
  // decided_by is no longer sent by the client - the backend derives it
  // from the authenticated session (see backend/app/routers/approvals.py).
  approveApproval: (id, reason) =>
    request(`/api/v1/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  denyApproval: (id, reason) =>
    request(`/api/v1/approvals/${id}/deny`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  listPolicies: () => request("/api/v1/policies"),
  createPolicy: (policy) =>
    request("/api/v1/policies", { method: "POST", body: JSON.stringify(policy) }),
  updatePolicy: (id, policy) =>
    request(`/api/v1/policies/${id}`, { method: "PATCH", body: JSON.stringify(policy) }),
  deletePolicy: (id) => request(`/api/v1/policies/${id}`, { method: "DELETE" }),
  // Week 9: dry-run a hypothetical call against the live policy set -
  // nothing gets persisted, so this is safe to use as a "test before you
  // save" preview.
  simulatePolicy: (payload) =>
    request("/api/v1/policies/simulate", { method: "POST", body: JSON.stringify(payload) }),

  listKeys: () => request("/api/v1/keys"),
  createKey: (agentId, label) =>
    request("/api/v1/keys", { method: "POST", body: JSON.stringify({ agent_id: agentId, label }) }),
  revokeKey: (id) => request(`/api/v1/keys/${id}/revoke`, { method: "POST" }),
};
