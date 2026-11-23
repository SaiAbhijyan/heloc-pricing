mountNav("/");

const $ = (id) => document.getElementById(id);
let lastData = null;
const PAR = 100;

function parseMoney(id) {
  const raw = $(id).value.replace(/,/g, "").trim();
  return parseFloat(raw) || 0;
}

function fmtMoney(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-US", { maximumFractionDigits: 3 });
}

function updateCltv() {
  const heloc = parseMoney("heloc_amount");
  const lien = parseMoney("first_lien_balance");
  const val = parseMoney("value");
  const el = $("cltvLive");
  if (val <= 0) {
    el.textContent = "—";
    return;
  }
  el.textContent = (((lien + heloc) / val) * 100).toFixed(2);
}

["heloc_amount", "first_lien_balance", "value"].forEach((id) =>
  $(id).addEventListener("input", updateCltv)
);
updateCltv();

async function loadProducts() {
  try {
    const res = await fetch("/api/products");
    if (!res.ok) return;
    const data = await res.json();
    const sel = $("product_id");
    (data.product_ids || []).forEach((pid) => {
      const o = document.createElement("option");
      o.value = pid;
      o.textContent = pid;
      sel.appendChild(o);
    });
  } catch {
    /* empty db on first paint */
  }
}
loadProducts();

function buildPayload() {
  const loan = {
    heloc_amount: parseMoney("heloc_amount"),
    first_lien_balance: parseMoney("first_lien_balance"),
  };
  const lock = $("lock_period_days").value;
  if (lock) loan.lock_period_days = parseInt(lock, 10);
  const pid = $("product_id").value;
  if (pid) loan.product_id = pid;
  return {
    loan,
    borrower: { fico: parseInt($("fico").value, 10), dti: parseFloat($("dti").value) },
    property: {
      value: parseMoney("value"),
      occupancy: $("occupancy").value,
      property_type: $("property_type").value,
    },
  };
}

function clientValidate(body) {
  let ok = true;
  const show = (id, msg) => {
    const el = $(id);
    if (msg) {
      el.textContent = msg;
      el.classList.remove("hidden");
      ok = false;
    } else el.classList.add("hidden");
  };
  show("err_heloc", body.loan.heloc_amount > 0 ? "" : "Must be greater than 0.");
  show("err_lien", body.loan.first_lien_balance >= 0 ? "" : "Cannot be negative.");
  show("err_value", body.property.value > 0 ? "" : "Must be greater than 0.");
  show(
    "err_fico",
    body.borrower.fico >= 300 && body.borrower.fico <= 850 ? "" : "FICO must be 300–850."
  );
  show(
    "err_dti",
    body.borrower.dti >= 0 && body.borrower.dti <= 100 ? "" : "DTI must be 0–100."
  );
  return ok ? "" : "Fix the fields above.";
}

function ledgerHtml(steps) {
  if (!steps?.length) return "";
  return (
    '<ul class="ledger">' +
    steps
      .map((s) => {
        const v = s.value != null ? fmtMoney(s.value) : "";
        const cls = Number(s.value) < 0 ? "ledger-neg" : "";
        return `<li class="${cls}"><span class="ledger-label">${s.label}</span><span class="ledger-val">${v}</span></li>`;
      })
      .join("") +
    "</ul>"
  );
}

function passFilters(r) {
  const fp = $("filterProduct").value;
  const fi = $("filterInvestor").value;
  const fl = $("filterLock").value;
  const fe = $("filterEligible").checked;
  if (fp && r.product_id !== fp) return false;
  if (fi && r.investor !== fi) return false;
  if (fl && String(r.lock_period_days) !== fl) return false;
  if (fe && !r.eligible) return false;
  return true;
}

function pickBestRow(rows) {
  const eligible = rows.filter((r) => r.eligible && r.final_price != null);
  if (!eligible.length) return null;
  const atPar = eligible.filter((r) => r.final_price >= PAR);
  if (atPar.length) {
    return atPar.reduce((a, b) =>
      b.final_rate < a.final_rate || (b.final_rate === a.final_rate && b.final_price > a.final_price)
        ? b
        : a
    );
  }
  return eligible.reduce((a, b) => (b.final_price > a.final_price ? b : a));
}

function ladderKey(r) {
  return `${r.product_id}\0${r.investor}\0${r.lock_period_days}`;
}

function parPicksOnly(rows) {
  const groups = new Map();
  rows.forEach((r) => {
    const k = ladderKey(r);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(r);
  });
  const out = [];
  groups.forEach((g) => {
    const pick = pickBestRow(g);
    if (pick) out.push(pick);
  });
  return out;
}

