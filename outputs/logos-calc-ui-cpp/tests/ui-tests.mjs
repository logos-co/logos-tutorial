import { resolve } from "node:path";

// CI sets LOGOS_QT_MCP automatically; for interactive use: nix build .#test-framework -o result-mcp
const root =
  process.env.LOGOS_QT_MCP ||
  new URL("../result-mcp", import.meta.url).pathname;
const { test, run } = await import(
  resolve(root, "test-framework/framework.mjs")
);

test("calc_ui_cpp: loads and shows title", async (app) => {
  await app.waitFor(
    async () => {
      await app.expectTexts(["Logos Calculator (C++ backend)"]);
    },
    { timeout: 15000, interval: 500, description: "UI to load" },
  );
});

test("calc_ui_cpp: operation buttons visible", async (app) => {
  await app.expectTexts(["Add", "Multiply", "Factorial", "Fibonacci"]);
});

run();
