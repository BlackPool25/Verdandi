import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { TwinStreamProvider } from "./sim/TwinStreamProvider";
import { AppShell } from "./components/shell/AppShell";
import { SimPage } from "./sim/SimPage";
import { AnomalyPage } from "./components/anomalies/AnomalyPage";
import { MetricsPage } from "./components/metrics/MetricsPage";

function SimRedirect(): React.JSX.Element {
  const location = useLocation();
  return <Navigate to={`/live${location.search}`} replace />;
}

export function App(): React.JSX.Element {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <TwinStreamProvider>
          <AppShell>
            <Routes>
              <Route path="/live" element={<SimPage />} />
              <Route path="/sim" element={<SimRedirect />} />
              <Route path="/anomalies" element={<AnomalyPage />} />
              <Route path="/metrics" element={<MetricsPage />} />
              <Route path="*" element={<SimRedirect />} />
            </Routes>
          </AppShell>
        </TwinStreamProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
