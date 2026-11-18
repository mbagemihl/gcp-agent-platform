<script lang="ts">
  import { onMount } from 'svelte';

  interface SampleRfp {
    id: string;
    title: string;
    badge: 'GREEN' | 'RED';
    label: string;
    content: string;
  }

  interface TraceStep {
    step_type: string;
    label: string;
    status: string;
    trace_id?: string;
    span_id?: string;
    latency_ms?: number;
    details?: Record<string, unknown>;
    output?: unknown;
  }

  interface RagSource {
    title: string;
    source: string;
    score: number;
    text: string;
    backend: string;
  }

  interface McpCall {
    tool: string;
    request: Record<string, unknown>;
    response: Record<string, unknown>;
  }

  interface TokenUsage {
    model: string;
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
  }

  let samples: SampleRfp[] = $state([]);
  let selectedSampleId = $state('');
  let rfpTitle = $state('FinTech Data & AI Platform (GCP Cloud-Native)');
  let rfpText = $state('');
  let userQuery = $state('Bewerte Machbarkeit, Compliance-Risiken und benötigte Tagessätze.');
  let modelName = $state<'gemini-2.5-flash' | 'gemini-2.5-pro'>('gemini-2.5-flash');
  let includeRawTraceIds = $state(true);

  let isRunning = $state(false);
  let errorMessage = $state('');
  let statusBadge = $state<'GREEN' | 'YELLOW' | 'RED' | ''>('');
  let riskScore = $state<number | null>(null);
  let traceId = $state('');
  let responseMarkdown = $state('');
  let steps: TraceStep[] = $state([]);
  let ragSources: RagSource[] = $state([]);
  let mcpCalls: McpCall[] = $state([]);
  let tokenUsage = $state<TokenUsage | null>(null);

  onMount(async () => {
    try {
      const res = await fetch('/api/sample-rfps');
      if (res.ok) {
        const data = await res.json();
        samples = data.samples || [];
        if (samples.length > 0) {
          selectSample(samples[0]);
        }
      }
    } catch (err) {
      errorMessage = `Beispiel-RFPs konnten nicht geladen werden: ${String(err)}`;
    }
  });

  function selectSample(sample: SampleRfp) {
    selectedSampleId = sample.id;
    rfpTitle = sample.title;
    rfpText = sample.content;
    errorMessage = '';
  }

  async function handleFileUpload(event: Event) {
    const target = event.target as HTMLInputElement;
    const file = target.files?.[0];
    if (!file) return;
    selectedSampleId = '';
    rfpTitle = file.name.replace(/\.(md|txt)$/i, '');
    rfpText = await file.text();
  }

  function resetResults() {
    errorMessage = '';
    statusBadge = '';
    riskScore = null;
    traceId = '';
    responseMarkdown = '';
    steps = [];
    ragSources = [];
    mcpCalls = [];
    tokenUsage = null;
  }

  async function runAnalysis(event: SubmitEvent) {
    event.preventDefault();
    if (!rfpTitle.trim() || !rfpText.trim()) {
      errorMessage = 'Bitte RFP-Titel und RFP-Inhalt ausfüllen.';
      return;
    }

    isRunning = true;
    resetResults();

    try {
      const res = await fetch('/api/analyze-stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rfp_title: rfpTitle.trim(),
          rfp_text: rfpText.trim(),
          user_query: userQuery.trim(),
          model_name: modelName,
        }),
      });

      if (!res.ok || !res.body) {
        const errPayload = await res.text();
        throw new Error(errPayload || `HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          handleStreamEvent(JSON.parse(trimmed));
        }
      }

      if (buffer.trim()) {
        handleStreamEvent(JSON.parse(buffer.trim()));
      }
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : String(err);
    } finally {
      isRunning = false;
    }
  }

  function handleStreamEvent(event: Record<string, unknown>) {
    if (event.type === 'step_completed' && event.step) {
      const step = event.step as TraceStep;
      steps = [...steps, step];
      if (!traceId && step.trace_id) {
        traceId = step.trace_id;
      }
      if (step.step_type === 'rag_retrieval' && Array.isArray(step.output)) {
        ragSources = step.output as RagSource[];
      }
      if (step.step_type === 'mcp_tool_call' && step.output) {
        mcpCalls = [...mcpCalls, step.output as McpCall];
      }
      return;
    }

    if (event.type === 'final_result') {
      statusBadge = (event.status as 'GREEN' | 'YELLOW' | 'RED') || '';
      riskScore = typeof event.risk_score === 'number' ? event.risk_score : null;
      traceId = (event.trace_id as string) || traceId;
      responseMarkdown = (event.response_markdown as string) || '';
      if (Array.isArray(event.rag_sources)) {
        ragSources = event.rag_sources as RagSource[];
      }
      if (Array.isArray(event.mcp_calls)) {
        mcpCalls = event.mcp_calls as McpCall[];
      }
      if (event.token_usage) {
        tokenUsage = event.token_usage as TokenUsage;
      }
      return;
    }

    if (event.type === 'error') {
      errorMessage = String(event.detail || 'Unbekannter Agenten-Fehler');
    }
  }
</script>

<div class="app-shell">
  <header class="topbar">
    <div class="topbar-title">
      <span class="pill-brand">GCP Enterprise Agent Platform</span>
      <h1>RFP Compliance & Pricing Inspector</h1>
    </div>
    <div class="topbar-meta">
      <span>Region: <code>europe-west3</code></span>
      {#if traceId}
        <span>Trace: <code>{traceId.slice(0, 12)}…</code></span>
      {/if}
    </div>
  </header>

  <main class="split-grid">
    <!-- LEFT COLUMN: RFP Input + Chat Interaction -->
    <section class="panel scroller" aria-label="RFP Eingabe und Agenten-Chat">
      <div class="panel-header">
        <h2>1. Ausschreibung (RFP) &amp; Analyse-Chat</h2>
        <p class="muted">Wähle eine Beispiel-Ausschreibung oder lade ein eigenes Dokument hoch.</p>
      </div>

      {#if samples.length > 0}
        <div class="sample-row" role="group" aria-label="Beispiel-RFPs">
          {#each samples as sample}
            <button
              type="button"
              class="sample-card"
              class:active={selectedSampleId === sample.id}
              onclick={() => selectSample(sample)}
            >
              <span class="badge badge-{sample.badge.toLowerCase()}">{sample.label}</span>
              <span class="sample-title">{sample.title}</span>
            </button>
          {/each}
        </div>
      {/if}

      <form class="rfp-form" onsubmit={runAnalysis}>
        <div class="form-row-split">
          <div class="field">
            <label for="rfp-title">RFP Titel</label>
            <input id="rfp-title" type="text" bind:value={rfpTitle} required />
          </div>
          <div class="field">
            <label for="model-select">Vertex AI Modell</label>
            <select id="model-select" bind:value={modelName}>
              <option value="gemini-2.5-flash">gemini-2.5-flash</option>
              <option value="gemini-2.5-pro">gemini-2.5-pro</option>
            </select>
          </div>
        </div>

        <div class="field">
          <div class="field-label-row">
            <label for="rfp-text">RFP Text / Ausschreibungsinhalt</label>
            <label class="upload-btn">
              <span>.md / .txt laden</span>
              <input type="file" accept=".md,.txt,text/plain,text/markdown" onchange={handleFileUpload} />
            </label>
          </div>
          <textarea id="rfp-text" rows="9" bind:value={rfpText} required></textarea>
        </div>

        <div class="field">
          <label for="user-query">Frage an den Compliance- &amp; Pricing-Agenten</label>
          <input id="user-query" type="text" bind:value={userQuery} required />
        </div>

        <div class="form-actions">
          <label class="checkbox-label" for="toggle-trace-ids">
            <input
              id="toggle-trace-ids"
              type="checkbox"
              class="brand-checkbox"
              bind:checked={includeRawTraceIds}
            />
            <span>OpenTelemetry Span-IDs anzeigen</span>
          </label>

          <button type="submit" class="primary-btn" disabled={isRunning}>
            {isRunning ? 'Agent analysiert…' : 'RFP analysieren & prüfen'}
          </button>
        </div>
      </form>

      {#if errorMessage}
        <div class="alert-error" role="alert">
          <strong>Fehler:</strong> {errorMessage}
        </div>
      {/if}

      {#if statusBadge}
        <div class="verdict-banner verdict-{statusBadge.toLowerCase()}">
          <div>
            <span class="verdict-label">Ampel-Status</span>
            <strong>{statusBadge}</strong>
          </div>
          {#if riskScore !== null}
            <div class="risk-meter">
              <span>Risiko-Score: <strong>{riskScore}/100</strong></span>
              <progress max="100" value={riskScore}></progress>
            </div>
          {/if}
        </div>
      {/if}

      {#if responseMarkdown}
        <article class="agent-response" aria-label="Agenten-Ergebnis">
          <h3>Agenten-Empfehlung</h3>
          <pre class="markdown-output">{responseMarkdown}</pre>
        </article>
      {/if}
    </section>

    <!-- RIGHT COLUMN: Under the Hood (Traces, RAG Sources, MCP Payloads, Costs) -->
    <section class="panel inspector scroller" aria-label="Under the Hood Live-Inspector">
      <div class="panel-header">
        <h2>2. „Under the Hood“ – Live Trace &amp; Tool Inspector</h2>
        <p class="muted">Echtzeit-Stream aus OpenTelemetry, Vertex AI RAG und MCP Pricing Server.</p>
      </div>

      {#if tokenUsage}
        <div class="telemetry-kpi-grid">
          <div class="kpi-card">
            <span class="kpi-label">Modell</span>
            <strong class="kpi-value">{tokenUsage.model}</strong>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Tokens (In / Out)</span>
            <strong class="kpi-value">{tokenUsage.input_tokens} / {tokenUsage.output_tokens}</strong>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Gesamt-Tokens</span>
            <strong class="kpi-value">{tokenUsage.total_tokens}</strong>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Geschätzte Kosten</span>
            <strong class="kpi-value">${tokenUsage.estimated_cost_usd.toFixed(6)}</strong>
          </div>
        </div>
      {/if}

      <div class="inspector-block">
        <h3>Ausführungs-Timeline (OpenTelemetry Spans)</h3>
        {#if steps.length === 0}
          <p class="empty-hint">Noch keine Analyse gestartet. Starte links eine Prüfung, um Live-Spans zu sehen.</p>
        {:else}
          <ol class="timeline">
            {#each steps as step, index}
              <li class="timeline-item">
                <div class="timeline-head">
                  <span class="step-index">#{index + 1}</span>
                  <span class="step-type">{step.step_type}</span>
                  <strong class="step-label">{step.label}</strong>
                  {#if step.latency_ms !== undefined}
                    <span class="latency-pill">{step.latency_ms} ms</span>
                  {/if}
                </div>
                {#if includeRawTraceIds && step.span_id}
                  <div class="span-meta">
                    span_id: <code>{step.span_id}</code> · status: <code>{step.status}</code>
                  </div>
                {/if}
              </li>
            {/each}
          </ol>
        {/if}
      </div>

      <div class="inspector-block">
        <h3>Abgerufene Vertex AI RAG Policies ({ragSources.length})</h3>
        {#if ragSources.length === 0}
          <p class="empty-hint">Policy-Passagen erscheinen hier nach dem RAG-Retrieval.</p>
        {:else}
          <div class="rag-list">
            {#each ragSources as src}
              <div class="rag-card">
                <div class="rag-head">
                  <strong>{src.title}</strong>
                  <span class="backend-pill">{src.backend}</span>
                </div>
                <div class="rag-score-row">
                  <span>Relevanz: {(src.score * 100).toFixed(0)}%</span>
                  <progress max="1" value={src.score}></progress>
                </div>
                <p class="rag-excerpt">{src.text}</p>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="inspector-block">
        <h3>MCP Tool-Payloads ({mcpCalls.length})</h3>
        {#if mcpCalls.length === 0}
          <p class="empty-hint">Live-Aufrufe gegen <code>mcp-pricing-server</code> erscheinen hier.</p>
        {:else}
          <div class="mcp-list">
            {#each mcpCalls as call}
              <div class="mcp-card">
                <div class="mcp-head">
                  <strong>{call.tool}</strong>
                </div>
                <div class="payload-pair">
                  <div>
                    <span class="payload-label">Request</span>
                    <pre class="json-code">{JSON.stringify(call.request, null, 2)}</pre>
                  </div>
                  <div>
                    <span class="payload-label">Response</span>
                    <pre class="json-code">{JSON.stringify(call.response, null, 2)}</pre>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </section>
  </main>
</div>

<style>
  .app-shell {
    display: grid;
    grid-template-rows: auto 1fr;
    min-block-size: 100dvb;
    inline-size: 100%;
    padding: 1rem 1.25rem 1.5rem;
    gap: 1rem;
  }

  .topbar {
    display: flex;
    flex-wrap: wrap;
    align-items: safe center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.9rem 1.2rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
  }

  .topbar-title {
    display: flex;
    flex-wrap: wrap;
    align-items: safe center;
    gap: 0.75rem;
  }

  .topbar-title h1 {
    margin: 0;
    font-size: 1.2rem;
    font-weight: 700;
  }

  .pill-brand {
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0.25rem 0.65rem;
    border-radius: 999px;
    background: var(--brand-accent);
    color: var(--brand-accent-text);
  }

  .topbar-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .split-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
    gap: 1rem;
    align-items: start;
  }

  @media (max-width: 980px) {
    .split-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    min-inline-size: 0;
    max-block-size: calc(100dvb - 7.5rem);
    overflow-y: auto;
    scrollbar-gutter: stable;
    overscroll-behavior: contain;
  }

  @media (max-width: 980px) {
    .panel {
      max-block-size: none;
    }
  }

  .panel-header h2 {
    margin: 0;
    font-size: 1.05rem;
  }

  .muted {
    margin: 0.2rem 0 0;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .sample-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.75rem;
  }

  .sample-card {
    text-align: start;
    background: var(--surface-muted);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.75rem;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    transition: border-color 0.15s ease;
  }

  .sample-card.active,
  .sample-card:hover {
    border-color: var(--brand-accent);
  }

  .sample-title {
    font-weight: 600;
    font-size: 0.9rem;
  }

  .badge {
    display: inline-block;
    inline-size: fit-content;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    border-radius: 999px;
  }

  .badge-green {
    background: var(--status-green-bg);
    color: var(--status-green-fg);
  }

  .badge-red {
    background: var(--status-red-bg);
    color: var(--status-red-fg);
  }

  .rfp-form {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
  }

  .form-row-split {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 210px);
    gap: 0.75rem;
  }

  @media (max-width: 600px) {
    .form-row-split {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    min-inline-size: 0;
  }

  .field label {
    font-size: 0.85rem;
    font-weight: 600;
  }

  .field-label-row {
    display: flex;
    align-items: safe center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .upload-btn {
    font-size: 0.8rem;
    color: var(--brand-accent);
    cursor: pointer;
    text-decoration: underline;
  }

  .upload-btn input {
    display: none;
  }

  input[type='text'],
  select,
  textarea {
    inline-size: 100%;
    padding: 0.55rem 0.7rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text);
    font: inherit;
    font-size: 0.9rem;
  }

  textarea {
    resize: vertical;
  }

  .form-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: safe center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .checkbox-label {
    display: inline-flex;
    align-items: safe center;
    gap: 0.5rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .primary-btn {
    padding: 0.6rem 1.15rem;
    border: none;
    border-radius: 8px;
    background: var(--brand-accent);
    color: var(--brand-accent-text);
    font-weight: 700;
    font-size: 0.9rem;
    cursor: pointer;
  }

  .primary-btn:disabled {
    opacity: 0.65;
    cursor: wait;
  }

  .alert-error {
    padding: 0.75rem;
    border-radius: 8px;
    background: var(--status-red-bg);
    color: var(--status-red-fg);
    font-size: 0.9rem;
  }

  .verdict-banner {
    display: flex;
    flex-wrap: wrap;
    align-items: safe center;
    justify-content: space-between;
    gap: 1rem;
    padding: 0.85rem 1rem;
    border-radius: 10px;
  }

  .verdict-green {
    background: var(--status-green-bg);
    color: var(--status-green-fg);
  }

  .verdict-yellow {
    background: var(--status-yellow-bg);
    color: var(--status-yellow-fg);
  }

  .verdict-red {
    background: var(--status-red-bg);
    color: var(--status-red-fg);
  }

  .verdict-label {
    display: block;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .risk-meter {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-inline-size: 170px;
    font-size: 0.85rem;
  }

  .agent-response {
    border-top: 1px solid var(--border);
    padding-top: 0.75rem;
    min-inline-size: 0;
  }

  .agent-response h3 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
  }

  .markdown-output {
    margin: 0;
    padding: 0.9rem;
    border-radius: 8px;
    background: #0f172a;
    color: #e2e8f0;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.85rem;
    line-height: 1.55;
  }

  .telemetry-kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 0.6rem;
  }

  .kpi-card {
    background: var(--surface-muted);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .kpi-label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .kpi-value {
    font-size: 0.9rem;
  }

  .inspector-block {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    min-inline-size: 0;
  }

  .inspector-block h3 {
    margin: 0;
    font-size: 0.95rem;
  }

  .empty-hint {
    margin: 0;
    padding: 0.75rem;
    border-radius: 8px;
    background: var(--surface-muted);
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .timeline {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .timeline-item {
    background: var(--surface-muted);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .timeline-head {
    display: flex;
    flex-wrap: wrap;
    align-items: safe center;
    gap: 0.45rem;
    font-size: 0.85rem;
  }

  .step-index {
    font-weight: 700;
    color: var(--brand-accent);
  }

  .step-type {
    font-size: 0.75rem;
    padding: 0.1rem 0.45rem;
    border-radius: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
  }

  .step-label {
    min-inline-size: 0;
  }

  .latency-pill {
    margin-inline-start: auto;
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .span-meta {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .rag-list,
  .mcp-list {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    min-inline-size: 0;
  }

  .rag-card,
  .mcp-card {
    background: var(--surface-muted);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    min-inline-size: 0;
  }

  .rag-head,
  .mcp-head {
    display: flex;
    align-items: safe center;
    justify-content: space-between;
    gap: 0.5rem;
    font-size: 0.85rem;
  }

  .backend-pill {
    font-size: 0.72rem;
    padding: 0.1rem 0.45rem;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
  }

  .rag-score-row {
    display: flex;
    align-items: safe center;
    gap: 0.65rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  .rag-score-row progress {
    flex: 1 1 auto;
  }

  .rag-excerpt {
    margin: 0;
    font-size: 0.82rem;
    color: var(--text-muted);
  }

  .payload-pair {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.5rem;
    min-inline-size: 0;
  }

  .payload-label {
    display: block;
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-bottom: 0.2rem;
  }

  .json-code {
    margin: 0;
    padding: 0.55rem;
    border-radius: 6px;
    background: #0d1117;
    color: #c9d1d9;
    font-size: 0.75rem;
    overflow-x: auto;
    max-block-size: 180px;
  }
</style>
