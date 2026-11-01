const $ = id => document.getElementById(id);
const el = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
const bytes = b => b < 1024 ? b + " B" : b < 1048576 ? (b / 1024).toFixed(1) + " KB" : b < 1073741824 ? (b / 1048576).toFixed(1) + " MB" : (b / 1073741824).toFixed(2) + " GB";
const LABEL = {0: "Manual only", 5: "Every 5 min", 15: "Every 15 min", 60: "Every hour", 1440: "Daily"};
let tt, pending = null;
const toast = m => { const t = $("toast"); t.textContent = m; t.classList.add("show"); clearTimeout(tt); tt = setTimeout(() => t.classList.remove("show"), 3000); };
async function call(url, method = "GET", body) {
  const r = await fetch(url, {method, headers: {"Content-Type": "application/json"}, body: body && JSON.stringify(body)});
  return {ok: r.ok, d: await r.json()};
}

async function loadStats() {
  const s = (await call("/api/stats")).d, box = $("stats"); box.innerHTML = "";
  [[s.files, "Files organised"], [s.runs, "Successful runs"], [bytes(s.bytes), "Data sorted"], [s.folders, "Watched folders"]].forEach(([v, l]) => {
    const d = el("div", "stat"); d.append(el("span", "", v), el("small", "", l)); box.append(d); });
  const c = $("cats"); c.innerHTML = ""; $("noCats").hidden = s.categories.length > 0;
  const max = Math.max(1, ...s.categories.map(x => x.n));
  s.categories.forEach(x => { const r = el("div", "cbar"), t = el("div", "t"), i = el("i"); i.style.width = x.n / max * 100 + "%"; t.append(i); r.append(el("span", "", x.category), t, el("span", "", x.n)); c.append(r); });
}

async function loadFolders() {
  const list = (await call("/api/folders")).d, box = $("folders"); box.innerHTML = ""; $("noFolders").hidden = list.length > 0;
  list.forEach(f => {
    const card = el("div", "folder"), meta = el("div", "fmeta"), acts = el("div", "acts");
    const sel = el("select"); Object.entries(LABEL).forEach(([v, t]) => sel.append(new Option(t, v))); sel.value = f.interval_minutes; sel.setAttribute("aria-label", "Schedule");
    sel.onchange = async () => { await call("/api/folders/" + f.id, "PATCH", {interval_minutes: Number(sel.value)}); toast("Schedule updated"); loadFolders(); };
    const lab = el("label"), cb = el("input"); cb.type = "checkbox"; cb.checked = !!f.enabled; cb.onchange = async () => { await call("/api/folders/" + f.id, "PATCH", {enabled: cb.checked}); toast(cb.checked ? "Automation on" : "Automation paused"); };
    lab.append(cb, document.createTextNode("Auto-run enabled"));
    meta.append(sel, lab, el("span", "", "Last run: " + (f.last_run || "never")));
    const pv = el("button", "", "Preview"), go = el("button", "", "Organise now"), rm = el("button", "", "Remove");
    pv.onclick = () => openPreview(f); go.onclick = async () => { const r = await call(`/api/folders/${f.id}/run`, "POST"); report(r); refresh(); };
    rm.onclick = async () => { if (!confirm("Stop watching this folder? Your files stay untouched.")) return; await call("/api/folders/" + f.id, "DELETE"); loadFolders(); loadStats(); };
    acts.append(pv, go, rm);
    card.append(el("div", "path", f.path), meta, acts); box.append(card);
  });
}
function report(r) {
  if (!r.ok) return toast(r.d.error);
  toast(r.d.moved ? `Organised ${r.d.moved} file${r.d.moved === 1 ? "" : "s"}` + (r.d.errors ? `, ${r.d.errors} skipped` : "") : "Nothing to organise right now");
}

