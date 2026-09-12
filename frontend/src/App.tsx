import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SimPage } from "./sim/SimPage";

export function App(): React.JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/sim" element={<SimPage />} />
        <Route path="*" element={<Navigate to="/sim" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
