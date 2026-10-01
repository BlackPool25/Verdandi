import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

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
});
