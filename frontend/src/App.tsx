import { useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, Boxes, BrainCircuit, Bug, ChevronRight, CircleCheck,
  CircleX, Container, FileWarning, GitBranch, GitCommitHorizontal, ListChecks,
  Menu, PlayCircle, RotateCcw, Search, Settings, Shield, SlidersHorizontal,
  Terminal, X, MessageCircle, Send,
} from "lucide-react";

type Json = Record<string, any>;
type PageKey = "overview" | "security-tests" | "changes" | "regression" | "mutation" | "failures" | "policy" | "cicd" | "chat" | "runtime" | "settings";

const nav: Array<{ key: PageKey; label: string; icon: typeof Shield }> = [
  { key: "overview", label: "Overview", icon: Activity },
  { key: "security-tests", label: "Security Tests", icon: Shield },
  { key: "changes", label: "Changes", icon: GitBranch },
  { key: "regression", label: "Regression", icon: SlidersHorizontal },
  { key: "mutation", label: "Mutation Testing", icon: Bug },
  { key: "failures", label: "Failures & Replay", icon: RotateCcw },
  { key: "policy", label: "Policy", icon: ListChecks },
  { key: "cicd", label: "CI/CD", icon: PlayCircle },
  { key: "chat", label: "Agent Chat", icon: MessageCircle },
  { key: "runtime", label: "Runtime", icon: Container },
  { key: "settings", label: "Settings", icon: Settings },
];

async function getJson(path: string): Promise<Json> {
  const response = await fetch(path);
  const text = await response.text();
  let body: Json = {};
  try { body = text ? JSON.parse(text) : {}; } catch { throw new Error(`Dashboard API returned invalid data (HTTP ${response.status})`); }
  if (!response.ok) throw new Error(body.detail || `Request failed: ${response.status}`);
  return body;
}

function pageFromLocation(): PageKey {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return (nav.some((item) => item.key === hash) ? hash : "overview") as PageKey;
}

function statusClass(value: unknown): string {
  const normalized = String(value ?? "unknown").toLowerCase().replace(/_/g, "-");
  return `status status-${normalized}`;
}

function Status({ value }: { value: unknown }) {
  return <span className={statusClass(value)}><span className="status-dot" />{String(value ?? "Unavailable")}</span>;
}

function Empty({ text = "Data unavailable" }: { text?: string }) {
  return <div className="empty"><AlertTriangle size={17} aria-hidden="true" /><span>{text}</span></div>;
}

function Metric({ label, value, detail, tone = "neutral" }: { label: string; value: unknown; detail?: string; tone?: string }) {
  return <div className={`metric metric-${tone}`}><div className="metric-label">{label}</div><div className="metric-value">{String(value ?? "—")}</div>{detail && <div className="metric-detail">{detail}</div>}</div>;
}

