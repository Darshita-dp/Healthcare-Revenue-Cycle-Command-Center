import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";

// Route-level code splitting: each page (and its Recharts imports on the
// Command Center) loads on demand, shrinking the initial bundle and keeping
// the first paint fast even on slow connections.
const CommandCenter    = lazy(() => import("./pages/CommandCenter"));
const ClaimsQueue      = lazy(() => import("./pages/ClaimsQueue"));
const ClaimDetail      = lazy(() => import("./pages/ClaimDetail"));
const PayerPerformance = lazy(() => import("./pages/PayerPerformance"));
const Tasks            = lazy(() => import("./pages/Tasks"));
const About            = lazy(() => import("./pages/About"));

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={
          <Suspense fallback={<Loading label="Loading command center…" />}>
            <CommandCenter />
          </Suspense>
        } />
        <Route path="claims" element={
          <Suspense fallback={<Loading label="Loading work queue…" />}>
            <ClaimsQueue />
          </Suspense>
        } />
        <Route path="claims/:claimId" element={
          <Suspense fallback={<Loading label="Loading claim…" />}>
            <ClaimDetail />
          </Suspense>
        } />
        <Route path="payers" element={
          <Suspense fallback={<Loading label="Loading payer scorecards…" />}>
            <PayerPerformance />
          </Suspense>
        } />
        <Route path="tasks" element={
          <Suspense fallback={<Loading label="Loading tasks…" />}>
            <Tasks />
          </Suspense>
        } />
        <Route path="about" element={
          <Suspense fallback={<Loading label="Loading…" />}>
            <About />
          </Suspense>
        } />
      </Route>
    </Routes>
  );
}
