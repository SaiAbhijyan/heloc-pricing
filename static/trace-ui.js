function traceStatusIcon(status) {
  if (status === "ok") return "✓";
  if (status === "fail") return "✗";
  return "○";
}

function fmtTraceVal(v) {
  if (v == null) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function matchedLine(step) {
  const m = step.matched;
  if (!m) return "";
  if (step.name === "match_grid_b_llpas" && m.attributes) {
    return m.attributes
      .map((a) => {
        const hit = a.matched
          ? `${a.matched.row} × ${a.matched.column}`
          : a.reason || "no match";
        return `<li class="trace-attr trace-${a.status}"><span class="trace-ico">${traceStatusIcon(
          a.status
        )}</span> <strong>${a.attribute}</strong> — ${hit}${
          a.value != null ? ` → ${a.value} pts` : ""
        }</li>`;
      })
      .join("");
  }
  if (typeof m === "object" && !Array.isArray(m)) {
    return Object.entries(m)
      .map(([k, v]) => `${k}: ${fmtTraceVal(v)}`)
      .join(" · ");
  }
  return fmtTraceVal(m);
}

function renderEngineTrace(trace) {
  if (!trace?.length) return "";
  const steps = trace
    .map((step) => {
      const attrs =
        step.name === "match_grid_b_llpas"
          ? `<ul class="trace-attrs">${matchedLine(step)}</ul>`
          : "";
      const matched =
        step.name !== "match_grid_b_llpas" && step.matched
          ? `<p class="trace-matched"><span class="muted">Matched:</span> ${matchedLine(step)}</p>`
          : "";
      return `<li class="trace-step trace-${step.status}">
        <div class="trace-head">
          <span class="trace-ico" aria-hidden="true">${traceStatusIcon(step.status)}</span>
          <span class="trace-name">${step.step}. ${step.name}</span>
          <span class="trace-ms muted">${step.duration_ms?.toFixed(2) ?? "—"} ms</span>
        </div>
        ${matched}
        ${attrs}
        <details class="trace-out-details"><summary class="muted">Output</summary>
          <pre class="trace-out">${JSON.stringify(step.output, null, 2)}</pre>
        </details>
      </li>`;
    })
    .join("");
  return `<ol class="engine-trace">${steps}</ol>`;
}