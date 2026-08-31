import { useState } from "react";
import Overview from "./components/Overview.jsx";
import ApprovalQueue from "./components/ApprovalQueue.jsx";
import TraceViewer from "./components/TraceViewer.jsx";
import Policies from "./components/Policies.jsx";

const PAGES = {
  overview: { label: "Overview", component: Overview },
  approvals: { label: "Approval Queue", component: ApprovalQueue },
  traces: { label: "Trace Viewer", component: TraceViewer },
  policies: { label: "Policies", component: Policies },
};

export default function App() {
  const [page, setPage] = useState("overview");
  const Page = PAGES[page].component;

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
      </div>
      <div className="main">
        <Page />
      </div>
    </div>
  );
}
