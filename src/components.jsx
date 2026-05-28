// components.jsx — Markdown renderer, Sidebar, ReaderPane, Controls, FullMarkdown, Uploader.

// ── Markdown ────────────────────────────────────────────────────────────
function Markdown({ text, className }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    if (!ref.current) return;
    const html = window.marked ? window.marked.parse(text || "") : (text || "");
    ref.current.innerHTML = html;
    if (window.hljs) {
      ref.current.querySelectorAll("pre code").forEach((block) => {
        // hljs has no qml grammar — alias to javascript for sensible coloring
        block.className = block.className.replace("language-qml", "language-javascript");
        try { window.hljs.highlightElement(block); } catch (e) {}
      });
    }
  }, [text]);
  return <div ref={ref} className={"md " + (className || "")} />;
}

// ── Sidebar outline ─────────────────────────────────────────────────────
function Sidebar({ spec, outline, currentStop, onJump, stats, perStop }) {
  return (
    <aside className="sidebar">
      <div className="sb-head">
        <div className="sb-kicker">TUTORIAL</div>
        <div className="sb-title">{spec.name}</div>
        <div className="sb-stats">
          <span title="step sections">{stats.stepSections} steps</span>
          <span className="sb-dot">·</span>
          <span title="commands">{stats.cmds} cmds</span>
          <span className="sb-dot">·</span>
          <span title="files">{stats.files} files</span>
          <span className="sb-dot">·</span>
          <span title="assertions">{stats.asserts} checks</span>
        </div>
      </div>
      <nav className="sb-nav">
        {outline.map((g, gi) => (
          <div className="sb-group" key={gi}>
            <div className="sb-group-title">
              {g.stepNo != null && <span className="sb-stepno">{String(g.stepNo).padStart(2, "0")}</span>}
              <span className="sb-group-label">{g.title}</span>
            </div>
            <div className="sb-items">
              {g.items.map((it) => {
                const active = it.stopIndex === currentStop;
                const res = perStop[it.stopIndex];
                let mark = null;
                if (res) {
                  if (res.fail > 0) mark = <span className="sb-mark sb-mark-fail">✕</span>;
                  else if (res.empty) mark = <span className="sb-mark sb-mark-done">•</span>;
                  else mark = <span className="sb-mark sb-mark-pass">✓</span>;
                }
                return (
                  <button
                    key={it.stopIndex}
                    className={"sb-item" + (active ? " sb-item-active" : "")}
                    onClick={() => onJump(it.stopIndex)}
                  >
                    <span className="sb-item-dot" />
                    <span className="sb-item-label">{it.label}</span>
                    {mark}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}

// ── Reader pane (left) ──────────────────────────────────────────────────
function ReaderPane({ stop, spec, platform, release }) {
  if (stop.kind === "intro") {
    return (
      <div className="reader-inner intro-card">
        <div className="intro-kicker">EXECUTABLE TUTORIAL</div>
        <h1 className="intro-title">{spec.name}</h1>
        {spec.intro && <Markdown text={window.TutorialParser.expandDisplay(spec.intro, release)} className="intro-md" />}
        {spec.what_you_build && (
          <div className="intro-callout">
            <span className="intro-callout-k">What you'll build</span>
            <span className="intro-callout-v">{spec.what_you_build}</span>
          </div>
        )}
        {Array.isArray(spec.what_you_learn) && spec.what_you_learn.length > 0 && (
          <div className="intro-learn">
            <div className="intro-learn-h">What you'll learn</div>
            <ul>
              {spec.what_you_learn.map((x, i) => (
                <li key={i}><Markdown text={x} /></li>
              ))}
            </ul>
          </div>
        )}
        {Array.isArray(spec.prerequisites) && spec.prerequisites.length > 0 && (
          <div className="intro-prereq">
            <div className="intro-learn-h">Prerequisites</div>
            <ul>
              {spec.prerequisites.map((x, i) => (
                <li key={i}><Markdown text={String(x)} /></li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  const heading = stop.section.title;
  const md = window.TutorialParser.stopMarkdown(stop, platform, release);
  const showSectionLead = stop.kind === "step" && stop.first && stop.section.text;

  return (
    <div className="reader-inner">
      <div className="reader-crumb">
        {stop.stepNo != null && <span className="reader-stepno">STEP {stop.stepNo}</span>}
        <span className="reader-section">{heading}</span>
        {stop.kind === "step" && !stop.first && <span className="reader-cont">· continued</span>}
      </div>
      {showSectionLead && (
        <div className="reader-lead">
          <Markdown text={window.TutorialParser.expandDisplay(stop.section.text, release)} />
        </div>
      )}
      <Markdown text={md} />
    </div>
  );
}

// ── Bottom control bar ──────────────────────────────────────────────────
function Controls({
  index, total, onPrev, onNext, playing, onTogglePlay, speed, onSpeed,
  platform, onPlatform, onRestart, release,
}) {
  return (
    <div className="controls">
      <div className="ctrl-left">
        <button className="ctrl-btn" onClick={onRestart} title="Restart from beginning">⟲</button>
        <button className="ctrl-btn" onClick={onPrev} disabled={index === 0} title="Previous (←)">←</button>
        <button className={"ctrl-play" + (playing ? " is-playing" : "")} onClick={onTogglePlay} title="Play / pause (space)">
          {playing ? "❚❚" : "▶"}
        </button>
        <button className="ctrl-btn" onClick={onNext} disabled={index === total - 1} title="Next (→)">→</button>
      </div>

      <div className="ctrl-progress">
        <div className="ctrl-count">{String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}</div>
        <div className="ctrl-track">
          <div className="ctrl-fill" style={{ width: ((index + 1) / total) * 100 + "%" }} />
        </div>
      </div>

      <div className="ctrl-right">
        <div className="ctrl-seg" title="Target platform — expands {ext} & {shared_flags}">
          <button className={platform === "linux" ? "seg-on" : ""} onClick={() => onPlatform("linux")}>Linux</button>
          <button className={platform === "macos" ? "seg-on" : ""} onClick={() => onPlatform("macos")}>macOS</button>
        </div>
        <div className="ctrl-speed" title="Autoplay speed">
          {[0.5, 1, 2, 3].map((s) => (
            <button key={s} className={speed === s ? "spd-on" : ""} onClick={() => onSpeed(s)}>
              {s}×
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Full generated markdown overlay ─────────────────────────────────────
function FullMarkdown({ spec, platform, release, onClose }) {
  const md = window.TutorialParser.generateMarkdown(spec, platform, release);
  const [view, setView] = React.useState("rendered");
  return (
    <div className="fm-overlay">
      <div className="fm-bar">
        <div className="fm-title">
          <span className="fm-icon">⌁</span> Generated markdown
          <span className="fm-sub">{spec.output || "tutorial.md"}</span>
        </div>
        <div className="fm-actions">
          <div className="ctrl-seg">
            <button className={view === "rendered" ? "seg-on" : ""} onClick={() => setView("rendered")}>Rendered</button>
            <button className={view === "source" ? "seg-on" : ""} onClick={() => setView("source")}>Source</button>
          </div>
          <button className="fm-copy" onClick={() => navigator.clipboard && navigator.clipboard.writeText(md)}>Copy</button>
          <button className="fm-close" onClick={onClose}>✕</button>
        </div>
      </div>
      <div className="fm-body">
        <div className="fm-inner">
          {view === "rendered" ? <Markdown text={md} /> : <pre className="fm-source">{md}</pre>}
        </div>
      </div>
    </div>
  );
}

// ── Uploader / landing ──────────────────────────────────────────────────
function Uploader({ onLoad, error }) {
  const [drag, setDrag] = React.useState(false);
  const [showPaste, setShowPaste] = React.useState(false);
  const [paste, setPaste] = React.useState("");
  const fileRef = React.useRef(null);

  function handleFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => onLoad(e.target.result, file.name);
    reader.readAsText(file);
  }

  return (
    <div className="landing">
      <div className="landing-grid" />
      <div className="landing-inner">
        <div className="landing-badge">▸ tutorial_runner · player</div>
        <h1 className="landing-title">Executable Tutorial Player</h1>
        <p className="landing-sub">
          Drop a <code>.test.yaml</code> spec and step through it — reading the rendered tutorial on the left
          while watching every command, file write, and assertion execute on the right.
        </p>

        <div
          className={"dropzone" + (drag ? " dz-drag" : "")}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
          }}
          onClick={() => fileRef.current && fileRef.current.click()}
        >
          <div className="dz-icon">⤓</div>
          <div className="dz-main">Drop your <b>.test.yaml</b> here</div>
          <div className="dz-or">or click to browse · <button className="dz-paste" onClick={(e) => { e.stopPropagation(); setShowPaste((s) => !s); }}>paste YAML</button></div>
          <input
            ref={fileRef}
            type="file"
            accept=".yaml,.yml,.txt"
            style={{ display: "none" }}
            onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
          />
        </div>

        {showPaste && (
          <div className="paste-box">
            <textarea
              value={paste}
              onChange={(e) => setPaste(e.target.value)}
              placeholder="name: &quot;My Tutorial&quot;&#10;sections:&#10;  - title: …"
              spellCheck={false}
            />
            <button className="paste-go" onClick={() => paste.trim() && onLoad(paste, "pasted.test.yaml")}>
              Load pasted YAML →
            </button>
          </div>
        )}

        {error && <div className="landing-error">⚠ {error}</div>}

        <div className="examples">
          <div className="examples-h">Or load an example</div>
          <div className="examples-row">
            {Object.entries(window.EXAMPLES).map(([key, ex]) => (
              <button key={key} className="example-card" onClick={() => onLoad(ex.yaml, ex.filename)}>
                <div className="ex-name">{ex.filename}</div>
                <ExampleMeta yaml={ex.yaml} />
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function ExampleMeta({ yaml }) {
  let title = "", stats = null;
  try {
    const spec = window.TutorialParser.parse(yaml);
    title = spec.name;
    stats = window.TutorialParser.specStats(spec);
  } catch (e) {}
  return (
    <div className="ex-meta">
      <div className="ex-title">{title}</div>
      {stats && (
        <div className="ex-stats">
          {stats.stepSections} steps · {stats.cmds} cmds · {stats.files} files · {stats.asserts} checks
        </div>
      )}
    </div>
  );
}

Object.assign(window, { Markdown, Sidebar, ReaderPane, Controls, FullMarkdown, Uploader });