function renderSummaryBar(data) {
  const s = data.summary || {};
  const best = (s.best_by_product || [])
    .map(
      (b) =>
        `${b.product_id}: ${fmtMoney(b.price ?? b.final_price)} pts @ ${b.rate ?? b.final_rate}%`
    )
    .join(" · ");
  $("summaryBar").innerHTML = `<strong>${s.eligible_count ?? 0}</strong> eligible of <strong>${s.total_count ?? 0}</strong> priced. ${
    best ? `Best per product: ${best}` : ""
  }`;
}

function fillFilterOptions(data) {
  const products = [...new Set(data.results.map((r) => r.product_id))].sort();
  const investors = [...new Set(data.results.map((r) => r.investor))].sort();
  const locks = [...new Set(data.results.map((r) => r.lock_period_days))].sort((a, b) => a - b);
  const fp = $("filterProduct");
  const fi = $("filterInvestor");
  const fl = $("filterLock");
  [fp, fi, fl].forEach((el) => {
    while (el.options.length > 1) el.remove(1);
  });
  products.forEach((p) => fp.appendChild(new Option(p, p)));
  investors.forEach((p) => fi.appendChild(new Option(p, p)));
  locks.forEach((p) => fl.appendChild(new Option(String(p), String(p))));
}

function reasonGroupKey(reasons) {
  return (reasons || []).slice().sort().join("\0");
}

function renderIneligibleGroups(ineligible) {
  const groups = new Map();
  ineligible.forEach((r) => {
    const k = reasonGroupKey(r.reasons);
    if (!groups.has(k)) groups.set(k, { reasons: r.reasons || [], rows: [] });
    groups.get(k).rows.push(r);
  });
  const sorted = [...groups.values()].sort((a, b) => b.rows.length - a.rows.length);
  return sorted
    .map((g, gi) => {
      const rowsHtml = g.rows
        .map(
          (r) =>
            `<li>${r.product_id} · ${r.investor} · ${r.lock_period_days}d lock</li>`
        )
        .join("");
      return `<details class="inelig-group" data-gi="${gi}">
        <summary>
          <ul class="reason-list reason-inline">${g.reasons.map((x) => `<li>${x}</li>`).join("")}</ul>
          <span class="inelig-count">applies to ${g.rows.length} row${g.rows.length === 1 ? "" : "s"}</span>
        </summary>
        <ul class="inelig-rows">${rowsHtml}</ul>
      </details>`;
    })
    .join("");
}

function renderEngineTracePanel(data) {
  const panel = $("tracePanel");
  const el = $("engineTrace");
  if (!data.trace?.length) {
    panel.classList.add("hidden");
    return;
  }
  panel.classList.remove("hidden");
  panel.open = true;
  el.innerHTML = renderEngineTrace(data.trace, { summary: data.summary });
}

