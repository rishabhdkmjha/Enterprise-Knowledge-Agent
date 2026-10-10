import { useEffect, useRef, useState } from "react";

async function api(path, opts) {
  const r = await fetch(`/api${path}`, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || r.statusText);
  return body;
}

export default function App() {
  const [sources, setSources] = useState([]);
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef(null);

  const loadSources = () => api("/sources").then(setSources).catch(() => {});
  useEffect(() => { loadSources(); }, []);
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function upload(e) {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    try { await api("/ingest", { method: "POST", body: fd }); await loadSources(); }
    catch (err) { alert(err.message); }
    e.target.value = "";
  }

  async function send() {
    const question = q.trim();
    if (!question || busy) return;
    setQ(""); setBusy(true);
    setMsgs((m) => [...m, { role: "user", text: question }]);
    try {
      const r = await api("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      setMsgs((m) => [...m, { role: "assistant", ...r }]);
    } catch (err) {
      setMsgs((m) => [...m, { role: "assistant", text: `Error: ${err.message}`, error: true }]);
    }
    setBusy(false);
  }

  return (
    <div className="app">
      <aside>
        <h2>Knowledge sources</h2>
        <ul>{sources.map((s) => <li key={s.name}>{s.name} <span>{s.chunks} chunks</span></li>)}</ul>
        <label className="upload">+ Upload PDF / TXT / MD
          <input type="file" accept=".pdf,.txt,.md" onChange={upload} hidden />
        </label>
        <p className="hint">Also connected: business database (read-only SQL via MCP).</p>
      </aside>
      <main>
        <div className="chat">
          {msgs.length === 0 && <p className="hint">Try: "How many annual leave days do employees get?" or "How many leave days has Vikram Singh taken?"</p>}
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              <p>{m.text ?? m.answer}</p>
              {m.role === "assistant" && !m.error && (
                <>
                  <span className={`badge ${m.grounded ? "ok" : "warn"}`}>
                    {m.grounded ? "verified" : "low confidence"}
                  </span>
                  {m.citations?.length > 0 && (
                    <details><summary>{m.citations.length} citation(s)</summary>
                      {m.citations.map((c) => (
                        <blockquote key={c.id}>
                          <b>[{c.id}] {c.source}{c.page ? ` p.${c.page}` : ""}</b><br />{c.snippet}
                        </blockquote>
                      ))}
                    </details>
                  )}
                  <details><summary>agent trace</summary><pre>{m.trace?.join("\n")}</pre></details>
                </>
              )}
            </div>
          ))}
          {busy && <div className="msg assistant"><p>Thinking…</p></div>}
          <div ref={bottom} />
        </div>
        <div className="input">
          <input value={q} onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()} placeholder="Ask a question…" />
          <button onClick={send} disabled={busy}>Ask</button>
        </div>
      </main>
    </div>
  );
}