async function openPreview(f) {
  const r = await call(`/api/folders/${f.id}/preview`, "POST"); if (!r.ok) return toast(r.d.error);
  const d = r.d; $("dlgTitle").textContent = "Preview"; $("dlgSub").textContent = f.path; $("chips").innerHTML = ""; $("dlgBody").innerHTML = "";
  Object.entries(d.summary).forEach(([c, n]) => $("chips").append(el("span", "pill", `${c}: ${n}`)));
  d.files.forEach(i => { const tr = el("tr"); tr.append(el("td", "", i.name), el("td", "", "→ " + i.category), el("td", "", bytes(i.size))); $("dlgBody").append(tr); });
  if (!d.total) { const tr = el("tr"), td = el("td", "empty", "Nothing to organise. Recently changed files are skipped for 10 seconds."); tr.append(td); $("dlgBody").append(tr); }
  pending = d.total ? f : null; $("dlgGo").hidden = !d.total; $("dlgGo").textContent = `Organise ${d.total} file${d.total === 1 ? "" : "s"} (${bytes(d.bytes)})`;
  $("dlg").showModal();
}
$("dlgGo").onclick = async () => { if (!pending) return; $("dlg").close(); const r = await call(`/api/folders/${pending.id}/run`, "POST"); report(r); refresh(); };
$("dlgClose").onclick = () => $("dlg").close();

async function loadRuns() {
  const runs = (await call("/api/runs")).d, tb = $("runs"); tb.innerHTML = ""; $("noRuns").hidden = runs.length > 0;
  runs.forEach(r => {
    const tr = el("tr"), cell = (l, ...k) => { const td = el("td"); td.dataset.l = l; td.append(...k); tr.append(td); return td; };
    cell("When", r.started_at); cell("Folder", r.folder_path.split(/[\\/]/).slice(-2).join("/"));
    cell("Trigger", el("span", "pill " + (r.trigger === "auto" ? "auto" : ""), r.trigger)); cell("Files", String(r.moved_count)); cell("Size", bytes(r.bytes));
    cell("Status", el("span", "pill " + r.status, r.status));
    const td = el("td", "none"), a = el("div", "acts"), v = el("button", "", "Details"); v.onclick = () => openRun(r); a.append(v);
    if (r.status === "done") { const u = el("button", "", "Undo"); u.onclick = () => undo(r); a.append(u); }
    td.append(a); tr.append(td); tb.append(tr);
  });
}
async function openRun(r) {
  const m = (await call("/api/runs/" + r.id)).d; $("dlgTitle").textContent = `Run #${r.id}`; $("dlgSub").textContent = `${r.started_at} · ${r.moved_count} files`;
  $("chips").innerHTML = ""; $("dlgBody").innerHTML = ""; $("dlgGo").hidden = true; pending = null;
  m.forEach(x => { const tr = el("tr"); tr.append(el("td", "", x.src.split(/[\\/]/).pop()), el("td", "", "→ " + x.category), el("td", "", bytes(x.size))); $("dlgBody").append(tr); });
  $("dlg").showModal();
}
async function undo(r) {
  if (!confirm(`Move the ${r.moved_count} files from run #${r.id} back to where they were?`)) return;
  const res = await call(`/api/runs/${r.id}/undo`, "POST");
  toast(res.ok ? `Restored ${res.d.restored} file${res.d.restored === 1 ? "" : "s"}` + (res.d.missing ? `, ${res.d.missing} not found` : "") : res.d.error); refresh();
}

$("addForm").addEventListener("submit", async e => {
  e.preventDefault(); const r = await call("/api/folders", "POST", {path: $("path").value, interval_minutes: Number($("interval").value)});
  $("addErr").textContent = r.ok ? "" : r.d.error; if (r.ok) { $("path").value = ""; toast("Folder added"); refresh(); }
});
function refresh() { loadStats(); loadFolders(); loadRuns(); }
refresh(); setInterval(() => { if (!$("dlg").open) refresh(); }, 15000);   // picks up automatic runs
