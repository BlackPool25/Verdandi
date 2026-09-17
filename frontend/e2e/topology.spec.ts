import { expect, test } from "@playwright/test";

// Topology-A: 28 nodes (26 machines + SBUF + _C7TAIL) + 31 edges.
test("topology renders 28 nodes + 31 edges", async ({ page }) => {
  await page.goto("/sim");
  await page.getByTestId("topology").waitFor();
  const nodes = page.locator(".react-flow__node");
  await expect(nodes).toHaveCount(28);
  const edges = page.locator(".react-flow__edge");
  await expect(edges).toHaveCount(31);
});
