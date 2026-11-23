mountNav("/grids");

function gridTable(container, labels, rows, rowKeys) {
  const head = rowKeys.concat(labels);
  let html = "<table><thead><tr>" + head.map((h) => `<th>${h}</th>`).join("") + "</tr></thead><tbody>";
  rows.forEach((r, ri) => {
    html += "<tr>";
    rowKeys.forEach((k) => {
      html += `<td><input data-ri="${ri}" data-k="${k}" data-cltv="" value="${r[k] ?? ""}" /></td>`;
    });
    labels.forEach((lb) => {
      const v = (r.cells && r.cells[lb]) ?? "";
      html += `<td><input data-ri="${ri}" data-cltv="${lb}" data-k="" value="${v}" /></td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  container.innerHTML = html;
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
  document.getElementById("metaA").textContent = data.meta?.uploaded_at
    ? `File: ${data.meta.file_name}`
    : "No grid A yet.";
  const g = data.data;
  if (!g) return;
  gridA = { cltv_labels: g.cltv_labels, rows: g.rows };
  gridTable(document.getElementById("tableA"), g.cltv_labels, g.rows, ["fico_min", "fico_max"]);
}

async function loadB() {
  const res = await fetch("/api/admin/grid-b");
  const data = await res.json();
  document.getElementById("metaB").textContent = data.meta?.uploaded_at
    ? `File: ${data.meta.file_name}`
    : "No grid B yet.";
  const g = data.data;
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
  if (!res.ok) alert(JSON.stringify(await res.json()));
  else loadA();
});

document.getElementById("saveB").addEventListener("click", async () => {
  const container = document.getElementById("tableB");
  const rows = readGrid(container, gridB.cltv_labels, ["attribute", "band"]);
  const res = await fetch("/api/admin/grid-b", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cltv_labels: gridB.cltv_labels, rows }),
  });
  if (!res.ok) alert(JSON.stringify(await res.json()));
  else loadB();
});

async function uploadGrid(component, file, errId) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(`/api/admin/${component}`, { method: "POST", body: fd });
  const data = await r.json();
  const el = document.getElementById(errId);
  if (!data.ok) {
    el.textContent = (data.errors || []).join("; ");
    el.classList.remove("hidden");
    return;
  }
  el.classList.add("hidden");
  if (component === "grid-a") loadA();
  else loadB();
}

document.getElementById("fileInputA").addEventListener("change", (e) => {
  if (e.target.files[0]) uploadGrid("grid-a", e.target.files[0], "uploadErrA");
});
document.getElementById("fileInputB").addEventListener("change", (e) => {
  if (e.target.files[0]) uploadGrid("grid-b", e.target.files[0], "uploadErrB");
});

loadA();
loadB();