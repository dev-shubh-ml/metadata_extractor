

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

from extract import extract_from_file

app = FastAPI(
    title="Rental Agreement Metadata Extractor",
    description="Upload a .docx or .png rental agreement → get structured metadata as JSON.",
    version="1.0.0",
)

ALLOWED_SUFFIXES = {".docx", ".png", ".jpg", ".jpeg"}

UI_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Rental Agreement Extractor</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .drop-active { border-color: #4f46e5 !important; background: #eef2ff; }
    .spin { animation: spin 1s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .fade-in { animation: fadeIn 0.4s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body class="bg-slate-50 min-h-screen font-sans">

  <!-- Header -->
  <div class="bg-gradient-to-r from-indigo-600 to-blue-500 shadow-lg">
    <div class="max-w-2xl mx-auto px-6 py-5">
      <h1 class="text-2xl font-bold text-white tracking-tight">Rental Agreement Extractor</h1>
      <p class="text-indigo-200 text-sm mt-1">AI-powered metadata extraction &mdash; powered by Google Gemini</p>
    </div>
  </div>

  <!-- Main -->
  <div class="max-w-2xl mx-auto px-6 py-8 space-y-6">

    <!-- Upload card -->
    <div class="bg-white rounded-2xl shadow-sm p-6">
      <h2 class="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-4">Upload Document</h2>

      <!-- Drop zone -->
      <div id="dropZone"
           class="border-2 border-dashed border-slate-200 rounded-xl p-10 text-center cursor-pointer transition-all hover:border-indigo-400 hover:bg-indigo-50"
           onclick="document.getElementById('fileInput').click()">
        <div class="text-5xl mb-3">📄</div>
        <p class="text-slate-600 font-medium">Drop your file here or <span class="text-indigo-600 underline">browse</span></p>
        <p class="text-slate-400 text-sm mt-1">Supports <strong>.docx</strong> and <strong>.png / .jpg</strong> files</p>
        <input type="file" id="fileInput" class="hidden" accept=".docx,.png,.jpg,.jpeg,.pdf.docx" />
      </div>

      <!-- Selected file pill -->
      <div id="filePill" class="hidden mt-4 flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-lg px-4 py-3">
        <span id="fileIcon" class="text-2xl">📄</span>
        <div class="flex-1 min-w-0">
          <p id="fileName" class="text-sm font-medium text-slate-700 truncate"></p>
          <p id="fileSize" class="text-xs text-slate-400"></p>
        </div>
        <button onclick="clearFile()" class="text-slate-400 hover:text-red-400 text-lg leading-none">&times;</button>
      </div>

      <!-- Extract button -->
      <button id="extractBtn"
              onclick="doExtract()"
              class="hidden mt-4 w-full bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold py-3 rounded-xl transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
        Extract Metadata
      </button>
    </div>

    <!-- Loading -->
    <div id="loading" class="hidden bg-white rounded-2xl shadow-sm p-8 text-center">
      <div class="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full spin mx-auto"></div>
      <p class="text-slate-500 mt-4 font-medium">Analyzing document with Gemini AI&hellip;</p>
      <p class="text-slate-400 text-sm mt-1">This takes about 3–5 seconds</p>
    </div>

    <!-- Error -->
    <div id="errorBox" class="hidden fade-in bg-red-50 border border-red-200 rounded-2xl p-5">
      <p class="text-red-600 font-semibold">Extraction failed</p>
      <p id="errorMsg" class="text-red-500 text-sm mt-1"></p>
    </div>

    <!-- Results -->
    <div id="results" class="hidden fade-in bg-white rounded-2xl shadow-sm p-6">
      <div class="flex items-center justify-between mb-5">
        <h2 class="text-sm font-semibold text-slate-500 uppercase tracking-wider">Extracted Metadata</h2>
        <span class="text-xs bg-green-100 text-green-700 font-semibold px-3 py-1 rounded-full">✓ Success</span>
      </div>

      <div class="grid grid-cols-2 gap-4" id="resultGrid"></div>

      <!-- Raw JSON toggle -->
      <details class="mt-5">
        <summary class="text-xs text-slate-400 cursor-pointer hover:text-slate-600 select-none">View raw JSON</summary>
        <pre id="rawJson" class="mt-2 bg-slate-50 rounded-lg p-4 text-xs text-slate-600 overflow-auto"></pre>
      </details>
    </div>

  </div>

  <script>
    const FIELD_META = {
      "Aggrement Value":        { label: "Agreement Value",      icon: "💰", format: v => v != null ? "₹ " + Number(v).toLocaleString("en-IN") : "—" },
      "Aggrement Start Date":   { label: "Start Date",           icon: "📅", format: v => v || "—" },
      "Aggrement End Date":     { label: "End Date",             icon: "📅", format: v => v || "—" },
      "Renewal Notice (Days)":  { label: "Renewal Notice",       icon: "🔔", format: v => v != null ? v + " days" : "Not mentioned" },
      "Party One":              { label: "Party One (Landlord)", icon: "🏠", format: v => v || "—" },
      "Party Two":              { label: "Party Two (Tenant)",   icon: "🧑", format: v => v || "—" },
    };

    let selectedFile = null;

    // Drag & drop
    const dropZone = document.getElementById("dropZone");
    dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("drop-active"); });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drop-active"));
    dropZone.addEventListener("drop", e => {
      e.preventDefault();
      dropZone.classList.remove("drop-active");
      if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
    });

    document.getElementById("fileInput").addEventListener("change", e => {
      if (e.target.files[0]) setFile(e.target.files[0]);
    });

    function setFile(file) {
      selectedFile = file;
      const isPng = file.name.toLowerCase().endsWith(".png") || file.name.toLowerCase().endsWith(".jpg");
      document.getElementById("fileIcon").textContent = isPng ? "🖼️" : "📝";
      document.getElementById("fileName").textContent = file.name;
      document.getElementById("fileSize").textContent = (file.size / 1024).toFixed(1) + " KB";
      document.getElementById("filePill").classList.remove("hidden");
      document.getElementById("extractBtn").classList.remove("hidden");
      hide("results"); hide("errorBox"); hide("loading");
    }

    function clearFile() {
      selectedFile = null;
      document.getElementById("fileInput").value = "";
      document.getElementById("filePill").classList.add("hidden");
      document.getElementById("extractBtn").classList.add("hidden");
      hide("results"); hide("errorBox");
    }

    async function doExtract() {
      if (!selectedFile) return;
      hide("results"); hide("errorBox");
      show("loading");
      document.getElementById("extractBtn").disabled = true;

      const form = new FormData();
      form.append("file", selectedFile);

      try {
        const res = await fetch("/extract", { method: "POST", body: form });
        const data = await res.json();
        hide("loading");
        if (!res.ok) {
          document.getElementById("errorMsg").textContent = data.detail || "Unknown error";
          show("errorBox");
        } else {
          renderResults(data);
          show("results");
        }
      } catch (err) {
        hide("loading");
        document.getElementById("errorMsg").textContent = err.message;
        show("errorBox");
      } finally {
        document.getElementById("extractBtn").disabled = false;
      }
    }

    function renderResults(data) {
      const grid = document.getElementById("resultGrid");
      grid.innerHTML = "";
      for (const [key, meta] of Object.entries(FIELD_META)) {
        const val = data[key];
        const card = document.createElement("div");
        card.className = "bg-slate-50 rounded-xl p-4 border border-slate-100";
        card.innerHTML = `
          <div class="flex items-center gap-2 mb-1">
            <span class="text-lg">${meta.icon}</span>
            <span class="text-xs font-semibold text-slate-400 uppercase tracking-wide">${meta.label}</span>
          </div>
          <p class="text-slate-800 font-semibold text-sm leading-snug">${meta.format(val)}</p>
        `;
        grid.appendChild(card);
      }
      document.getElementById("rawJson").textContent = JSON.stringify(data, null, 2);
    }

    function show(id) { document.getElementById(id).classList.remove("hidden"); }
    function hide(id) { document.getElementById(id).classList.add("hidden"); }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def ui():
    return UI_HTML


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Upload a rental agreement (.docx or .png/.jpg). Returns extracted metadata as JSON."""
    filename = file.filename or ""
    name_lower = filename.lower()
    suffix = Path(filename).suffix.lower()

    is_pdf_docx = name_lower.endswith(".pdf.docx")
    if suffix not in ALLOWED_SUFFIXES and not is_pdf_docx:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    effective_suffix = ".docx" if is_pdf_docx else suffix
    with tempfile.NamedTemporaryFile(suffix=effective_suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        metadata = extract_from_file(tmp_path)
        return JSONResponse(content=metadata)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        tmp_path.unlink(missing_ok=True)
