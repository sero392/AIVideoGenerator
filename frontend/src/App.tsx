import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/layouts/AppLayout";
import { NAV_ITEMS } from "@/layouts/navigation";
import { ComingSoonPage } from "@/pages/ComingSoonPage";
import { OverviewPage } from "@/pages/OverviewPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<OverviewPage />} />
        {NAV_ITEMS.filter((item) => item.phase).map((item) => (
          <Route key={item.path} path={item.path.slice(1)} element={<ComingSoonPage item={item} />} />
        ))}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
