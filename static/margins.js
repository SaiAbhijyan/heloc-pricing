mountNav("/margins");
const COLS = ["loan_amount_min", "loan_amount_max", "margin_dollar", "margin_percent"];

function renderTable(rows) {
  const thead = document.querySelector("#tbl thead");
  const tbody = document.querySelector("#tbl tbody");
  thead.innerHTML = "<tr>" + COLS.map((c) => `<th>${c}</th>`).join("") + "<th></th></tr>";
  tbody.innerHTML = rows
    .map((r, i) => {
      const cells = COLS.map(
        (c) =>
          `<td><input data-i="${i}" data-c="${c}" value="${r[c] ?? ""}" /></td>`
      ).join("");
      return `<tr>${cells}<td><button type="button" data-del="${i}" class="ghost">×</button></td></tr>`;
    })
    .join("");
  tbody.querySelectorAll("button[data-del]").forEach((b) =>
    b.addEventListener("click", () => {
      rows.splice(parseInt(b.dataset.del, 10), 1);
      renderTable(rows);
    })
  );
}

let rows = [];

async function load() {
  const res = await fetch("/api/admin/margins");
  const data = await res.json();
  document.getElementById("meta").textContent = metaLine(data.meta, (data.rows || []).length);
  rows = (data.rows || []).map((r) =>
    Object.fromEntries(COLS.map((c) => [c, r[c] ?? ""]))
  );
  renderTable(rows);
}

wireUpload("margins", null, () => load());

document.getElementById("addRow").addEventListener("click", () => {
  rows.push(Object.fromEntries(COLS.map((c) => [c, ""])));
  renderTable(rows);
});

document.getElementById("saveEdit").addEventListener("click", async () => {
  document.querySelectorAll("#tbl input").forEach((inp) => {
    rows[parseInt(inp.dataset.i, 10)][inp.dataset.c] = inp.value;
  });
  const res = await fetch("/api/admin/margins", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows }),
  });
  if (!res.ok) {
    alert(JSON.stringify(await res.json()));
    return;
  }
  load();
});

load();