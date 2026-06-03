import { resolve } from "node:path";
import { writeFileSync } from "node:fs";
const qtMcpRoot = "/Users/iurimatias/Projects/Logos/logos-workspace/repos/logos-tutorial/outputs/logos-calc-ui/result-mcp";
const { test, run } = await import(resolve(qtMcpRoot, "test-framework/framework.mjs"));

test("Tutorial Part 2: Building a QML UI for Your Logos Module: Launch basecamp and use the calculator", async (app) => {
  await app.waitFor(
    async () => { await app.expectTexts(["Dashboard"]); },
    { timeout: 60000, interval: 500, description: "Basecamp shell loads" }
  );
  {
    const shot = await app.screenshot();
    if (shot && shot.image) {
      writeFileSync("/Users/iurimatias/Projects/Logos/logos-workspace/repos/logos-tutorial/outputs/images/basecamp-load.png", Buffer.from(shot.image, "base64"));
    } else {
      throw new Error("screenshot " + "basecamp-load.png" + ": no image returned");
    }
  }
  await app.click("calc_ui", { exact: true });
  await app.waitFor(
    async () => { await app.expectTexts(["Logos Calculator", "Add", "Multiply"]); },
    { timeout: 15000, interval: 500, description: "Calculator view renders" }
  );
  {
    const shot = await app.screenshot();
    if (shot && shot.image) {
      writeFileSync("/Users/iurimatias/Projects/Logos/logos-workspace/repos/logos-tutorial/outputs/images/basecamp-load-calculator.png", Buffer.from(shot.image, "base64"));
    } else {
      throw new Error("screenshot " + "basecamp-load-calculator.png" + ": no image returned");
    }
  }
  {
    const found = await app.inspector.send("findByProperty", { property: "placeholderText", value: "a" });
    if (!found.matches || found.matches.length === 0) throw new Error("set_text: element not found");
    await app.inspector.send("setProperty", { objectId: found.matches[0].id, property: "text", value: "3" });
  }
  {
    const found = await app.inspector.send("findByProperty", { property: "placeholderText", value: "b" });
    if (!found.matches || found.matches.length === 0) throw new Error("set_text: element not found");
    await app.inspector.send("setProperty", { objectId: found.matches[0].id, property: "text", value: "5" });
  }
  await app.click("Add", { exact: true });
  await app.waitFor(
    async () => { await app.expectTexts(["8"]); },
    { timeout: 10000, interval: 500, description: "calc_module returns 3 + 5 = 8" }
  );
  {
    const shot = await app.screenshot();
    if (shot && shot.image) {
      writeFileSync("/Users/iurimatias/Projects/Logos/logos-workspace/repos/logos-tutorial/outputs/images/basecamp-calc-installed.png", Buffer.from(shot.image, "base64"));
    } else {
      throw new Error("screenshot " + "basecamp-calc-installed.png" + ": no image returned");
    }
  }
});

run();
