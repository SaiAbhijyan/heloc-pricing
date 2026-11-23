mountNav("/grids");

function formatMeta(meta, rowCount) {
  if (!meta?.uploaded_at) return "No upload yet.";
  const t = new Date(meta.uploaded_at).toLocaleString();
  return `Loaded ${meta.filename} at ${t}, ${rowCount} rows`;
}

function gridTable(container, labels, rows, rowKeys, yPrefix) {
  const head = rowKeys.map((k) => `<th class="grid-y-label">${k}</th>`).join("");
  const cltvHead = labels
    .map((h) => `<th class="cltv-head">${h}<small>CLTV %</small></th>`)
    .join("");
  let html =
    '<motion-remove/><div class="table-scroll"><table class="grid-table"><thead><tr>' +
    head +
    cltvHead +
    "</tr></thead><tbody>";
  rows.forEach((r, ri) => {
    html += "<tr>";
    rowKeys.forEach((k) => {
      html += `<td class="grid-y-label"><input data-ri="${ri}" data-k="${k}" data-cltv="" value="${r[k] ?? ""}" /></td>`;
    });
    labels.forEach((lb) => {
      const v = (r.cells && r.cells[lb]) ?? "";
      const na = String(v).toUpperCase() === "NA" || String(v).toUpperCase() === "N/A";
      html += `<td class="${na ? "na-cell" : ""}"><input data-ri="${ri}" data-cltv="${lb}" data-k="" value="${v}" /></td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table></div>";
  container.innerHTML = html.replace("<motion-remove/>", "");
}

let gridA = { cltv_labels: [], rows: [] };
let gridB = { cltv_labels: [], rows: [] };

function readGrid(container, labels, rowKeys) {
  const rows = [];
  const inputs = container.querySelectorAll("input");
  const maxRi = Math.max(...[...inputs].map((i) => parseInt(i.dataset.ri, 10)));
  for (let ri = 0; ri <= maxRi; ri++) {
    const row = { cells: {} };
    rowKeys.forEach((k) => (row[k] = ""));
    labels.forEach((lb) => (row.cells[lb] = ""));
    rows.push(row);
  }
  inputs.forEach((inp) => {
    const ri = parseInt(inp.dataset.ri, 10);
    if (inp.dataset.cltv) rows[ri].cells[inp.dataset.cltv] = inp.value;
    else rows[ri][inp.dataset.k] = inp.value;
  });
  return rows;
}

async function loadA() {
  const res = await fetch("/api/admin/grid-a");
  const data = await res.json();
  const g = data.data;
  const n = g?.rows?.length ?? 0;
  document.getElementById("metaA").textContent = formatMeta(data.meta, n);
  if (!g) return;
  gridA = { cltv_labels: g.cltv_labels, rows: g.rows };
  gridTable(document.getElementById("tableA"), g.cltv_labels, g.rows, ["fico_min", "fico_max"]);
}

async function loadB() {
  const res = await fetch("/api/admin/grid-b");
  const data = await res.json();
  const g = data.data;
  const n = g?.rows?.length ?? 0;
  document.getElementById("metaB").textContent = formatMeta(data.meta, n);
  if (!g) return;
  gridB = { cltv_labels: g.cltv_labels, rows: g.rows };
  gridTable(document.getElementById("tableB"), g.cltv_labels, g.rows, ["attribute", "band"]);
}

document.getElementById("saveA").addEventListener("click", async () => {
  const container = document.getElementById("tableA");
  const rows = readGrid(container, gridA.cltv_labels, ["fico_min", "fico_max"]);
  const res = await fetch("/api/admin/grid-a", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cltv_labels: gridA.cltv_labels, rows }),
  });
  const errEl = document.getElementById("uploadErrA");
  if (!res.ok) {
    const data = await res.json();
    errEl.textContent = JSON.stringify(data.detail || data);
    errEl.classList.remove("hidden");
    return;
  }
  errEl.classList.add("hidden");
  loadA();
});

document.getElementById("saveB").addEventListener("click", async () => {
  const container = document.getElementById("tableB");
  const rows = readGrid(container, gridB.cltv_labels, ["attribute", "band"]);
  const res = await fetch("/api/admin/grid-b", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cltv_labels: gridB.cltv_labels, rows }),
  });
  const errEl = document.getElementById("uploadErrB");
  if (!res.ok) {
    const data = await res.json();
    errEl.textContent = JSON.stringify(data.detail || data);
    errEl.classList.remove("hidden");
    return;
  }
  errEl.classList.add("hidden");
  loadB();
});

async function previewGrid(component, file, errId, previewId, onCommit) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/api/admin/${component}?preview=true`, { method: "POST", body: fd });
  const data = await r.json();
  const el = document.getElementById(errId);
  const prev = document.getElementById(previewId);
  if (!data.ok) {
    el.textContent = (data.errors || []).join("; ");
    el.classList.remove("hidden");
    prev.classList.add("hidden");
    return;
  }
  el.classList.add("hidden");
  prev.classList.remove("hidden");
  const n = data.rows?.rows?.length ?? (Array.isArray(data.rows) ? data.rows.length : 0);
  prev.innerHTML = `<p class="ok">${n} rows parsed. <button type="button" class="secondary" id="commit${component}">Save</button> <button type="button" class="ghost" id="cancel${component}">Cancel</button></p>`;
  document.getElementById(`commit${component}`).onclick = async () => {
    const fd2 = new FormData();
    fd2.append("file", file);
    await fetch(`/api/admin/${component}`, { method: "POST", body: fd2 });
    prev.classList.add("hidden");
    onCommit();
  };
  document.getElementById(`cancel${component}`).onclick = () => prev.classList.add("hidden");
}

document.getElementById("fileInputA").addEventListener("change", (e) => {
  if (e.target.files[0])
    previewGrid("grid-a", e.target.files[0], "uploadErrA", "previewA", loadA);
});
document.getElementById("fileInputB").addEventListener("change", (e) => {
  if (e.target.files[0])
    previewGrid("grid-b", e.target.files[0], "uploadErrB", "previewB", loadB);
});

loadA();
loadB();