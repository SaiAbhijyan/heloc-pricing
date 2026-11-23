function metaLine(meta) {
  if (!meta || !meta.uploaded_at) return "No data stored yet.";
  return `Last upload: ${meta.file_name || "—"} at ${meta.uploaded_at}`;
}

async function uploadFile(component, file, preview) {
  const fd = new FormData();
  fd.append("file", file);
  const url = `/api/admin/${component}${preview ? "?preview=true" : ""}`;
  return fetch(url, { method: "POST", body: fd });
}

function wireUpload(component, onPreview, onSaved) {
  const input = document.getElementById("fileInput");
  const zone = document.getElementById("dropZone");
  const errEl = document.getElementById("uploadErr");
  const previewEl = document.getElementById("previewBox");

  async function handle(file) {
    errEl.classList.add("hidden");
    previewEl.innerHTML = "";
    const r = await uploadFile(component, file, true);
    const data = await r.json();
    if (!data.ok) {
      errEl.textContent = (data.errors || [data.detail]).join("; ");
      errEl.classList.remove("hidden");
      return;
    }
    previewEl.innerHTML = `<p class="ok">Parsed ${(data.rows?.length ?? data.rows?.rows?.length ?? "?")} row(s). Review then Save.</p>`;
    onPreview(data, file);
  }

  input.addEventListener("change", () => {
    if (input.files[0]) handle(input.files[0]);
  });
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
    if (e.dataTransfer.files[0]) handle(e.dataTransfer.files[0]);
  });

  document.getElementById("saveUpload").addEventListener("click", async () => {
    const pending = window.__pendingUpload;
    if (!pending) return;
    const r = await uploadFile(component, pending.file, false);
    const data = await r.json();
    if (!data.ok) {
      errEl.textContent = JSON.stringify(data);
      errEl.classList.remove("hidden");
      return;
    }
    window.__pendingUpload = null;
    previewEl.innerHTML = "";
    onSaved(data);
  });
}

function pending(file) {
  window.__pendingUpload = { file };
}