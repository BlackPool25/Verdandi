import { expect, test } from "@playwright/test";

// Failing-first: red on empty scaffold (no /sim route), green after T4.
test("topology renders 34 nodes + 36 edges", async ({ page }) => {
  await page.goto("/sim");
  await page.getByTestId("topology").waitFor();
  const nodes = page.locator(".react-flow__node");
  await expect(nodes).toHaveCount(34);
  const edges = page.locator(".react-flow__edge");
  await expect(edges).toHaveCount(36);
});
