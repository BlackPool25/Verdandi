import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { TwinStreamProvider } from "./sim/TwinStreamProvider";
import { AppShell } from "./components/shell/AppShell";
import { SimPage } from "./sim/SimPage";
import { AnomalyPage } from "./components/anomalies/AnomalyPage";
import { lazy, Suspense } from "react";
import { MetricsPage } from "./components/metrics/MetricsPage";

const DiagnosisDemo = lazy(() =>
  import("./demo/DiagnosisDemo").then((m) => ({ default: m.DiagnosisDemo })),
);

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
              {import.meta.env.DEV && (
                <Route
                  path="/demo/diagnosis"
                  element={
                    <Suspense fallback={null}>
                      <DiagnosisDemo />
                    </Suspense>
                  }
                />
              )}
              <Route path="*" element={<SimRedirect />} />
            </Routes>
          </AppShell>
        </TwinStreamProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
