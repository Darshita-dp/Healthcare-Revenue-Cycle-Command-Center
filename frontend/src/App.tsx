import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import About from "./pages/About";
import ClaimDetail from "./pages/ClaimDetail";
import ClaimsQueue from "./pages/ClaimsQueue";
import CommandCenter from "./pages/CommandCenter";
import PayerPerformance from "./pages/PayerPerformance";
import Tasks from "./pages/Tasks";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<CommandCenter />} />
        <Route path="claims" element={<ClaimsQueue />} />
        <Route path="claims/:claimId" element={<ClaimDetail />} />
        <Route path="payers" element={<PayerPerformance />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="about" element={<About />} />
      </Route>
    </Routes>
  );
}
