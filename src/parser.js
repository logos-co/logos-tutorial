// parser.js — turns a tutorial .test.yaml into navigable "stops",
// builds execution operation lists for the terminal, expands platform/release
// placeholders, and generates the full markdown document (mirrors the runner's
// generator behavior described in spec.md).
//
// Exposed on window.TutorialParser.

(function () {
  "use strict";

  // ── Placeholder expansion ─────────────────────────────────────────────
  const PLATFORMS = {
    linux: { ext: "so", shared_flags: "-shared -fPIC", label: "Linux" },
    macos: { ext: "dylib", shared_flags: "-dynamiclib", label: "macOS" },
  };

  function expandPlatform(str, platform) {
    if (str == null) return str;
    const p = PLATFORMS[platform] || PLATFORMS.linux;
    return String(str)
      .replaceAll("{ext}", p.ext)
      .replaceAll("{shared_flags}", p.shared_flags);
  }

  function expandRelease(str, release) {
    if (str == null) return str;
    const rel = release ? "/" + release : "";
    return String(str).replaceAll("{release}", rel);
  }

  // run / check_file / extra_run.run / file.content → expand BOTH platform + release
  function expandExec(str, platform, release) {
    return expandPlatform(expandRelease(str, release), platform);
  }
  // code_block / text / post_text → release only, NOT platform (verbatim platform)
  function expandDisplay(str, release) {
    return expandRelease(str, release);
  }

  // ── Parse ─────────────────────────────────────────────────────────────
  function parse(yamlText) {
    const spec = jsyaml.load(yamlText);
    if (!spec || typeof spec !== "object") {
      throw new Error("YAML did not parse into an object.");
    }
    if (!Array.isArray(spec.sections)) {
      throw new Error("Spec is missing a `sections:` list.");
    }
    return spec;
  }

  // ── Flatten into ordered stops ────────────────────────────────────────
  // A stop is one navigation unit. Either:
  //   { kind: 'intro' }                          — the title card
  //   { kind: 'section', section, stepNo }       — prose-only section
  //   { kind: 'step', section, stepNo, step, idx, first, last } — one step
  function buildStops(spec) {
    const stops = [];
    stops.push({ kind: "intro" });

    let stepCounter = 0;
    spec.sections.forEach((section, si) => {
      const isStep = !!section.step;
      const stepNo = isStep ? ++stepCounter : null;
      const steps = Array.isArray(section.steps) ? section.steps : [];

      if (steps.length > 0) {
        steps.forEach((step, idx) => {
          stops.push({
            kind: "step",
            section,
            sectionIndex: si,
            stepNo,
            step,
            idx,
            first: idx === 0,
            last: idx === steps.length - 1,
          });
        });
      } else {
        stops.push({ kind: "section", section, sectionIndex: si, stepNo });
      }
    });
    return stops;
  }

  // Group stops by section for the sidebar outline.
  function buildOutline(spec, stops) {
    const groups = [];
    let cur = null;
    stops.forEach((stop, i) => {
      if (stop.kind === "intro") {
        groups.push({ title: "Introduction", stepNo: null, items: [{ stopIndex: i, label: "Overview", kind: "intro" }] });
        return;
      }
      if (!cur || cur.sectionIndex !== stop.sectionIndex) {
        cur = {
          sectionIndex: stop.sectionIndex,
          title: stop.section.title,
          stepNo: stop.stepNo,
          items: [],
        };
        groups.push(cur);
      }
      let label;
      if (stop.kind === "section") label = "Read";
      else label = stepLabel(stop.step, stop.idx);
      cur.items.push({ stopIndex: i, label, kind: stop.kind });
    });
    return groups;
  }

  function stepLabel(step, idx) {
    if (step.title) return stripMd(step.title);
    if (step.run) return "Run command";
    if (step.file) return "Write " + (step.file.path || "file");
    if (step.ui_test) return "UI test";
    if (step.check_file) return "Check file";
    if (step.text) return "Note";
    return "Step " + (idx + 1);
  }

  function stripMd(s) {
    return String(s).replace(/[`*_]/g, "");
  }

  // ── Build execution operations for a step ─────────────────────────────
  // Returns an array of ops the terminal animates. Empty array → "docs only".
  function buildOps(stop, platform, release) {
    if (stop.kind !== "step") return [];
    const step = stop.step;
    const ops = [];

    // 1. file write
    if (step.file && step.file.path) {
      const f = step.file;
      ops.push({
        type: "file",
        path: f.path,
        language: f.language || guessLang(f.path),
        binary: f.encoding === "base64",
        content: f.encoding === "base64" ? null : expandExec(f.content || "", platform, release),
      });
    }

    // 2. run
    if (step.run) {
      const executed = expandExec(step.run, platform, release);
      const displayed = step.code_block != null ? expandDisplay(step.code_block, release) : executed;
      ops.push({
        type: "cmd",
        command: executed,
        displayDiffers: step.code_block != null && normalizeCmd(displayed) !== normalizeCmd(executed),
        displayed,
        asserts: buildAsserts(step, platform, release),
      });
    }

    // 3. check_file
    if (step.check_file) {
      ops.push({ type: "check", path: expandExec(step.check_file, platform, release) });
    }

    // 4. extra_run
    if (step.extra_run && step.extra_run.run) {
      const er = step.extra_run;
      const executed = expandExec(er.run, platform, release);
      const displayed = er.code_block != null ? expandDisplay(er.code_block, release) : executed;
      ops.push({
        type: "cmd",
        command: executed,
        extra: true,
        displayDiffers: er.code_block != null && normalizeCmd(displayed) !== normalizeCmd(executed),
        displayed,
        asserts: [],
      });
    }

    // 5. ui_test
    if (step.ui_test) {
      const ut = step.ui_test;
      ops.push({
        type: "ui",
        launch: ut.launch ? expandExec(ut.launch, platform, release) : null,
        build: ut.build || null,
        binary: ut.binary || null,
        setup: (ut.setup || []).map((s) => expandExec(s, platform, release)),
        qt_mcp: ut.qt_mcp || null,
        port: ut.inspector_port || 3768,
        tests: (ut.tests || []).map((t) => normalizeTest(t)),
      });
    }

    return ops;
  }

  function buildAsserts(step, platform, release) {
    const out = [];
    if (Array.isArray(step.expect_contains)) {
      step.expect_contains.forEach((s) =>
        out.push({ kind: "contains", text: expandExec(s, platform, release) })
      );
    }
    return out;
  }

  function normalizeTest(t) {
    return {
      action: t.action,
      name: t.name || null,
      target: t.target || null,
      texts: t.texts || null,
      timeout: t.timeout || null,
      find_by: t.find_by || null,
      find_value: t.find_value || null,
      value: t.value != null ? t.value : null,
      ms: t.ms != null ? t.ms : null,
    };
  }

  function normalizeCmd(s) {
    return String(s)
      .split("\n")
      .map((l) => l.replace(/\s+#.*$/, "").trim()) // drop trailing comments
      .filter((l) => l && !l.startsWith("#"))
      .join("\n")
      .trim();
  }

  function guessLang(path) {
    const ext = (path.split(".").pop() || "").toLowerCase();
    const map = {
      c: "c", h: "cpp", cpp: "cpp", cc: "cpp",
      json: "json", nix: "nix", qml: "qml",
      js: "javascript", mjs: "javascript", py: "python",
      sh: "bash", txt: "text", md: "markdown",
    };
    return map[ext] || "text";
  }

  // ── Reader-pane markdown for a single stop ────────────────────────────
  // Mirrors generator step order: title → text → file → run/code_block →
  // post_text → extra_run → ui_test.launch
  function stopMarkdown(stop, platform, release) {
    if (stop.kind === "intro") return null; // handled specially in UI
    const md = [];

    if (stop.kind === "section") {
      const s = stop.section;
      md.push(headingFor(s, stop.stepNo));
      if (s.text) md.push(expandDisplay(s.text, release));
      return md.join("\n\n");
    }

    // step
    const step = stop.step;
    if (step.title) md.push("### " + expandDisplay(step.title, release));
    if (step.text) md.push(expandDisplay(step.text, release));
    if (step.file && step.file.path) md.push(fileBlock(step.file, platform, release));
    if (step.run) md.push(runBlock(step, platform, release));
    if (step.post_text) md.push(expandDisplay(step.post_text, release));
    if (step.extra_run) md.push(extraRunBlock(step.extra_run, platform, release));
    if (step.ui_test && step.ui_test.launch)
      md.push("```bash\n" + expandExec(step.ui_test.launch, platform, release) + "\n```");
    if (step.check_file && !step.run) {
      // check_file alone has no reader markdown per spec (runner-only); skip.
    }
    return md.join("\n\n");
  }

  function headingFor(section, stepNo) {
    if (section.step && stepNo != null) return "## Step " + stepNo + ": " + section.title;
    return "## " + section.title;
  }

  function fileBlock(file, platform, release) {
    if (file.encoding === "base64") return "*Binary file: `" + file.path + "`*";
    const lang = file.language || guessLang(file.path);
    const content = expandExec(file.content || "", platform, release);
    return "```" + lang + "\n" + content + "\n```";
  }

  function runBlock(step, platform, release) {
    if (step.code_block != null) {
      return "```bash\n" + expandDisplay(step.code_block, release) + "\n```";
    }
    return "```bash\n" + expandExec(step.run, platform, release) + "\n```";
  }

  function extraRunBlock(er, platform, release) {
    const parts = [];
    if (er.code_block != null) parts.push("```bash\n" + expandDisplay(er.code_block, release) + "\n```");
    else if (er.run) parts.push("```bash\n" + expandExec(er.run, platform, release) + "\n```");
    if (er.post_text) parts.push(expandDisplay(er.post_text, release));
    return parts.join("\n\n");
  }

  // ── Full document generation (mirrors `generate`) ─────────────────────
  function generateMarkdown(spec, platform, release) {
    const out = [];
    out.push("# " + spec.name);
    if (spec.intro) out.push(expandDisplay(spec.intro, release).trim());
    if (spec.what_you_build) out.push("**What you'll build:** " + spec.what_you_build);
    if (Array.isArray(spec.what_you_learn) && spec.what_you_learn.length) {
      out.push("**What you'll learn:**\n\n" + spec.what_you_learn.map((x) => "- " + x).join("\n"));
    }
    if (spec.comparison) out.push(expandDisplay(spec.comparison, release).trim());
    if (Array.isArray(spec.prerequisites) && spec.prerequisites.length) {
      out.push("## Prerequisites\n\n" + spec.prerequisites.map((x) => "- " + String(x).trim()).join("\n\n"));
    }

    let stepCounter = 0;
    spec.sections.forEach((section, si) => {
      const isStep = !!section.step;
      const stepNo = isStep ? ++stepCounter : null;
      out.push(headingFor(section, stepNo));
      if (section.text) out.push(expandDisplay(section.text, release).trim());

      const steps = Array.isArray(section.steps) ? section.steps : [];
      steps.forEach((step) => {
        const m = [];
        if (step.title) m.push("### " + expandDisplay(step.title, release));
        if (step.text) m.push(expandDisplay(step.text, release).trim());
        if (step.file && step.file.path) m.push(fileBlock(step.file, platform, release));
        if (step.run) m.push(runBlock(step, platform, release));
        if (step.post_text) m.push(expandDisplay(step.post_text, release).trim());
        if (step.extra_run) m.push(extraRunBlock(step.extra_run, platform, release));
        if (step.ui_test && step.ui_test.launch)
          m.push("```bash\n" + expandExec(step.ui_test.launch, platform, release) + "\n```");
        if (m.length) out.push(m.join("\n\n"));
      });

      if (isStep && si < spec.sections.length - 1) out.push("---");
    });

    let doc = out.join("\n\n");
    doc = doc.replace(/\n{3,}/g, "\n\n"); // collapse triple+ blanks
    return doc;
  }

  // ── Stats about a spec ────────────────────────────────────────────────
  function specStats(spec) {
    let steps = 0, cmds = 0, files = 0, asserts = 0, uiTests = 0, checks = 0;
    spec.sections.forEach((sec) => {
      (sec.steps || []).forEach((st) => {
        steps++;
        if (st.run) cmds++;
        if (st.extra_run && st.extra_run.run) cmds++;
        if (st.file) files++;
        if (Array.isArray(st.expect_contains)) asserts += st.expect_contains.length;
        if (st.check_file) checks++;
        if (st.ui_test) {
          uiTests++;
          asserts += (st.ui_test.tests || []).length;
        }
      });
    });
    const stepSections = spec.sections.filter((s) => s.step).length;
    return { sections: spec.sections.length, stepSections, steps, cmds, files, asserts, uiTests, checks };
  }

  window.TutorialParser = {
    PLATFORMS,
    parse,
    buildStops,
    buildOutline,
    buildOps,
    stopMarkdown,
    generateMarkdown,
    specStats,
    stepLabel,
    expandExec,
    expandDisplay,
    guessLang,
  };
})();
