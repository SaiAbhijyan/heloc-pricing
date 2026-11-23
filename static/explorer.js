mountNav("/explorer");

const bodyEl = document.getElementById("body");
const sel = document.getElementById("scenario");

async function loadScenarios() {
  const res = await fetch("/api/scenarios");
  const data = await res.json();
  (data.scenarios || []).forEach((sc, i) => {
    const o = document.createElement("option");
    o.value = String(i);
    o.textContent = sc.name;
    sel.appendChild(o);
  });
  if (data.scenarios?.length) {
    bodyEl.value = JSON.stringify(
      {
        loan: data.scenarios[0].loan,
        borrower: data.scenarios[0].borrower,
        property: data.scenarios[0].property,
      },
      null,
      2
    );
  }
}

sel.addEventListener("change", async () => {
  const res = await fetch("/api/scenarios");
  const data = await res.json();
  const sc = data.scenarios[parseInt(sel.value, 10)];
  bodyEl.value = JSON.stringify(
    { loan: sc.loan, borrower: sc.borrower, property: sc.property },
    null,
    2
  );
});

document.getElementById("send").addEventListener("click", async () => {
  const t0 = performance.now();
  let payload;
  try {
    payload = JSON.parse(bodyEl.value);
  } catch (e) {
    document.getElementById("response").textContent = "Invalid JSON: " + e.message;
    return;
  }
  const res = await fetch("/api/eligibility", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const ms = (performance.now() - t0).toFixed(0);
  const text = await res.text();
  document.getElementById("timing").textContent = `HTTP ${res.status} in ${ms} ms`;
  try {
    document.getElementById("response").textContent = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    document.getElementById("response").textContent = text;
  }
});

document.getElementById("curl").addEventListener("click", () => {
  const origin = location.origin;
  const esc = bodyEl.value.replace(/'/g, "'\\''");
  const cmd = `curl -s -X POST '${origin}/api/eligibility' -H 'Content-Type: application/json' -d '${esc}'`;
  navigator.clipboard.writeText(cmd);
  document.getElementById("timing").textContent = "curl copied to clipboard";
});

loadScenarios();