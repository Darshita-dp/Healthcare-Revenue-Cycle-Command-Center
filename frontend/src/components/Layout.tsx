import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";
import { useFetch } from "./ui";
import {
  IconBook, IconCheckSquare, IconCross, IconGrid, IconList, IconScale, IconShield,
} from "./Icons";
import type { Health } from "../api/types";

const NAV = [
  {
    section: "Operations",
    items: [
      { to: "/", label: "Command Center", icon: <IconGrid size={17} />, end: true },
      { to: "/claims", label: "Claims Work Queue", icon: <IconList size={17} />, end: false },
      { to: "/payers", label: "Payer Performance", icon: <IconScale size={17} />, end: false },
      { to: "/tasks", label: "Follow-Up Tasks", icon: <IconCheckSquare size={17} />, end: false },
    ],
  },
  {
    section: "Reference",
    items: [{ to: "/about", label: "About & Dictionary", icon: <IconBook size={17} />, end: false }],
  },
];

const CRUMBS: [string, string][] = [
  ["/claims/", "Claims Work Queue / Claim Detail"],
  ["/claims", "Claims Work Queue"],
  ["/payers", "Payer Performance"],
  ["/tasks", "Follow-Up Tasks"],
  ["/about", "About & Data Dictionary"],
];

function crumbFor(path: string): string {
  const hit = CRUMBS.find(([p]) => path.startsWith(p));
  return hit ? hit[1] : "Command Center";
}

export default function Layout() {
  const location = useLocation();
  const health = useFetch<Health>(() => api.health());

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="logo-mark">
            <IconCross size={19} strokeWidth={2.2} />
          </span>
          <div>
            <div className="brand-name">Revenue Cycle
              <br />Command Center</div>
          </div>
        </div>
        <nav>
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="nav-section">{group.section}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
                >
                  {item.icon}
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className="pill-safe">
            <IconShield size={12} />
            Synthetic data · No PHI
          </span>
          <br />
          Healthcare operations analytics
          <br />
          Portfolio project · v1.0
        </div>
      </aside>

      <div className="main-col">
        <header className="topbar">
          <div className="crumb">
            Revenue Cycle Operations <span style={{ color: "var(--text-faint)" }}>/</span>{" "}
            <strong>{crumbFor(location.pathname)}</strong>
          </div>
          <div className="topbar-meta">
            <span className="mode-badge">
              <span className="live-dot" />
              {health.data ? `${health.data.mode.toUpperCase()} mode` : "Connecting…"} · Synthetic · No PHI
            </span>
          </div>
        </header>
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
