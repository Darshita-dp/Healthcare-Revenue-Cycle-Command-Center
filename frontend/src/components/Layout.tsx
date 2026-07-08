import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Command Center", icon: "◧", end: true },
  { to: "/claims", label: "Claims Work Queue", icon: "☰", end: false },
  { to: "/payers", label: "Payer Performance", icon: "⛁", end: false },
  { to: "/tasks", label: "Follow-Up Tasks", icon: "✓", end: false },
  { to: "/about", label: "About & Dictionary", icon: "ℹ", end: false },
];

export default function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo">
            <span className="logo-mark">⚕</span>
            RCM Command Center
          </div>
          <div className="sub">Revenue Cycle Operations</div>
        </div>
        <nav>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              <span className="icon">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          Synthetic data only — no PHI.
          <br />
          Portfolio project · v1.0
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
