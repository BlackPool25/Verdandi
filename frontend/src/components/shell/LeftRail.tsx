import { useLocation, useNavigate } from "react-router-dom";
import { useTwinStream } from "../../sim/TwinStreamProvider";
import "./shell.css";

interface NavItem {
  readonly id: string;
  readonly label: string;
  readonly icon: string;
  readonly path?: string;
  readonly isAction?: boolean;
}

const NAV_ITEMS: readonly NavItem[] = [
  {
    id: "live",
    label: "Live View",
    icon: "🏭",
    path: "/live",
  },
  {
    id: "anomalies",
    label: "Anomalies",
    icon: "⚠️",
    path: "/anomalies",
  },
  {
    id: "metrics",
    label: "Metrics",
    icon: "📊",
    path: "/metrics",
  },
  {
    id: "guide",
    label: "Guide",
    icon: "📖",
    isAction: true,
  },
];

export function LeftRail(): React.JSX.Element {
  const location = useLocation();
  const navigate = useNavigate();
  const { guideOpen, setGuideOpen, markGuideVisited, hasVisitedGuide } =
    useTwinStream();

  const handleNavClick = (item: NavItem) => {
    if (item.isAction && item.id === "guide") {
      markGuideVisited();
      setGuideOpen(!guideOpen);
      return;
    }
    if (item.path) {
      // Preserve search parameters across page transitions
      navigate(`${item.path}${location.search}`);
    }
  };

  return (
    <nav
      aria-label="primary navigation"
      className="vd-left-rail"
      data-testid="left-rail"
    >
      <div className="vd-rail-logo">
        <span className="vd-rail-logo-glyph">V</span>
      </div>
      <ul className="vd-rail-list">
        {NAV_ITEMS.map((item) => {
          const isActive = item.path
            ? location.pathname === item.path ||
              (item.path === "/live" && location.pathname === "/sim")
            : item.id === "guide" && guideOpen;

          return (
            <li key={item.id} className="vd-rail-item">
              <button
                type="button"
                className={`vd-rail-btn ${isActive ? "is-active" : ""}`}
                data-testid={`nav-${item.id}`}
                aria-current={isActive ? "page" : undefined}
                onClick={() => handleNavClick(item)}
                title={item.label}
              >
                {isActive && <span className="vd-rail-accent-bar" />}
                <span className="vd-rail-icon" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="vd-rail-label">{item.label}</span>
                {item.id === "guide" && !hasVisitedGuide && (
                  <span
                    className="vd-guide-badge"
                    aria-label="unvisited guide indicator"
                  />
                )}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="vd-rail-footer">
        <span className="vd-rail-version">v2.0</span>
      </div>
    </nav>
  );
}
