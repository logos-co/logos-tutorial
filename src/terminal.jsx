// terminal.jsx — animated simulated execution terminal.
// Given a list of ops (from TutorialParser.buildOps) it "types" commands,
// shows a running spinner, then PASS/FAIL, plus file writes, assertions,
// check_file, and ui_test actions. Reports a {pass,fail,skip} tally on finish.

const SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

function ExecTerminal({ ops, playKey, speed, animate, simulateFail, workdir, onComplete }) {
  const linesRef = React.useRef([]);
  const [, force] = React.useReducer((x) => x + 1, 0);
  const cancelRef = React.useRef(false);
  const scrollRef = React.useRef(null);

  React.useEffect(() => {
    cancelRef.current = false;
    linesRef.current = [];
    force();
    runSequence();
    return () => {
      cancelRef.current = true;
    };
    // eslint-disable-next-line
  }, [playKey]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  });

  const spd = speed || 1;
  const baseChar = animate ? 13 / spd : 0;
  const baseStep = animate ? 280 / spd : 0;

  function push(line) {
    linesRef.current.push({ id: linesRef.current.length + "-" + Math.random().toString(36).slice(2, 6), ...line });
    force();
    return linesRef.current.length - 1;
  }
  function update(i, patch) {
    if (linesRef.current[i]) Object.assign(linesRef.current[i], patch);
    force();
  }

  function sleep(ms) {
    return new Promise((res, rej) => {
      if (!ms) return res();
      const t = setInterval(() => {
        if (cancelRef.current) {
          clearInterval(t);
          rej(new Error("cancelled"));
        }
      }, 40);
      setTimeout(() => {
        clearInterval(t);
        cancelRef.current ? rej(new Error("cancelled")) : res();
      }, ms);
    });
  }

  async function typeInto(i, full, field) {
    if (!animate) {
      update(i, { [field]: full });
      return;
    }
    const chars = [...full];
    let buf = "";
    const chunk = chars.length > 120 ? 4 : 2;
    for (let c = 0; c < chars.length; c += chunk) {
      if (cancelRef.current) throw new Error("cancelled");
      buf += chars.slice(c, c + chunk).join("");
      update(i, { [field]: buf });
      await sleep(baseChar);
    }
    update(i, { [field]: full });
  }

  async function spin(i, ms) {
    if (!animate) return;
    let f = 0;
    const start = Date.now();
    while (Date.now() - start < ms) {
      if (cancelRef.current) throw new Error("cancelled");
      update(i, { spinner: SPIN[f % SPIN.length] });
      f++;
      await sleep(70);
    }
  }

  async function runSequence() {
    const tally = { pass: 0, fail: 0, skip: 0 };
    try {
      if (!ops || ops.length === 0) {
        push({ type: "idle" });
        force();
        onComplete && onComplete({ pass: 0, fail: 0, skip: 0, empty: true });
        return;
      }

      let failed = false;
      let firstCmdSeen = false;

      for (const op of ops) {
        if (cancelRef.current) return;

        if (failed) {
          // runner stops on first failure → remaining actions skipped
          push({ type: "skip", text: describeOp(op) });
          tally.skip++;
          continue;
        }

        if (op.type === "file") {
          const i = push({ type: "file", path: op.path, language: op.language, binary: op.binary, content: "", revealed: false });
          await sleep(baseStep * 0.4);
          update(i, { revealed: true, content: op.binary ? "" : op.content });
          tally.pass++;
          await sleep(baseStep * 0.5);
        } else if (op.type === "cmd") {
          if (op.displayDiffers) {
            push({ type: "note", text: "docs display a multi-platform / annotated form — runner executes the line below" });
          }
          const pi = push({ type: "prompt", typed: "", extra: op.extra });
          await typeInto(pi, op.command, "typed");
          await sleep(baseStep * 0.25);
          const willFail = simulateFail && !firstCmdSeen;
          firstCmdSeen = true;
          const ri = push({ type: "run", status: "running", spinner: SPIN[0] });
          await spin(ri, baseStep * (op.command.length > 60 ? 1.6 : 1.1));
          if (willFail) {
            update(ri, { status: "fail", spinner: null, code: 1 });
            tally.fail++;
            failed = true;
            continue;
          }
          update(ri, { status: "pass", spinner: null, code: 0 });
          tally.pass++;
          // assertions
          if (op.asserts && op.asserts.length) {
            push({ type: "assert-head", count: op.asserts.length });
            for (const a of op.asserts) {
              if (cancelRef.current) return;
              const ai = push({ type: "assert", status: "running", text: a.text, spinner: SPIN[0] });
              await spin(ai, baseStep * 0.5);
              update(ai, { status: "pass", spinner: null });
              tally.pass++;
              await sleep(baseStep * 0.15);
            }
          }
          await sleep(baseStep * 0.4);
        } else if (op.type === "check") {
          const ci = push({ type: "check", status: "running", path: op.path, spinner: SPIN[0] });
          await spin(ci, baseStep * 0.6);
          update(ci, { status: "pass", spinner: null });
          tally.pass++;
          await sleep(baseStep * 0.3);
        } else if (op.type === "ui") {
          if (op.setup && op.setup.length) {
            for (const s of op.setup) {
              const si = push({ type: "prompt", typed: "", dim: true });
              await typeInto(si, s, "typed");
              const sri = push({ type: "run", status: "running", spinner: SPIN[0], small: true });
              await spin(sri, baseStep * 0.7);
              update(sri, { status: "pass", spinner: null, code: 0 });
              tally.pass++;
            }
          }
          if (op.launch) {
            push({ type: "note", text: "launch app (QT_QPA_PLATFORM=offscreen), connect QML inspector :" + op.port });
            const li = push({ type: "prompt", typed: "" });
            await typeInto(li, op.launch, "typed");
            const lri = push({ type: "run", status: "running", spinner: SPIN[0], label: "app running" });
            await spin(lri, baseStep * 1.1);
            update(lri, { status: "pass", spinner: null, label: "app up" });
            tally.pass++;
          }
          for (const t of op.tests || []) {
            if (cancelRef.current) return;
            const ti = push({ type: "ui-test", status: "running", label: uiLabel(t), name: t.name, spinner: SPIN[0] });
            await spin(ti, baseStep * 0.6);
            update(ti, { status: "pass", spinner: null });
            tally.pass++;
            await sleep(baseStep * 0.15);
          }
          if (op.launch) push({ type: "note", text: "kill app process" });
          await sleep(baseStep * 0.3);
        }
      }

      push({ type: "summary", pass: tally.pass, fail: tally.fail, skip: tally.skip });
      force();
      onComplete && onComplete(tally);
    } catch (e) {
      // cancelled — ignore
    }
  }

  return (
    <div className="term-scroll" ref={scrollRef}>
      <div className="term-body">
        {linesRef.current.map((l) => (
          <TermLine key={l.id} l={l} workdir={workdir} />
        ))}
      </div>
    </div>
  );
}