function App() {
  const [page, setPage] = useState<PageKey>(pageFromLocation());
  const [overview, setOverview] = useState<Json | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  useEffect(() => {
    const onHashChange = () => setPage(pageFromLocation());
    window.addEventListener("hashchange", onHashChange);
    getJson("/api/dashboard/overview").then(setOverview).catch((error: Error) => setOverviewError(error.message));
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const policy = overview?.policy?.report?.decision;
  const commit = overview?.security?.target?.commit;
  const runtime = overview?.runtime;

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Shield size={18} /></div><div><strong>TraceGuard</strong><span>Security control plane</span></div></div>
      <div className="nav-label">Workspace</div>
      <nav aria-label="Primary navigation">{nav.map(({ key, label, icon: Icon }) => <a key={key} href={`#/${key}`} className={page === key ? "nav-item active" : "nav-item"}><Icon size={16} /><span>{label}</span>{page === key && <ChevronRight size={14} className="nav-current" />}</a>)}</nav>
      <div className="sidebar-foot"><span className="online-dot" />Local environment</div>
    </aside>
    <main className="main-content">
      <header className="topbar"><div className="topbar-title"><Menu size={18} className="mobile-menu" /><span>Project</span><strong>TraceGuard</strong></div><div className="topbar-meta"><span className="branch"><GitBranch size={14} />main</span><span className="commit"><GitCommitHorizontal size={14} />{commit ? String(commit).slice(0, 9) : "commit unavailable"}</span><Status value={policy || "UNAVAILABLE"} /></div></header>
      <div className="page-wrap">
        {overviewError && <div className="error-banner"><CircleX size={17} />{overviewError}</div>}
        {page === "overview" && <Overview data={overview} />}
        {page === "security-tests" && <SecurityTests />}
        {page === "changes" && <Changes />}
        {page === "regression" && <Regression />}
        {page === "mutation" && <Mutation />}
        {page === "failures" && <Failures />}
        {page === "policy" && <Policy />}
        {page === "cicd" && <Cicd />}
        {page === "chat" && <AgentChat />}
        {page === "runtime" && <Runtime runtime={runtime} />}
        {page === "settings" && <SettingsPage />}
      </div>
    </main>
  </div>;
}

function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

function Section({ title, icon: Icon, children, className = "" }: { title: string; icon?: typeof Shield; children: React.ReactNode; className?: string }) {
  return <section className={`section ${className}`}><div className="section-header"><div className="section-title">{Icon && <Icon size={16} />}{title}</div></div>{children}</section>;
}

function Overview({ data }: { data: Json | null }) {
  if (!data) return <><PageHeader eyebrow="Security operations" title="Overview" description="Loading the latest TraceGuard evidence." /><Empty text="Loading dashboard data…" /></>;
  const security = data.security;
  const overall = security?.overall || {};
  const policy = data.policy?.report || {};
  const regression = data.regression?.report?.regression;
  const changes = data.changes?.report?.selection;
  const categories = security?.categories || {};
  return <>
    <PageHeader eyebrow="Security operations" title="Security status" description="Evidence-backed view of the latest application scan, change analysis, and policy gate." action={<button className="icon-button" title="Refresh dashboard" onClick={() => window.location.reload()}><RotateCcw size={16} /></button>} />
    <div className="metric-grid"><Metric label="Policy decision" value={policy.decision || "Unavailable"} tone={policy.decision?.toLowerCase()} detail={policy.triggered_rules?.join(", ") || "No policy evidence"} /><Metric label="Security score" value={overall.score != null ? `${overall.score}%` : "Unavailable"} detail={`${overall.passed ?? "—"} passed / ${overall.total ?? "—"} total`} /><Metric label="Regression" value={regression?.status || "Unavailable"} detail={regression ? `Delta ${regression.overall?.delta ?? "—"}` : "Baseline comparison unavailable"} /><Metric label="Change mode" value={changes?.mode || "Unavailable"} detail={changes?.reason || "No change-impact report"} /></div>
    <div className="content-grid"><Section title="Security summary" icon={Shield}><CategoryTable categories={categories} /></Section><Section title="Policy evidence" icon={ListChecks}><PolicyEvidence policy={policy} /></Section></div>
    <div className="content-grid"><Section title="Latest change" icon={GitBranch}><ChangeSummary data={data.changes} /></Section><Section title="Runtime" icon={Activity}><RuntimeSummary runtime={data.runtime} /></Section></div>
  </>;
}

function CategoryTable({ categories }: { categories: Json }) {
  const labels: Record<string, string> = { prompt_injection: "Prompt Injection", rag_injection: "RAG Injection", data_leakage: "Data Leakage", tool_abuse: "Tool Abuse" };
  if (!Object.keys(categories).length) return <Empty text="Security category data unavailable" />;
  return <div className="table-wrap"><table><thead><tr><th>Category</th><th>Tests</th><th>Passed</th><th>Failed</th><th>Score</th></tr></thead><tbody>{Object.entries(categories).map(([key, value]) => <tr key={key}><td><strong>{labels[key] || key}</strong></td><td>{value.total ?? "—"}</td><td className="text-success">{value.passed ?? "—"}</td><td className={value.failed ? "text-danger" : ""}>{value.failed ?? "—"}</td><td><strong>{value.score != null ? `${value.score}%` : "—"}</strong></td></tr>)}</tbody></table></div>;
}

function PolicyEvidence({ policy }: { policy: Json }) {
  if (!Object.keys(policy).length) return <Empty text="Policy result unavailable" />;
  return <div className="evidence"><div className="evidence-decision"><Status value={policy.decision} /><span>Exit code {policy.decision === "ALLOW" ? 0 : policy.decision === "BLOCK" ? 10 : 20}</span></div><p>{policy.summary || "No policy summary available."}</p><div className="evidence-list">{(policy.triggered_rules || []).map((rule: string) => <div key={rule}><FileWarning size={14} />{rule}</div>)}{!(policy.triggered_rules || []).length && <div>No triggered rules recorded.</div>}</div></div>;
}

function ChangeSummary({ data }: { data: Json }) {
  if (!data?.available) return <Empty text={data?.reason || "Change-impact report unavailable"} />;
  const report = data.report || {}; const selection = report.selection || {};
  return <div className="summary-list"><div><span>Mode</span><Status value={selection.mode || "NONE"} /></div><div><span>Base</span><code>{report.base || "—"}</code></div><div><span>Current</span><code>{report.current || "—"}</code></div><div><span>Categories</span><strong>{(selection.tests || []).join(", ") || "None"}</strong></div></div>;
}

function RuntimeSummary({ runtime }: { runtime: Json }) { if (!runtime) return <Empty />; return <div className="runtime-list">{["application", "ollama", "rag", "chromadb", "docker"].map((key) => <div key={key}><span>{key === "chromadb" ? "ChromaDB" : key[0].toUpperCase() + key.slice(1)}</span><Status value={runtime[key]?.status} /></div>)}</div>; }

function DataPage({ title, description, endpoint, children }: { title: string; description: string; endpoint: string; children: (data: Json | null, error: string | null) => React.ReactNode }) {
  const [data, setData] = useState<Json | null>(null); const [error, setError] = useState<string | null>(null);
  useEffect(() => { getJson(endpoint).then(setData).catch((e: Error) => setError(e.message)); }, [endpoint]);
  return <><PageHeader eyebrow="TraceGuard evidence" title={title} description={description} />{error ? <div className="error-banner"><CircleX size={17} />{error}</div> : children(data, null)}</>;
}

function SecurityTests() { return <DataPage title="Security tests" description="Inspect the deterministic test population and its evidence." endpoint="/api/security/tests">{(data) => { const [selected, setSelected] = useState<Json | null>(null); if (!data) return <Empty text="Loading security results…" />; if (!data.available) return <Empty text={data.reason} />; return <Section title={`${data.total} recorded tests`} icon={Shield}><div className="table-wrap"><table><thead><tr><th>ID</th><th>Category</th><th>Severity</th><th>Status</th><th>Score</th><th>Evidence</th></tr></thead><tbody>{data.results.map((item: Json) => <tr key={item.test_id} className="clickable" onClick={() => setSelected(item)}><td><code>{item.test_id}</code></td><td>{item.category}</td><td>{item.severity}</td><td><Status value={item.status} /></td><td>{item.score}%</td><td className="truncate">{item.evidence}</td></tr>)}</tbody></table></div>{selected && <Detail title={`${selected.test_id} evidence`} onClose={() => setSelected(null)}><dl className="detail-grid"><dt>Request</dt><dd>{selected.request}</dd><dt>Response</dt><dd>{selected.response}</dd><dt>Evidence</dt><dd>{selected.evidence}</dd><dt>Metadata</dt><dd><pre>{JSON.stringify(selected.metadata, null, 2)}</pre></dd></dl></Detail>}</Section>; }}</DataPage>; }

function Changes() { return <DataPage title="Change analysis" description="Trace changed files to affected security categories and selection mode." endpoint="/api/changes">{(data) => !data ? <Empty text="Loading change analysis…" /> : !data.available ? <Empty text={data.reason} /> : <Section title={`Selection: ${data.selection?.mode || "NONE"}`} icon={GitBranch}><p className="section-note">{data.reason || data.selection?.reason}</p><div className="table-wrap"><table><thead><tr><th>File</th><th>Component</th><th>Impact</th><th>Categories</th><th>Change</th></tr></thead><tbody>{(data.changes || []).map((item: Json, index: number) => <tr key={`${item.path}-${index}`}><td><code>{item.path}</code></td><td>{item.component}</td><td>{item.impact}</td><td>{(item.security_impact || item.security_impacts || item.impacts || []).join(", ") || "—"}</td><td>{item.change_type || item.status || "—"}</td></tr>)}</tbody></table></div></Section>}</DataPage>; }

function Regression() { return <DataPage title="Regression" description="Compare the current scan with its reviewed baseline." endpoint="/api/regression">{(data) => { const r = data?.regression; if (!data) return <Empty text="Loading regression report…" />; if (!data.available) return <Empty text={data.reason} />; return <><div className="metric-grid"><Metric label="Overall state" value={r?.status} tone={r?.status?.toLowerCase()} /><Metric label="Baseline score" value={r?.overall?.baseline_score != null ? `${r.overall.baseline_score}%` : "—"} /><Metric label="Current score" value={r?.overall?.current_score != null ? `${r.overall.current_score}%` : "—"} /><Metric label="Delta" value={r?.overall?.delta != null ? `${r.overall.delta}` : "—"} /></div><div className="content-grid"><Section title="Category comparison" icon={SlidersHorizontal}><ComparisonTable categories={r?.categories || {}} /></Section><Section title="Test changes" icon={ListChecks}><TestChanges changes={r?.test_changes || {}} /></Section></div></>; }}</DataPage>; }

function ComparisonTable({ categories }: { categories: Json }) { return <div className="table-wrap"><table><thead><tr><th>Category</th><th>Baseline</th><th>Current</th><th>Delta</th><th>Direction</th></tr></thead><tbody>{Object.entries(categories).map(([key, value]) => <tr key={key}><td>{key}</td><td>{value.baseline_score}%</td><td>{value.current_score}%</td><td>{value.delta}</td><td><Status value={value.direction} /></td></tr>)}</tbody></table></div>; }
function TestChanges({ changes }: { changes: Json }) { return <div className="summary-list"><div><span>Newly failed</span><strong>{(changes.newly_failed_tests || []).join(", ") || "None"}</strong></div><div><span>Recovered</span><strong>{(changes.recovered_tests || []).join(", ") || "None"}</strong></div><div><span>Persistent failures</span><strong className="text-danger">{(changes.persistent_failed_tests || []).join(", ") || "None"}</strong></div></div>; }

function Mutation() { return <DataPage title="Mutation testing" description="Measure whether the security suite detects controlled weaknesses." endpoint="/api/mutations">{(data) => { if (!data) return <Empty text="Loading mutation report…" />; if (!data.available) return <Empty text={data.reason} />; return <><div className="metric-grid"><Metric label="Detection rate" value={`${data.mutation_detection_rate ?? "—"}%`} /><Metric label="Injected" value={data.injected_mutations} /><Metric label="Detected" value={data.detected_mutations} tone="success" /><Metric label="Survived" value={data.survived_mutations} tone={data.survived_mutations ? "danger" : "success"} /></div><Section title="Mutation evidence" icon={Bug}><div className="table-wrap"><table><thead><tr><th>ID</th><th>Category</th><th>Target</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{(data.mutations || []).map((item: Json) => <tr key={item.mutation_id}><td><code>{item.mutation_id}</code></td><td>{item.category}</td><td><code>{item.metadata?.target_file || "—"}</code></td><td><Status value={item.status} /></td><td>{item.evidence}</td></tr>)}</tbody></table></div></Section></>; }}</DataPage>; }

function Failures() { return <DataPage title="Failures & replay" description="Review sanitized failure bundles and replay outcomes." endpoint="/api/failures">{(data) => { const [selected, setSelected] = useState<Json | null>(null); if (!data) return <Empty text="Loading failure bundles…" />; if (!data.available) return <Empty text={data.reason} />; return <Section title={`${data.total} failure bundles`} icon={RotateCcw}><div className="table-wrap"><table><thead><tr><th>Bundle</th><th>Test</th><th>Category</th><th>Status</th><th>Created</th></tr></thead><tbody>{(data.bundles || []).map((item: Json) => <tr key={item.bundle_id} className="clickable" onClick={() => getJson(`/api/failures/${item.bundle_id}`).then(setSelected)}><td><code>{item.bundle_id}</code></td><td>{item.test_id}</td><td>{item.category}</td><td><Status value={item.original_status} /></td><td>{item.created_at}</td></tr>)}</tbody></table></div>{selected && <Detail title={selected.bundle?.bundle_id || "Failure bundle"} onClose={() => setSelected(null)}><dl className="detail-grid"><dt>Request</dt><dd>{selected.bundle?.request}</dd><dt>Evidence</dt><dd>{selected.bundle?.evidence}</dd><dt>Replay</dt><dd><Status value={selected.replay?.replay_outcome || "Unavailable"} /></dd><dt>Metadata</dt><dd><pre>{JSON.stringify(selected.bundle?.test_metadata, null, 2)}</pre></dd></dl></Detail>}</Section>; }}</DataPage>; }

function Policy() { return <DataPage title="Policy gate" description="The backend policy engine remains authoritative for every decision." endpoint="/api/policy">{(data) => { if (!data) return <Empty text="Loading policy data…" />; const result = data.result?.report; return <><Section title="Latest decision" icon={ListChecks}><PolicyEvidence policy={result || {}} /></Section><Section title="Active policy configuration" icon={Settings}><pre className="code-block">{JSON.stringify(data.configuration, null, 2)}</pre></Section></>; }}</DataPage>; }
function Cicd() {
  const [data, setData] = useState<Json | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const load = () => getJson("/api/cicd").then(value => { if (active) { setData(value); setError(null); } }).catch((e: Error) => { if (active) setError(e.message); });
    load();
    const timer = window.setInterval(load, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const build = data?.build || {};
  const commits = data?.git_history?.commits || [];
  return <><PageHeader eyebrow="TraceGuard evidence" title="CI/CD" description="Live Jenkins status, gated Docker deployment state, and repository commit history. Refreshes every five seconds." />
    {error && <div className="error-banner"><CircleX size={17} />{error}</div>}
    <div className="metric-grid"><Metric label="Jenkins build" value={data?.available ? (build.displayName || build.number || "Available") : "Unavailable"} tone={data?.available ? (build.result || (build.building ? "running" : "success")).toLowerCase() : "unavailable"} detail={data?.available ? (build.building ? "Build in progress" : build.result || "Result pending") : data?.reason} /><Metric label="Build state" value={data?.available ? (build.building ? "RUNNING" : build.result || "UNKNOWN") : "UNAVAILABLE"} /><Metric label="Policy gate" value={data?.policy?.report?.decision || "Unavailable"} tone={data?.policy?.report?.decision?.toLowerCase()} detail="Local evidence report" /><Metric label="Commits" value={data?.git_history?.available ? commits.length : "Unavailable"} detail="Latest repository history" /></div>
    <div className="content-grid"><Section title="Jenkins status" icon={PlayCircle}>{data?.available ? <div className="summary-list"><div><span>Job</span><strong>{data.job}</strong></div><div><span>Build</span><strong>{build.displayName || `#${build.number}`}</strong></div><div><span>Result</span><Status value={build.building ? "RUNNING" : build.result || "UNKNOWN"} /></div><div><span>Jenkins endpoint</span><code>{data.url}</code></div><div><span>Build URL</span><a href={build.url} target="_blank" rel="noreferrer">{build.url || "Unavailable"}</a></div></div> : <Empty text={data?.reason || "Live Jenkins data unavailable"} />}</Section><Section title="Recent Git commits" icon={GitCommitHorizontal}>{data?.git_history?.available ? <div className="table-wrap"><table><thead><tr><th>Commit</th><th>Message</th><th>Author</th><th>Timestamp</th></tr></thead><tbody>{commits.map((commit: Json) => <tr key={commit.sha}><td><code>{commit.short_sha}</code></td><td>{commit.message}</td><td>{commit.author}</td><td>{commit.timestamp}</td></tr>)}</tbody></table></div> : <Empty text={data?.git_history?.reason || "Git history unavailable"} />}</Section></div>
  </>;
}

type ChatMessage = { role: "user" | "agent"; content: string; metadata?: Json };
function AgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || sending) return;
    setMessages(previous => [...previous, { role: "user", content: message }]);
    setInput(""); setSending(true); setError(null);
    try {
      const response = await fetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message }) });
      const text = await response.text();
      let body: Json = {}; try { body = text ? JSON.parse(text) : {}; } catch { throw new Error(`Agent returned invalid data (HTTP ${response.status})`); }
      if (!response.ok) throw new Error(body.detail || `Agent request failed: ${response.status}`);
      setMessages(previous => [...previous, { role: "agent", content: body.response, metadata: body.metadata }]);
    } catch (reason) { const detail = reason instanceof Error ? reason.message : "Agent request failed"; setError(detail); setMessages(previous => [...previous, { role: "agent", content: detail }]); }
    finally { setSending(false); }
  }
  return <><PageHeader eyebrow="TraceGuard agent" title="Agent chat" description="Talk to the configured customer-support agent through the real /chat endpoint. Responses are subject to the same security controls as CI scans." />
    {error && <div className="error-banner"><CircleX size={17} />{error}</div>}
    <Section title="Conversation" icon={MessageCircle}><div className="chat-shell"><div className="chat-log">{messages.length === 0 ? <Empty text="Ask the configured agent a question to begin." /> : messages.map((message, index) => <div className={`chat-message chat-${message.role}`} key={`${message.role}-${index}`}><div className="chat-role">{message.role === "user" ? "You" : "TraceGuard agent"}</div><div className="chat-content">{message.content}</div>{message.metadata && <div className="chat-metadata">Tool: {message.metadata.selected_tool || "none"} · Sources: {(message.metadata.retrieved_documents || []).join(", ") || "none"}</div>}</div>)}</div><form className="chat-composer" onSubmit={submit}><input aria-label="Message the agent" value={input} onChange={event => setInput(event.target.value)} placeholder="Ask the TraceGuard agent…" disabled={sending} /><button type="submit" disabled={sending || !input.trim()}><Send size={15} />{sending ? "Sending…" : "Send"}</button></form></div></Section>
  </>;
}
function Runtime({ runtime: initial }: { runtime: Json }) { return <DataPage title="Runtime" description="Current application, model, RAG, and container availability." endpoint="/api/runtime">{(data) => { const runtime = data || initial; if (!runtime) return <Empty text="Loading runtime status…" />; return <Section title="Runtime dependencies" icon={Activity}><div className="runtime-grid">{["application", "fastapi", "ollama", "rag", "chromadb", "docker", "container"].map((key) => <div className="runtime-item" key={key}><div><strong>{key === "chromadb" ? "ChromaDB" : key[0].toUpperCase() + key.slice(1)}</strong><small>{runtime[key]?.detail || "Live status"}</small></div><Status value={runtime[key]?.status} /></div>)}</div></Section>; }}</DataPage>; }
function SettingsPage() { return <DataPage title="Settings" description="Safe configuration visibility with secret values excluded." endpoint="/api/settings">{(data) => !data ? <Empty text="Loading settings…" /> : <div className="content-grid"><Section title="Application" icon={Settings}><dl className="detail-grid"><dt>Name</dt><dd>{data.application?.name}</dd><dt>Host</dt><dd><code>{data.application?.host}</code></dd><dt>Port</dt><dd><code>{data.application?.port}</code></dd><dt>Environment</dt><dd>{data.environment}</dd></dl></Section><Section title="Model runtime" icon={BrainCircuit}><dl className="detail-grid"><dt>Provider</dt><dd>{data.model?.provider}</dd><dt>Chat model</dt><dd><code>{data.model?.chat_model}</code></dd><dt>Embedding model</dt><dd><code>{data.model?.embedding_model}</code></dd><dt>Ollama endpoint</dt><dd><code>{data.model?.ollama_endpoint}</code></dd></dl></Section></div>}</DataPage>; }

function Detail({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="detail-overlay" role="dialog" aria-modal="true" aria-label={title}><div className="detail-panel"><div className="detail-header"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close details"><X size={17} /></button></div>{children}</div></div>; }

export default App;
