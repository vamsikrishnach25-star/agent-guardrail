// Thin fetch wrapper around the Guardrail backend. Deliberately no state
// management library here - four screens polling a REST API don't need
// one, and pulling in Redux/Zustand would be complexity for its own sake.
//
// VITE_API_URL is baked in at build time (see frontend/.env.example and
// docker-compose.yml). Falls back to localhost:8000 for plain `npm run dev`.
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const resp = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

export const api = {
  health: () => request("/health"),

  listEvents: (limit = 200) => request(`/api/v1/events?limit=${limit}`),

  listApprovals: (status) =>
    request(`/api/v1/approvals${status ? `?status=${status}` : ""}`),
  approveApproval: (id, decidedBy, reason) =>
    request(`/api/v1/approvals/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, reason }),
    }),
  denyApproval: (id, decidedBy, reason) =>
    request(`/api/v1/approvals/${id}/deny`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, reason }),
    }),

  listPolicies: () => request("/api/v1/policies"),
  createPolicy: (policy) =>
    request("/api/v1/policies", { method: "POST", body: JSON.stringify(policy) }),
  updatePolicy: (id, policy) =>
    request(`/api/v1/policies/${id}`, { method: "PATCH", body: JSON.stringify(policy) }),
  deletePolicy: (id) => request(`/api/v1/policies/${id}`, { method: "DELETE" }),
};
