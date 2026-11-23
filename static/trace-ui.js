function traceStatusIcon(status) {
  if (status === "ok") return "✓";
  if (status === "fail") return "✗";
  return "○";
}

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function fmtPts(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function fmtUsd(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function fmtBest(summary) {
  return (summary?.best_by_product || [])
    .map(
      (b) =>
        `${b.product_id}: ${fmtPts(b.price ?? b.final_price)} pts @ ${b.rate ?? b.final_rate}%`
    )
    .join(" · ");
}

function stepSummary(step, ctx) {
  const o = step.output || {};
  const m = step.matched;
  switch (step.name) {
    case "validate_input": {
      const loan = o.loan || {};
      const br = o.borrower || {};
      const prop = o.property || {};
      const parts = [];
      if (loan.heloc_amount != null) parts.push(`heloc $${fmtUsd(loan.heloc_amount)}`);
      if (br.fico != null) parts.push(`FICO ${br.fico}`);
      if (prop.value != null) parts.push(`value $${fmtUsd(prop.value)}`);
      if (loan.lock_period_days != null) parts.push(`lock ${loan.lock_period_days}d`);
      if (loan.product_id) parts.push(`product ${loan.product_id}`);
      return parts.join(", ") || "inputs normalized";
    }
    case "compute_cltv": {
      const col = o.grid_a_cltv_column || o.grid_b_cltv_column;
      return `CLTV ${fmtPts(o.raw_cltv)} → ${fmtPts(o.rounded_cltv)}${
        col ? `, column ${col}` : ""
      }`;
    }
    case "load_rate_sheet_rows": {
      const inp = step.inputs || {};
      let filt = "";
      if (inp.lock_period_days != null) filt = ` (lock ${inp.lock_period_days})`;
      else if (inp.product_id) filt = ` (${inp.product_id})`;
      return `${o.rows_before_filter} → ${o.rows_after_filter} rows${filt}`;
    }
    case "match_grid_a_llpa": {
      if (!m) return o.reasons?.length ? o.reasons.join("; ") : "no band match";
      return `${m.row} × ${m.column} = ${fmtPts(o.llpa_value)}`;
    }
    case "match_grid_b_llpas":
      return o.llpa_total != null
        ? `sum = ${fmtPts(o.llpa_total)} pts`
        : o.reasons?.join("; ") || "—";
    case "apply_margin": {
      if (!m) return o.reason || "no margin band";
      return `row ${m.row}: $${fmtUsd(m.margin_dollar)} + ${m.margin_percent}% = ${fmtPts(
        o.margin_points
      )} pts`;
    }
    case "eligibility_checks": {
      if (o.eligible_count != null) {
        return `${o.eligible_count} eligible / ${o.ineligible_count} ineligible`;
      }
      const failed = (o.checks || []).filter((c) => !c.pass).map((c) => c.name);
      return failed.length ? `failed: ${failed.join(", ")}` : "all checks passed";
    }
    case "compute_final_price": {
      const base = `${o.eligible_count ?? 0} eligible / ${o.ineligible_count ?? 0} ineligible`;
      const best = fmtBest(ctx?.summary);
      return best ? `${base}; best per product: ${best}` : base;
    }
    default:
      return "";
  }
}

function gridBAttrSummary(a) {
  const hit = a.matched
    ? `${a.matched.row} × ${a.matched.column}`
    : a.reason || "no match";
  const val = a.value != null ? ` = ${fmtPts(a.value)} pts` : "";
  return `${a.attribute}: ${hit}${val}`;
}

function renderEngineTrace(trace, ctx) {
  if (!trace?.length) return "";
  const steps = trace
    .map((step) => {
      const summary = esc(stepSummary(step, ctx));
      const gbAttrs =
        step.name === "match_grid_b_llpas" && step.matched?.attributes
          ? `<ul class="trace-attrs">${step.matched.attributes
              .map(
                (a) =>
                  `<li class="trace-attr-line trace-${a.status}"><span class="trace-ico" aria-hidden="true">${traceStatusIcon(
                    a.status
                  )}</span><span class="trace-attr-sum">${esc(gridBAttrSummary(a))}</span></li>`
              )
              .join("")}</ul>`
          : "";
      const detail = esc(
        JSON.stringify(
          { inputs: step.inputs, matched: step.matched, output: step.output },
          null,
          2
        )
      );
      return `<li class="trace-step trace-${step.status}">
        <div class="trace-head">
          <span class="trace-ico" aria-hidden="true">${traceStatusIcon(step.status)}</span>
          <span class="trace-num">${step.step}.</span>
          <span class="trace-name">${esc(step.name)}</span>
          <span class="trace-sum">${summary}</span>
          <span class="trace-ms muted">${step.duration_ms?.toFixed(2) ?? "—"} ms</span>
        </div>
        ${gbAttrs}
        <details class="trace-out-details"><summary class="muted">Details</summary>
          <pre class="trace-out">${detail}</pre>
        </details>
      </li>`;
    })
    .join("");
  return `<ol class="engine-trace">${steps}</ol>`;
}