import { mountNav } from "./nav.js";

const component = document.body.dataset.component;
mountNav(document.body.dataset.nav || "/ratesheet");

const state = { rows: [], meta: null, cltv: [], gridRows: [] };
const msg = document.getElementById("msg");
const preview = document.getElementById("preview");
const tableHost = document.getElementById("tableHost");

async function refresh() {
  const r = await fetch(`/api/admin/${component}`);
  const data = await r.json();
  state.meta = data.meta;
  if (component === "grid-a" || component === "grid-b") {
    state.cltv = data.data?.cltv_labels || [];
    state.gridRows = data.data?.rows || [];
    renderGridTable();
  } else {
    state.rows = data.rows || [];
    renderFlatTable();
  }
  document.getElementById("meta").textContent = state.meta
    ? `File: ${state.meta.filename} · ${state.meta.uploaded_at}`
    : "No upload yet.";
}

function renderFlatTable() {
  if (!state.rows.length) {
    tableHost.innerHTML = "<p>No rows.</p>";
    return;
  }
  const keys = Object.keys(state.rows[0]);
  let h = "<table><thead><tr>" + keys.map((k) => `<th>${k}</th>`).join("") + "<th></th></tr></thead><tbody>";
  state.rows.forEach((row, i) => {
    h += "<tr>";
    keys.forEach((k) => {
      h += `<td contenteditable="true" data-i="${i}" data-k="${k}">${row[k]}</td>`;
    });
    h += `<td><button type="button" data-del="${i}">Del</button></td></tr>`;
  });
  h += "</tbody></table>";
  tableHost.innerHTML = h;
  tableHost.querySelectorAll("td[contenteditable]").forEach((td) => {
    td.onblur = () => {
      const i = +td.dataset.i;
      const k = td.dataset.k;
      state.rows[i][k] = td.textContent.trim();
    };
  });
  tableHost.querySelectorAll("button[data-del]").forEach((b) => {
    b.onclick = () => {
      state.rows.splice(+b.dataset.del, 1);
      renderFlatTable();
    };
  });
}

function renderGridTable() {
  if (!state.gridRows.length) {
    tableHost.innerHTML = "<p>No rows.</p>";
    return;
  }
  const cols = state.cltv;
  let headers;
  if (component === "grid-a") headers = ["fico_min", "fico_max", ...cols];
  else headers = ["attribute", "band", ...cols];
  let h = "<table><thead><tr>" + headers.map((x) => `<th>${x}</th>`).join("") + "<th></th></tr></thead><tbody>";
  state.gridRows.forEach((row, i) => {
    h += "<tr>";
    if (component === "grid-a") {
      h += cell(i, "fico_min", row.fico_min);
      h += cell(i, "fico_max", row.fico_max ?? "");
    } else {
      h += cell(i, "attribute", row.attribute);
      h += cell(i, "band", row.band);
    }
    cols.forEach((c) => {
      h += `<td contenteditable="true" data-i="${i}" data-c="${c}">${row.cells[c] ?? ""}</td>`;
    });
    h += `<td><button type="button" data-del="${i}">Del</button></td></tr>`;
  });
  h += "</tbody></table>";
  tableHost.innerHTML = h;
  wireGridEdit();
}

function cell(i, k, v) {
  return `<td contenteditable="true" data-i="${i}" data-f="${k}">${v}</td>`;
}

function wireGridEdit() {
  tableHost.querySelectorAll("td[contenteditable]").forEach((td) => {
    td.onblur = () => {
      const i = +td.dataset.i;
      const r = state.gridRows[i];
      if (td.dataset.f) {
        const k = td.dataset.f;
        let v = td.textContent.trim();
        if (k === "fico_max" && !v) r[k] = null;
        else if (k.startsWith("fico")) r[k] = v;
        else r[k] = v;
      } else if (td.dataset.c) {
        r.cells[td.dataset.c] = td.textContent.trim();
      }
    };
  });
  tableHost.querySelectorAll("button[data-del]").forEach((b) => {
    b.onclick = () => {
      state.gridRows.splice(+b.dataset.del, 1);
      renderGridTable();
    };
  });
}

document.getElementById("file")?.addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append("file", f);
  const r = await fetch(`/api/admin/${component}?preview=true`, { method: "POST", body: fd });
  const data = await r.json();
  preview.textContent = data.ok
    ? `Preview OK (${JSON.stringify(data.rows).slice(0, 400)}…)`
    : data.errors?.join("\n") || JSON.stringify(data);
});

document.getElementById("saveUpload")?.addEventListener("click", async () => {
  const f = document.getElementById("file").files[0];
  if (!f) return (msg.textContent = "Pick a file first.");
  const fd = new FormData();
  fd.append("file", f);
  const r = await fetch(`/api/admin/${component}`, { method: "POST", body: fd });
  const data = await r.json();
  msg.textContent = data.ok ? "Saved upload." : data.errors?.join("; ") || data.detail;
  if (data.ok) refresh();
});

document.getElementById("saveTable")?.addEventListener("click", async () => {
  let body;
  if (component === "grid-a" || component === "grid-b") {
    body = { cltv_labels: state.cltv, rows: state.gridRows };
  } else {
    body = { rows: state.rows };
  }
  const r = await fetch(`/api/admin/${component}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) msg.textContent = JSON.stringify(data.detail || data);
  else {
    msg.textContent = "Table saved.";
    refresh();
  }
});

document.getElementById("addRow")?.addEventListener("click", () => {
  if (component === "rate-sheet") state.rows.push({ product_id: "", investor: "", lock_period_days: 30, base_rate: 0, base_price: 100 });
  else if (component === "margins") state.rows.push({ loan_amount_min: 0, loan_amount_max: "", margin_dollar: 0, margin_percent: 0 });
  else if (component === "grid-a") state.gridRows.push({ fico_min: 0, fico_max: null, cells: Object.fromEntries(state.cltv.map((c) => [c, "0"])) });
  else state.gridRows.push({ attribute: "occupancy", band: "primary", band_lower: null, band_upper: null, cells: Object.fromEntries(state.cltv.map((c) => [c, "0"])) });
  component.startsWith("grid") ? renderGridTable() : renderFlatTable();
});

document.getElementById("download")?.addEventListener("click", () => {
  window.location.href = `/api/admin/${component}/download`;
});

refresh();