import { resolve } from "node:path";

// CI sets LOGOS_QT_MCP automatically; for interactive use: nix build .#test-framework -o result-mcp
const root =
  process.env.LOGOS_QT_MCP ||
  new URL("../result-mcp", import.meta.url).pathname;
const { test, run } = await import(
  resolve(root, "test-framework/framework.mjs")
);

test("calc_ui: loads and shows title", async (app) => {
  await app.waitFor(
    async () => {
      await app.expectTexts(["Logos Calculator"]);
    },
    { timeout: 15000, interval: 500, description: "calc_ui to load" },
  );
});

test("calc_ui: add button visible", async (app) => {
  await app.expectTexts(["Add"]);
});

test("calc_ui: click add shows validation", async (app) => {
  await app.click("Add");
  await app.waitFor(
    async () => {
      await app.expectTexts(["Enter values for a and b"]);
    },
    { timeout: 5000, interval: 500, description: "validation message to appear" },
  );
});

run();
