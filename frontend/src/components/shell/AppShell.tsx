import type { ReactNode } from "react";
import { LeftRail } from "./LeftRail";
import { TopBar } from "./TopBar";
import "./shell.css";

export function AppShell({
  children,
}: {
  readonly children: ReactNode;
}): React.JSX.Element {
  return (
    <div className="vd-app-shell" data-testid="app-shell">
      <LeftRail />
      <div className="vd-main-content">
        <TopBar />
        <main className="vd-page-outlet" data-testid="page-outlet">
          {children}
        </main>
      </div>
    </div>
  );
}
