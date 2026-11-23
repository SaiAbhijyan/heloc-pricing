mountNav("/");

const $ = (id) => document.getElementById(id);

function updateCltv() {
  const heloc = parseFloat($("heloc_amount").value) || 0;
  const lien = parseFloat($("first_lien_balance").value) || 0;
  const val = parseFloat($("value").value) || 0;
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

function buildPayload() {
  const loan = {
    heloc_amount: parseFloat($("heloc_amount").value),
    first_lien_balance: parseFloat($("first_lien_balance").value),
  };
  const lock = $("lock_period_days").value.trim();
  if (lock) loan.lock_period_days = parseInt(lock, 10);
  const pid = $("product_id").value.trim();
  if (pid) loan.product_id = pid;
  return {
    loan,
    borrower: { fico: parseInt($("fico").value, 10), dti: parseFloat($("dti").value) },
    property: {
      value: parseFloat($("value").value),
      occupancy: $("occupancy").value,
      property_type: $("property_type").value.trim(),
    },
  };
}

function clientValidate(body) {
  if (!(body.loan.heloc_amount > 0)) return "HELOC amount must be greater than 0.";
  if (body.loan.first_lien_balance < 0) return "First lien balance cannot be negative.";
  if (!(body.property.value > 0)) return "Property value must be greater than 0.";
  if (body.borrower.fico < 300 || body.borrower.fico > 850) return "FICO must be 300–850.";
  if (body.borrower.dti < 0 || body.borrower.dti > 100) return "DTI must be 0–100.";
  return "";
}

function breakdown(r) {
  let s = `base price ${r.base_price}\n`;
  for (const ll of r.llpas || []) {
    s += `  + LLPA ${ll.source} | ${ll.row} | ${ll.column}: ${ll.value}\n`;
  }
  s += `  = LLPA total ${r.llpa_total}\n`;
  if (r.margin) {
    const m = r.margin;
    s += `  − margin ($${m.dollar}, ${m.percent}%, ${m.points} pts, row ${m.row})\n`;
  }
  s += `  = final price ${r.final_price} | final rate ${r.final_rate}`;
  return s;
}

function renderResults(data) {
  const eligible = (data.results || []).filter((r) => r.eligible);
  const ineligible = (data.results || []).filter((r) => !r.eligible);
  $("summary").textContent = `${eligible.length} eligible of ${data.results.length} priced`;
  $("summary").classList.remove("hidden");

  const eEl = $("eligible");
  eEl.classList.toggle("hidden", !eligible.length);
  eEl.innerHTML =
    "<h2>Eligible</h2>" +
    eligible
      .map(
        (r) => `<div class="card">
          <strong>${r.product_id}</strong> · ${r.investor} · lock ${r.lock_period_days}d
          <pre class="breakdown">${breakdown(r)}</pre>
        </div>`
      )
      .join("");

  const iEl = $("ineligible");
  iEl.classList.toggle("hidden", !ineligible.length);
  iEl.innerHTML =
    "<h2>Ineligible</h2>" +
    ineligible
      .map(
        (r) => `<div class="card">
          <strong>${r.product_id}</strong> · ${r.investor} · lock ${r.lock_period_days}d
          <ul>${(r.reasons || []).map((x) => `<li>${x}</li>`).join("")}</ul>
        </div>`
      )
      .join("");
}

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
    b.textContent = sc.name.replace(/_/g, " ");
    b.addEventListener("click", () => {
      const L = sc.loan;
      $("heloc_amount").value = L.heloc_amount;
      $("first_lien_balance").value = L.first_lien_balance;
      $("lock_period_days").value = L.lock_period_days ?? "";
      $("product_id").value = L.product_id ?? "";
      $("fico").value = sc.borrower.fico;
      $("dti").value = sc.borrower.dti;
      $("value").value = sc.property.value;
      $("occupancy").value = sc.property.occupancy;
      $("property_type").value = sc.property.property_type;
      updateCltv();
    });
    wrap.appendChild(b);
  });
}

loadScenarios();