// app.jsx — root of the Executable Tutorial Player.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#7ab8ff",
  "mono": "'JetBrains Mono'",
  "sans": "'Public Sans'",
  "typewriter": true,
  "fontScale": 100,
  "simulateFail": false
}/*EDITMODE-END*/;

function randWorkdir() {
  const s = Math.random().toString(36).slice(2, 8);
  return "/tmp/tutorial-test-" + s;
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  const [raw, setRaw] = React.useState(null); // {yaml, filename}
  const [spec, setSpec] = React.useState(null);
  const [stops, setStops] = React.useState([]);
  const [outline, setOutline] = React.useState([]);
  const [stats, setStats] = React.useState(null);
  const [error, setError] = React.useState(null);

  const [cur, setCur] = React.useState(0);
  const [replay, setReplay] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);
  const [speed, setSpeed] = React.useState(1);
  const [platform, setPlatform] = React.useState("linux");
  const [perStop, setPerStop] = React.useState({});
  const [showFull, setShowFull] = React.useState(false);
  const [workdir, setWorkdir] = React.useState(randWorkdir());

  const advanceRef = React.useRef(null);
  const release = (spec && spec.release) || "";

  // accent + fonts → CSS vars
  React.useEffect(() => {
    const r = document.documentElement;
    r.style.setProperty("--accent", t.accent);
    r.style.setProperty("--mono", t.mono + ", ui-monospace, monospace");
    r.style.setProperty("--sans", t.sans + ", system-ui, sans-serif");
    r.style.setProperty("--font-scale", (t.fontScale || 100) / 100);
  }, [t.accent, t.mono, t.sans, t.fontScale]);

  function loadYaml(yaml, filename) {
    try {
      const parsed = window.TutorialParser.parse(yaml);
      const st = window.TutorialParser.buildStops(parsed);
      const ol = window.TutorialParser.buildOutline(parsed, st);
      setSpec(parsed);
      setStops(st);
      setOutline(ol);
      setStats(window.TutorialParser.specStats(parsed));
      setRaw({ yaml, filename });
      setError(null);
      setCur(0);
      setReplay((r) => r + 1);
      setPerStop({});
      setPlaying(false);
      setWorkdir(randWorkdir());
    } catch (e) {
      setError(e.message || String(e));
    }
  }

  function reset() {
    if (advanceRef.current) clearTimeout(advanceRef.current);
    setRaw(null); setSpec(null); setStops([]); setOutline([]);
    setStats(null); setCur(0); setPlaying(false); setPerStop({});
  }

  const goTo = React.useCallback((i) => {
    if (advanceRef.current) clearTimeout(advanceRef.current);
    setCur((prev) => {
      const next = Math.max(0, Math.min(stops.length - 1, i));
      if (next === prev) return prev;
      return next;
    });
  }, [stops.length]);

  const next = React.useCallback(() => goTo(cur + 1), [cur, goTo]);
  const prev = React.useCallback(() => { setPlaying(false); goTo(cur - 1); }, [cur, goTo]);

  function restart() {
    if (advanceRef.current) clearTimeout(advanceRef.current);
    setPerStop({});
    setPlaying(false);
    if (cur === 0) setReplay((r) => r + 1);
    else setCur(0);
  }

  function onTermComplete(tally) {
    setPerStop((p) => ({ ...p, [cur]: tally }));
    if (playing) {
      if (cur < stops.length - 1) {
        advanceRef.current = setTimeout(() => setCur((c) => Math.min(stops.length - 1, c + 1)), 850 / speed);
      } else {
        setPlaying(false);
      }
    }
  }

  // keyboard
  React.useEffect(() => {
    function onKey(e) {
      if (!spec || showFull) return;
      if (e.target && /INPUT|TEXTAREA/.test(e.target.tagName)) return;
      if (e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); prev(); }
      else if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [spec, showFull, next, prev]);

  React.useEffect(() => () => { if (advanceRef.current) clearTimeout(advanceRef.current); }, []);

  if (!spec) {
    return (
      <React.Fragment>
        <Uploader onLoad={loadYaml} error={error} />
        <TweaksUI t={t} setTweak={setTweak} />
      </React.Fragment>
    );
  }

  const stop = stops[cur];
  const ops = window.TutorialParser.buildOps(stop, platform, release);
  const playKey = cur + "-" + replay + "-" + platform + "-" + (t.simulateFail ? "f" : "") + "-" + (t.typewriter ? "a" : "i");

  const totalPass = Object.values(perStop).reduce((a, b) => a + (b.pass || 0), 0);
  const totalFail = Object.values(perStop).reduce((a, b) => a + (b.fail || 0), 0);
  const totalSkip = Object.values(perStop).reduce((a, b) => a + (b.skip || 0), 0);

  return (
    <div className="app">
      <header className="topbar">
        <div className="tb-left">
          <span className="tb-logo">⌁</span>
          <span className="tb-name">tutorial_runner</span>
          <span className="tb-file">{raw.filename}</span>
        </div>
        <div className="tb-right">
          <div className="tb-tally" title="cumulative results across visited steps">
            <span className="tally-pass">✓ {totalPass}</span>
            {totalFail > 0 && <span className="tally-fail">✕ {totalFail}</span>}
            {totalSkip > 0 && <span className="tally-skip">⊘ {totalSkip}</span>}
          </div>
          <button className="tb-btn" onClick={() => setShowFull(true)}>⌁ Full markdown</button>
          <button className="tb-btn tb-btn-ghost" onClick={reset}>＋ New file</button>
        </div>
      </header>

      <div className="main">
        <Sidebar
          spec={spec}
          outline={outline}
          currentStop={cur}
          onJump={(i) => { setPlaying(false); goTo(i); }}
          stats={stats}
          perStop={perStop}
        />

        <div className="panes">
          <section className="reader">
            <div className="pane-head">
              <span className="pane-label">reader</span>
              <span className="pane-hint">what the tutorial shows</span>
            </div>
            <div className="reader-scroll">
              <ReaderPane key={cur} stop={stop} spec={spec} platform={platform} release={release} />
            </div>
          </section>

          <div className="pane-divider" />

          <section className="exec">
            <div className="pane-head exec-head">
              <span className="pane-label exec-label">execution</span>
              <span className="exec-meta">
                <span className="exec-wd">{workdir}</span>
                {t.simulateFail && <span className="exec-failflag">fail-sim</span>}
                <button className="exec-replay" onClick={() => setReplay((r) => r + 1)} title="Replay this step">⟲ replay</button>
              </span>
            </div>
            <ExecTerminal
              ops={ops}
              playKey={playKey}
              speed={speed}
              animate={t.typewriter}
              simulateFail={t.simulateFail}
              workdir={workdir}
              onComplete={onTermComplete}
            />
          </section>
        </div>
      </div>

      <Controls
        index={cur}
        total={stops.length}
        onPrev={prev}
        onNext={next}
        playing={playing}
        onTogglePlay={() => setPlaying((p) => !p)}
        speed={speed}
        onSpeed={setSpeed}
        platform={platform}
        onPlatform={(p) => { setPlatform(p); }}
        onRestart={restart}
        release={release}
      />

      {showFull && <FullMarkdown spec={spec} platform={platform} release={release} onClose={() => setShowFull(false)} />}

      <TweaksUI t={t} setTweak={setTweak} />
    </div>
  );
}

function TweaksUI({ t, setTweak }) {
  return (
    <TweaksPanel>
      <TweakSection label="Appearance" />
      <TweakColor label="Accent" value={t.accent}
        options={["#7ab8ff", "#56d364", "#e3b341", "#d2a8ff"]}
        onChange={(v) => setTweak("accent", v)} />
      <TweakSelect label="Terminal font" value={t.mono}
        options={["'JetBrains Mono'", "'IBM Plex Mono'", "'Fira Code'", "ui-monospace"]}
        onChange={(v) => setTweak("mono", v)} />
      <TweakSelect label="Prose font" value={t.sans}
        options={["'Public Sans'", "'Inter'", "system-ui"]}
        onChange={(v) => setTweak("sans", v)} />
      <TweakSlider label="Font size" value={t.fontScale} min={85} max={120} step={5} unit="%"
        onChange={(v) => setTweak("fontScale", v)} />
      <TweakSection label="Playback" />
      <TweakToggle label="Typewriter animation" value={t.typewriter}
        onChange={(v) => setTweak("typewriter", v)} />
      <TweakToggle label="Simulate failure on step" value={t.simulateFail}
        onChange={(v) => setTweak("simulateFail", v)} />
    </TweaksPanel>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
