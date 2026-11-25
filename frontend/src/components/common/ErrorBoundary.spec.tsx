import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import type { ReactElement, ReactNode } from "react";
import { ErrorBoundary } from "./ErrorBoundary";

function findRetryHandler(node: ReactNode): () => void {
  const stack: ReactNode[] = [node];
  while (stack.length > 0) {
    const current = stack.pop();
    if (
      current !== null &&
      typeof current === "object" &&
      "type" in (current as ReactElement) &&
      "props" in (current as ReactElement)
    ) {
      const el = current as ReactElement<{ children?: ReactNode; onClick?: () => void }>;
      if (el.type === "button" && typeof el.props.onClick === "function") {
        return el.props.onClick;
      }
      const kids = el.props.children;
      if (Array.isArray(kids)) {
        stack.push(...kids);
      } else if (kids !== undefined && kids !== null) {
        stack.push(kids);
      }
    }
  }
  throw new Error("retry button not found in ErrorBoundary fallback");
}

describe("ErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    const html = renderToStaticMarkup(
      <ErrorBoundary>
        <div>All good</div>
      </ErrorBoundary>,
    );
    expect(html).toContain("All good");
  });

  it("getDerivedStateFromError captures error state", () => {
    const err = new Error("simulated failure");
    const state = ErrorBoundary.getDerivedStateFromError(err);
    expect(state.hasError).toBe(true);
    expect(state.error).toBe(err);
  });

  it("retry reloads the page instead of re-rendering the identical broken subtree", () => {
    const reload = vi.fn();
    vi.stubGlobal("window", { location: { reload } });
    try {
      const boundary = new ErrorBoundary({ children: null });
      boundary.state = { hasError: true, error: new Error("boom") };
      const setState = vi.spyOn(boundary, "setState");
      const onRetry = findRetryHandler(boundary.render());
      onRetry();
      // Must do a full reload: merely clearing hasError would mount the
      // same throwing children again and loop on the broken tree.
      expect(reload).toHaveBeenCalledTimes(1);
      expect(setState).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
