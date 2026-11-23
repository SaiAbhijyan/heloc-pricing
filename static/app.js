mountNav("/");

const $ = (id) => document.getElementById(id);
let lastData = null;

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

function renderSummaryBar(data) {
  const s = data.summary || {};
  const best = (s.best_by_product || [])
    .map((b) => `${b.product_id}: ${fmtMoney(b.final_price)} pts @ ${b.final_rate}%`)
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

function bestPriceByProduct(rows) {
  const m = {};
  rows.forEach((r) => {
    if (!r.eligible) return;
    if (!(r.product_id in m) || r.final_price > m[r.product_id]) {
      m[r.product_id] = r.final_price;
    }
  });
  return m;
}

function renderResults(data) {
  lastData = data;
  $("resultsPanel").classList.remove("hidden");
  renderSummaryBar(data);
  fillFilterOptions(data);

  const eligible = data.results.filter((r) => r.eligible && passFilters(r));
  const ineligible = data.results.filter((r) => !r.eligible && passFilters(r));
  const best = bestPriceByProduct(data.results.filter((r) => r.eligible));

  $("summary").textContent = `${eligible.length} eligible (filtered)`;
  $("summary").classList.remove("hidden");

  const eEl = $("eligible");
  eEl.classList.toggle("hidden", !eligible.length);
  eEl.innerHTML =
    "<h2>Eligible</h2>" +
    '<div class="table-scroll"><table class="results-table"><thead><tr>' +
    "<th>Product</th><th>Investor</th><th>Lock</th><th>Base rate</th><th>Base price</th><th>LLPA total</th><th>Margin pts</th><th>Final price</th><th>Final rate</th>" +
    "</tr></thead><tbody>" +
    eligible
      .map((r, i) => {
        const hi = best[r.product_id] === r.final_price ? "row-best" : "";
        return `<tr class="eligible-row ${hi}" data-i="${i}" tabindex="0"><td>${r.product_id}</td><td>${r.investor}</td><td>${r.lock_period_days}d</td><td>${fmtMoney(
          r.base_rate
        )}%</td><td>${fmtMoney(r.base_price)}</td><td>${fmtMoney(r.llpa_total)}</td><td>${fmtMoney(
          r.margin?.points
        )}</td><td><strong>${fmtMoney(r.final_price)}</strong></td><td>${fmtMoney(r.final_rate)}%</td></tr>`;
      })
      .join("") +
    "</tbody></table></div>" +
    '<div id="eligibleDetail" class="ledger-panel hidden"></div>';

  eEl.querySelectorAll(".eligible-row").forEach((tr) => {
    tr.addEventListener("click", () => {
      const r = eligible[parseInt(tr.dataset.i, 10)];
      const panel = $("eligibleDetail");
      panel.classList.remove("hidden");
      panel.innerHTML = `<h3>Price breakdown · ${r.product_id}</h3>${ledgerHtml(r.steps)}`;
      eEl.querySelectorAll(".eligible-row").forEach((x) => x.classList.remove("row-active"));
      tr.classList.add("row-active");
    });
  });

  const iEl = $("ineligible");
  iEl.classList.toggle("hidden", !ineligible.length);
  iEl.innerHTML =
    "<h2>Ineligible</h2>" +
    '<div class="table-scroll"><table class="results-table"><thead><tr><th>Product</th><th>Investor</th><th>Lock</th><th>Reasons</th></tr></thead><tbody>' +
    ineligible
      .map(
        (r) =>
          `<tr><td>${r.product_id}</td><td>${r.investor}</td><td>${r.lock_period_days}d</td><td><ul class="reason-list">${(
            r.reasons || []
          )
            .map((x) => `<li>${x}</li>`)
            .join("")}</ul></td></tr>`
      )
      .join("") +
    "</tbody></table></div>";
}

["filterProduct", "filterInvestor", "filterLock", "filterEligible"].forEach((id) =>
  $(id)?.addEventListener("change", () => lastData && renderResults(lastData))
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