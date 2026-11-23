function mountNav(active) {
  const el = document.getElementById("nav");
  if (!el) return;
  const links = [
    ["Eligibility", "/"],
    ["Rate Sheet", "/ratesheet"],
    ["LLPA Grids", "/grids"],
    ["Margins", "/margins"],
    ["API Explorer", "/explorer"],
  ];
  el.innerHTML =
    links
      .map(
        ([t, href]) =>
          `<a href="${href}" class="${active === href ? "active" : ""}">${t}</a>`
      )
      .join("") + '<span class="badge">SYNTHETIC DATA</span>';
}