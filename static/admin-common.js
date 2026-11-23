function metaLine(meta, rowCount) {
  if (!meta?.uploaded_at) return "No upload yet.";
  const t = new Date(meta.uploaded_at).toLocaleString();
  const n = rowCount != null ? `, ${rowCount} rows` : "";
  return `Loaded ${meta.filename || "—"} at ${t}${n}`;
}

async function uploadFile(component, file, preview) {
  const fd = new FormData();
  fd.append("file", file);
  const url = `/api/admin/${component}${preview ? "?preview=true" : ""}`;
  return fetch(url, { method: "POST", body: fd });
}

function previewSummaryHtml(summary, component) {
  if (!summary) return "";
  if (component === "rate-sheet") {
    const parts = [
      `<strong>${summary.row_count ?? "—"}</strong> rows`,
      summary.products?.length ? `${summary.products.length} products` : "",
      summary.investors?.length ? `${summary.investors.length} investors` : "",
      summary.locks?.length ? `locks ${summary.locks.join(", ")}d` : "",
    ].filter(Boolean);
    const ranges = [];
    if (summary.rate_min != null)
      ranges.push(`rates ${summary.rate_min}–${summary.rate_max}%`);
    if (summary.price_min != null)
      ranges.push(`prices ${summary.price_min}–${summary.price_max}`);
    return `<p class="preview-summary">${parts.join(" · ")}${ranges.length ? `<br/>${ranges.join(" · ")}` : ""}</p>`;
  }
  if (component === "margins") {
    return `<p class="preview-summary"><strong>${summary.row_count ?? "—"}</strong> margin band(s)</p>`;
  }
  return `<p class="preview-summary"><strong>${summary.row_count ?? "—"}</strong> rows · ${summary.cltv_columns ?? "?"} CLTV columns</p>`;
}

function previewSampleTable(rows, component) {
  const flat = Array.isArray(rows)
    ? rows
    : rows?.rows && Array.isArray(rows.rows)
      ? rows.rows
      : [];
  if (!flat.length) return "";
  if (component === "rate-sheet") {
    const cols = ["product_id", "investor", "lock_period_days", "base_rate", "base_price"];
    let html =
      '<div class="table-scroll"><table class="results-table preview-sample"><thead><tr>' +
      cols.map((c) => `<th>${c}</th>`).join("") +
      "</tr></thead><tbody>";
    flat.forEach((r) => {
      html += "<tr>" + cols.map((c) => `<td>${r[c] ?? ""}</td>`).join("") + "</tr>";
    });
    return html + "</tbody></table></div>";
  }
  if (component === "margins") {
    const cols = ["loan_amount_min", "loan_amount_max", "margin_dollar", "margin_percent"];
    let html =
      '<div class="table-scroll"><table class="results-table preview-sample"><thead><tr>' +
      cols.map((c) => `<th>${c}</th>`).join("") +
      "</tr></thead><tbody>";
    flat.forEach((r) => {
      html += "<tr>" + cols.map((c) => `<td>${r[c] ?? ""}</td>`).join("") + "</tr>";
    });
    return html + "</tbody></table></div>";
  }
  return `<pre class="preview-sample-json">${JSON.stringify(rows, null, 2).slice(0, 4000)}</pre>`;
}

function renderUploadPreview(previewEl, data, component, onSaved) {
  const errs = data.errors || [];
  let html = previewSummaryHtml(data.summary, component);
  if (errs.length) {
    html += `<ul class="preview-errors">${errs.map((e) => `<li>${e}</li>`).join("")}</ul>`;
  }
  html += '<p class="muted">First parsed rows (max 20):</p>';
  html += previewSampleTable(data.rows, component);
  html +=
    '<motion-remove/><div class="row" style="margin-top:0.75rem">' +
    '<button type="button" id="saveUpload" class="secondary">Save upload</button>' +
    '<button type="button" id="cancelUpload" class="ghost">Cancel</button></div>';
  previewEl.innerHTML = html.replace("<motion-remove/>", "");
  previewEl.querySelector("#cancelUpload")?.addEventListener("click", () => {
    window.__pendingUpload = null;
    previewEl.innerHTML = "";
  });
  previewEl.querySelector("#saveUpload")?.addEventListener("click", async () => {
    const up = window.__pendingUpload;
    if (!up) return;
    const res = await uploadFile(component, up.file, false);
    const saved = await res.json();
    if (!saved.ok) {
      const errEl = document.getElementById("uploadErr");
      if (errEl) {
        errEl.textContent = JSON.stringify(saved);
        errEl.classList.remove("hidden");
      }
      return;
    }
    window.__pendingUpload = null;
    previewEl.innerHTML = "";
    onSaved?.(saved);
  });
}

function wireUpload(component, onPreview, onSaved) {
  const input = document.getElementById("fileInput");
  const zone = document.getElementById("dropZone");
  const errEl = document.getElementById("uploadErr");
  const previewEl = document.getElementById("previewBox");

  async function handle(file) {
    errEl.classList.add("hidden");
    previewEl.innerHTML = "";
    const r = await uploadFile(component, file, true);
    const data = await r.json();
    if (!data.ok) {
      errEl.textContent = (data.errors || [data.detail]).join("; ");
      errEl.classList.remove("hidden");
      return;
    }
    pending(file);
    renderUploadPreview(previewEl, data, component, onSaved);
    onPreview?.(data, file);
  }

  input.addEventListener("change", () => {
    if (input.files[0]) handle(input.files[0]);
  });
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    if (e.dataTransfer.files[0]) handle(e.dataTransfer.files[0]);
  });
}

function pending(file) {
  window.__pendingUpload = { file };
}