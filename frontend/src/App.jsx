import { useEffect, useState } from "react";
import Overview from "./components/Overview.jsx";
import ApprovalQueue from "./components/ApprovalQueue.jsx";
import TraceViewer from "./components/TraceViewer.jsx";
import Policies from "./components/Policies.jsx";
import ApiKeys from "./components/ApiKeys.jsx";
import Users from "./components/Users.jsx";
import Login from "./components/Login.jsx";
import { api, getToken, clearToken } from "./api.js";

const PAGES = {
  overview: { label: "Overview", component: Overview },
  approvals: { label: "Approval Queue", component: ApprovalQueue },
  traces: { label: "Trace Viewer", component: TraceViewer },
  policies: { label: "Policies", component: Policies },
  keys: { label: "API Keys", component: ApiKeys },
  // Week 11: only ADMIN sees this tab at all - filtered out below. The
  // backend enforces the same restriction independently (require_admin on
  // every route in routers/users.py), so hiding the tab is a UX nicety,
  // not the actual security boundary.
  users: { label: "Users", component: Users, adminOnly: true },
};

export default function App() {
  const [page, setPage] = useState("overview");
  // Week 6: the whole dashboard is now gated on a logged-in session -
  // re-checked on every render via getToken() rather than cached once, so
  // a 401 anywhere (api.js clears the token on 401) reliably drops back to
  // the login screen instead of leaving the UI in a half-authed state.
  const [loggedIn, setLoggedIn] = useState(() => !!getToken());
  // Week 11: who's logged in, including role - fetched once right after
  // login (the login response itself doesn't include role, /me does).
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    if (!loggedIn) {
      setCurrentUser(null);
      return;
    }
    api.me().then(setCurrentUser).catch(() => {});
  }, [loggedIn]);

  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />;
  }

  const role = currentUser?.role;
  const visiblePages = Object.entries(PAGES).filter(([, p]) => !p.adminOnly || role === "ADMIN");
  const Page = (PAGES[page] && (!PAGES[page].adminOnly || role === "ADMIN") ? PAGES[page] : PAGES.overview).component;

  const logout = () => {
    clearToken();
    setLoggedIn(false);
  };

  return (
    <div className="app">
      <div className="sidebar">
        <h1>Agent Guardrail</h1>
        <p className="subtitle">
          Runtime safety dashboard
          {role && <><br />signed in as {currentUser.username} · <strong>{role}</strong></>}
        </p>
        {visiblePages.map(([key, { label }]) => (
          <button
            key={key}
            className={`nav-item ${page === key ? "active" : ""}`}
            onClick={() => setPage(key)}
          >
            {label}
          </button>
        ))}
        <button className="nav-item logout" onClick={logout}>Log out</button>
      </div>
      <div className="main">
        <Page currentUser={currentUser} role={role} />
      </div>
    </div>
  );
}
