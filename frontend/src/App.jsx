import { useState } from "react";
import Overview from "./components/Overview.jsx";
import ApprovalQueue from "./components/ApprovalQueue.jsx";
import TraceViewer from "./components/TraceViewer.jsx";
import Policies from "./components/Policies.jsx";
import ApiKeys from "./components/ApiKeys.jsx";
import Login from "./components/Login.jsx";
import { getToken, clearToken } from "./api.js";

const PAGES = {
  overview: { label: "Overview", component: Overview },
  approvals: { label: "Approval Queue", component: ApprovalQueue },
  traces: { label: "Trace Viewer", component: TraceViewer },
  policies: { label: "Policies", component: Policies },
  keys: { label: "API Keys", component: ApiKeys },
};

export default function App() {
  const [page, setPage] = useState("overview");
  // Week 6: the whole dashboard is now gated on a logged-in session -
  // re-checked on every render via getToken() rather than cached once, so
  // a 401 anywhere (api.js clears the token on 401) reliably drops back to
  // the login screen instead of leaving the UI in a half-authed state.
  const [loggedIn, setLoggedIn] = useState(() => !!getToken());

  if (!loggedIn) {
    return <Login onLoggedIn={() => setLoggedIn(true)} />;
  }

  const Page = PAGES[page].component;

  const logout = () => {
    clearToken();
    setLoggedIn(false);
  };

  return (
    <div className="app">
      <div className="sidebar">
        <h1>Agent Guardrail</h1>
        <p className="subtitle">Runtime safety dashboard</p>
        {Object.entries(PAGES).map(([key, { label }]) => (
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
        <Page />
      </div>
    </div>
  );
}