function renderResults(data) {
  lastData = data;
  $("resultsPanel").classList.remove("hidden");
  renderSummaryBar(data);
  renderEngineTracePanel(data);
  fillFilterOptions(data);

  let eligible = data.results.filter((r) => r.eligible && passFilters(r));
  const showAll = $("showFullLadder")?.checked;
  if (!showAll) eligible = parPicksOnly(eligible);
  eligible.sort((a, b) => {
    if (a.product_id !== b.product_id) return a.product_id.localeCompare(b.product_id);
    if (a.lock_period_days !== b.lock_period_days) return a.lock_period_days - b.lock_period_days;
    if (a.investor !== b.investor) return a.investor.localeCompare(b.investor);
    return (a.final_rate || 0) - (b.final_rate || 0);
  });

  const ineligible = data.results.filter((r) => !r.eligible && passFilters(r));

  $("summary").textContent = `${eligible.length} eligible row(s) shown`;
  $("summary").classList.remove("hidden");

  const colSpan = 9;
  let tbody = "";
  let lastProduct = null;
  let rowIndex = 0;
  const rowRefs = [];
  const openState = new Set(
    [...document.querySelectorAll("tr.ledger-row:not(.hidden)")].map((tr) => tr.dataset.ledger)
  );
  eligible.forEach((r) => {
    if (r.product_id !== lastProduct) {
      lastProduct = r.product_id;
      tbody += `<tr class="product-head"><td colspan="${colSpan}">${r.product_id}</td></tr>`;
    }
    const hi = r.best ? "row-best" : "";
    const i = rowIndex++;
    rowRefs.push(r);
    const open = openState.has(String(i));
    tbody += `<tr class="eligible-row ${hi}" data-testid="result-row" data-i="${i}" tabindex="0"><td><span class="details-affordance" aria-hidden="true">▸</span> ${r.product_id}</td><td>${r.investor}</td><td>${r.lock_period_days}d</td><td>${fmtMoney(
      r.base_rate
    )}%</td><td>${fmtMoney(r.base_price)}</td><td>${fmtMoney(r.llpa_total)}</td><td>${fmtMoney(
      r.margin?.points
    )}</td><td><strong>${fmtMoney(r.final_price)}</strong></td><td>${fmtMoney(r.final_rate)}%</td></tr>`;
    tbody += `<tr class="ledger-row ${open ? "" : "hidden"}" data-testid="breakdown" data-ledger="${i}"><td colspan="${colSpan}"><div class="ledger-panel">${
      open ? `<h3>Price breakdown · ${r.product_id} · ${r.investor}</h3>${ledgerHtml(r.steps)}` : ""
    }</div></td></tr>`;
  });

  const eEl = $("eligible");
  eEl.classList.toggle("hidden", !eligible.length);
  eEl.innerHTML =
    "<h2>Eligible</h2>" +
    '<div class="table-scroll"><table class="results-table"><thead><tr>' +
    "<th>Product</th><th>Investor</th><th>Lock</th><th>Base rate</th><th>Base price</th><th>LLPA total</th><th>Margin pts</th><th>Final price</th><th>Final rate</th>" +
    "</tr></thead><tbody>" +
    tbody +
    "</tbody></table></div>";

  eEl.querySelectorAll(".eligible-row").forEach((tr) => {
    const toggleRow = () => {
      const idx = parseInt(tr.dataset.i, 10);
      const r = rowRefs[idx];
      const ledgerTr = eEl.querySelector(`tr[data-ledger="${idx}"]`);
      const panel = ledgerTr?.querySelector(".ledger-panel");
      const afford = tr.querySelector(".details-affordance");
      const wasOpen = ledgerTr && !ledgerTr.classList.contains("hidden");
      eEl.querySelectorAll(".ledger-row").forEach((x) => x.classList.add("hidden"));
      eEl.querySelectorAll(".eligible-row").forEach((x) => {
        x.classList.remove("row-active");
        x.querySelector(".details-affordance")?.classList.remove("open");
      });
      if (wasOpen) return;
      if (ledgerTr && panel && r) {
        ledgerTr.classList.remove("hidden");
        panel.innerHTML = `<h3>Price breakdown · ${r.product_id} · ${r.investor}</h3>${ledgerHtml(r.steps)}`;
        tr.classList.add("row-active");
        afford?.classList.add("open");
        ledgerTr.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    };
    tr.addEventListener("click", toggleRow);
    tr.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        toggleRow();
      }
    });
  });

  const iEl = $("ineligible");
  iEl.classList.toggle("hidden", !ineligible.length);
  iEl.innerHTML =
    "<h2>Ineligible</h2>" +
    `<div class="inelig-groups">${renderIneligibleGroups(ineligible)}</div>`;
}

["filterProduct", "filterInvestor", "filterLock", "filterEligible", "showFullLadder"].forEach(
  (id) => $(id)?.addEventListener("change", () => lastData && renderResults(lastData))
);

$("runBtn").addEventListener("click", async () => {
  const errEl = $("formErr");
  errEl.classList.add("hidden");
  const body = buildPayload();
  const v = clientValidate(body);
  if (v) {
    errEl.textContent = v;
    errEl.classList.remove("hidden");
    return;
  }
  $("runBtn").disabled = true;
  try {
    const res = await fetch("/api/eligibility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      errEl.textContent =
        typeof data.detail === "string"
          ? data.detail
          : JSON.stringify(data.detail || data);
      errEl.classList.remove("hidden");
      return;
    }
    renderResults(data);
  } finally {
    $("runBtn").disabled = false;
  }
});

async function loadScenarios() {
  const res = await fetch("/api/scenarios");
  const data = await res.json();
  const wrap = $("scenarioBtns");
  (data.scenarios || []).forEach((sc) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "ghost";
    b.textContent = sc.name;
    b.addEventListener("click", () => {
      const L = sc.loan;
      $("heloc_amount").value = Number(L.heloc_amount).toLocaleString("en-US");
      $("first_lien_balance").value = Number(L.first_lien_balance).toLocaleString("en-US");
      $("lock_period_days").value = L.lock_period_days ?? "";
      $("product_id").value = L.product_id ?? "";
      $("fico").value = sc.borrower.fico;
      $("dti").value = sc.borrower.dti;
      $("value").value = Number(sc.property.value).toLocaleString("en-US");
      $("occupancy").value = sc.property.occupancy;
      $("property_type").value = sc.property.property_type;
      updateCltv();
    });
    wrap.appendChild(b);
  });
}

loadScenarios();