function describeOp(op) {
  if (op.type === "cmd") return op.command.split("\n")[0];
  if (op.type === "file") return "write " + op.path;
  if (op.type === "check") return "check " + op.path;
  if (op.type === "ui") return op.launch || "ui test";
  return "action";
}

function uiLabel(t) {
  switch (t.action) {
    case "click": return 'click "' + t.target + '"';
    case "wait_for": return "wait_for " + JSON.stringify(t.texts) + (t.timeout ? "  ↻" + t.timeout + "ms" : "");
    case "expect_texts": return "expect_texts " + JSON.stringify(t.texts);
    case "set_text": return "set_text " + t.find_by + "=" + JSON.stringify(t.find_value) + ' → "' + t.value + '"';
    case "sleep": return "sleep " + t.ms + "ms";
    default: return t.action;
  }
}

function TermLine({ l, workdir }) {
  if (l.type === "idle")
    return (
      <div className="t-idle">
        <span className="t-idle-dot" /> documentation only — no commands to execute for this step
      </div>
    );

  if (l.type === "note") return <div className="t-note"># {l.text}</div>;

  if (l.type === "skip")
    return (
      <div className="t-skip">
        <span className="t-mark t-mark-skip">⊘</span>
        <span className="t-skip-text">skipped — {l.text.split("\n")[0]}</span>
      </div>
    );

  if (l.type === "prompt")
    return (
      <div className={"t-prompt" + (l.dim ? " t-dim" : "") + (l.extra ? " t-extra" : "")}>
        <span className="t-dollar">{l.extra ? "↳" : "$"}</span>
        <pre className="t-cmd">{l.typed}</pre>
      </div>
    );

  if (l.type === "run") {
    const running = l.status === "running";
    return (
      <div className={"t-run t-run-" + l.status + (l.small ? " t-run-small" : "")}>
        {running ? (
          <span className="t-spin">{l.spinner}</span>
        ) : (
          <span className={"t-mark " + (l.status === "pass" ? "t-mark-pass" : "t-mark-fail")}>
            {l.status === "pass" ? "✓" : "✕"}
          </span>
        )}
        <span className="t-run-text">
          {running
            ? "running…"
            : l.status === "pass"
            ? l.label
              ? l.label
              : "exit 0 · pass"
            : "exit " + (l.code || 1) + " · FAILED"}
        </span>
      </div>
    );
  }

  if (l.type === "file")
    return (
      <div className="t-file">
        <div className="t-file-head">
          <span className="t-file-icon">›</span> write <span className="t-file-path">{l.path}</span>
          <span className="t-file-lang">{l.language}</span>
        </div>
        {l.revealed && (
          l.binary ? (
            <div className="t-file-binary">binary file (base64) — decoded to disk</div>
          ) : (
            <pre className="t-file-body">
              <code className={"language-" + (l.language || "text")}>{l.content}</code>
            </pre>
          )
        )}
      </div>
    );

  if (l.type === "assert-head") return <div className="t-asserthead">assert · output contains ({l.count})</div>;

  if (l.type === "assert") {
    const running = l.status === "running";
    return (
      <div className={"t-assert t-assert-" + l.status}>
        {running ? <span className="t-spin t-spin-sm">{l.spinner}</span> : <span className="t-mark t-mark-pass">✓</span>}
        <pre className="t-assert-text">{l.text}</pre>
      </div>
    );
  }

  if (l.type === "check") {
    const running = l.status === "running";
    return (
      <div className={"t-check t-check-" + l.status}>
        {running ? <span className="t-spin t-spin-sm">{l.spinner}</span> : <span className="t-mark t-mark-pass">✓</span>}
        <span className="t-check-text">file exists · <span className="t-file-path">{l.path}</span></span>
      </div>
    );
  }

  if (l.type === "ui-test") {
    const running = l.status === "running";
    return (
      <div className={"t-ui t-ui-" + l.status}>
        {running ? <span className="t-spin t-spin-sm">{l.spinner}</span> : <span className="t-mark t-mark-pass">✓</span>}
        <span className="t-ui-label">{l.label}</span>
        {l.name && <span className="t-ui-name">{l.name}</span>}
      </div>
    );
  }

  if (l.type === "summary")
    return (
      <div className="t-summary">
        <span className="t-sum-pass">{l.pass} passed</span>
        {l.fail > 0 && <span className="t-sum-fail">{l.fail} failed</span>}
        {l.skip > 0 && <span className="t-sum-skip">{l.skip} skipped</span>}
      </div>
    );

  return null;
}

Object.assign(window, { ExecTerminal });
