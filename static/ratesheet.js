mountNav("/ratesheet");
const COLS = ["product_id", "investor", "lock_period_days", "base_rate", "base_price"];
const PAGE = 50;

let rows = [];
let page = 0;
let filterQ = "";

function filteredRows() {
  const q = filterQ.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((r) =>
    COLS.some((c) => String(r[c] ?? "").toLowerCase().includes(q))
  );
}

function renderTable() {
  const vis = filteredRows();
  const pages = Math.max(1, Math.ceil(vis.length / PAGE));
  if (page >= pages) page = pages - 1;
  const slice = vis.slice(page * PAGE, page * PAGE + PAGE);
  const thead = document.querySelector("#tbl thead");
  const tbody = document.querySelector("#tbl tbody");
  thead.innerHTML = "<tr>" + COLS.map((c) => `<th>${c}</th>`).join("") + "<th></th></tr>";
  tbody.innerHTML = slice
    .map((r, i) => {
      const gi = rows.indexOf(r);
      const cells = COLS.map(
        (c) => `<td><input data-i="${gi}" data-c="${c}" value="${r[c] ?? ""}" /></td>`
      ).join("");
      return `<tr>${cells}<td><button type="button" data-del="${gi}" class="ghost">×</button></td></tr>`;
    })
    .join("");
  tbody.querySelectorAll("button[data-del]").forEach((b) =>
    b.addEventListener("click", () => {
      rows.splice(parseInt(b.dataset.del, 10), 1);
      renderTable();
    })
  );
  document.getElementById("pageInfo").textContent =
    vis.length ? `Page ${page + 1} of ${pages} (${vis.length} rows)` : "No rows";
  document.getElementById("pagePrev").disabled = page <= 0;
  document.getElementById("pageNext").disabled = page >= pages - 1;
}

async function load() {
  const res = await fetch("/api/admin/rate-sheet");
  const data = await res.json();
  document.getElementById("meta").textContent = metaLine(data.meta, (data.rows || []).length);
  rows = (data.rows || []).map((r) =>
    Object.fromEntries(COLS.map((c) => [c, r[c] ?? ""]))
  );
  page = 0;
  renderTable();
}

wireUpload("rate-sheet", null, () => load());

document.getElementById("tableSearch")?.addEventListener("input", (e) => {
  filterQ = e.target.value;
  page = 0;
  renderTable();
});
document.getElementById("pagePrev")?.addEventListener("click", () => {
  if (page > 0) {
    page--;
    renderTable();
  }
});
document.getElementById("pageNext")?.addEventListener("click", () => {
  page++;
  renderTable();
});

document.getElementById("addRow").addEventListener("click", () => {
  rows.push(Object.fromEntries(COLS.map((c) => [c, ""])));
  renderTable();
});

document.getElementById("saveEdit").addEventListener("click", async () => {
  document.querySelectorAll("#tbl input").forEach((inp) => {
    rows[parseInt(inp.dataset.i, 10)][inp.dataset.c] = inp.value;
  });
  const res = await fetch("/api/admin/rate-sheet", {
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