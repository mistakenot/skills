/* evals view — the page over one run directory.
 *
 * Vanilla JS, no build step. The server is the source of truth for
 * everything shown here (the run description, file bytes, diffs); this file
 * only arranges it. Comments are the one thing the page writes, and they go
 * to the server on every change with localStorage as a fallback mirror.
 */
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);
  const el = (tag, attrs, children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (v !== null && v !== undefined) node.setAttribute(k, v);
    }
    for (const c of children || []) node.append(c);
    return node;
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const human = (n) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`);
  const cellKey = (c) => `${c.arm}/${c.trial}`;

  const state = {
    runId: null,
    run: null,       // the /api/runs/<id> payload
    tab: "outputs",
    activeCell: null, // "<arm>/<trial>"
    fileByCell: {},   // cellKey -> selected file rel (run-relative) or "out.md"
    comments: [],
    skillDiffCache: {},
  };

  async function api(path, opts) {
    const r = await fetch(path, opts);
    let data = null;
    try { data = await r.json(); } catch (_) { /* not JSON */ }
    if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
    return data;
  }
  const fileUrl = (rel) => `/api/runs/${encodeURIComponent(state.runId)}/file?path=${encodeURIComponent(rel)}`;

  function showError(msg) {
    const box = $("#error");
    box.textContent = msg;
    box.hidden = !msg;
  }

  // ------------------------------------------------------------- run list
  async function renderRunList() {
    const runs = await api("/api/runs");
    const box = $("#run-list");
    box.hidden = false;
    $("#run-view").hidden = true;
    $("#run-meta").innerHTML = `<span>${runs.length} run(s)</span>`;
    if (!runs.length) {
      box.append(el("p", { text: "No runs yet. Run `make evals ARGS='run ...'` first." }));
      return;
    }
    const table = el("table");
    table.append(el("thead", { html: "<tr><th>run</th><th>skill</th><th>arms</th><th>trials</th><th>scenario</th><th>started</th><th>status</th></tr>" }));
    const tbody = el("tbody");
    for (const r of runs) {
      const tr = el("tr");
      tr.append(el("td", {}, [el("a", { href: `/run/${encodeURIComponent(r.id)}`, class: "mono", text: r.id })]));
      tr.append(el("td", { text: r.skill || "?" }));
      tr.append(el("td", { text: (r.arms || []).join(", ") || "-" }));
      tr.append(el("td", { text: String(r.trials || 1) }));
      tr.append(el("td", { text: r.scenario || "(inline prompt)" }));
      tr.append(el("td", { text: r.started_at || "" }));
      tr.append(el("td", { text: r.status === "ok" ? "" : r.status }));
      tbody.append(tr);
    }
    table.append(tbody);
    box.append(table);
  }

  // ------------------------------------------------------------- header
  function renderHeader() {
    const run = state.run.run;
    const arms = state.run.arms.map((a) => {
      let prov = a.kind || "?";
      if (a.sha && a.kind !== "none") prov += ` ${a.sha === "WORKTREE" ? "worktree" : a.sha.slice(0, 8)}`;
      if (a.head) prov += ` @${a.head.slice(0, 8)}${a.dirty ? " dirty" : ""}`;
      const inv = a.invocation ? (a.invocation.invoked ? "invoked" : "NOT INVOKED") : "";
      return `<span class="arm"><b>${esc(a.name)}</b> ${esc(prov)}${inv ? " · " + esc(inv) : ""}</span>`;
    }).join(" ");
    const report = run.report ? `<a href="${fileUrl("REPORT.md")}" target="_blank">REPORT.md</a>` : "";
    $("#run-meta").innerHTML = [
      `<span class="mono"><b>${esc(run.id)}</b>${run.status !== "ok" ? " [" + esc(run.status) + "]" : ""}</span>`,
      `<span>skill <b>${esc(run.skill || "?")}</b>${run.with && run.with.length ? " with " + esc(run.with.join(", ")) : ""}</span>`,
      arms,
      `<span>trials <b>${esc(run.trials)}</b></span>`,
      `<span>scenario <b>${esc(run.scenario || "(inline prompt)")}</b></span>`,
      run.runner === "stub" ? `<span class="bad">stub run — canned transcript</span>` : "",
      report,
    ].filter(Boolean).join("");
    document.title = `evals ${run.id}`;
  }

  // ------------------------------------------------------------- tabs
  function setTab(name) {
    state.tab = name;
    for (const b of document.querySelectorAll("#tabs button")) b.classList.toggle("active", b.dataset.tab === name);
    for (const s of document.querySelectorAll(".tab")) s.hidden = s.id !== `tab-${name}`;
    if (name === "diffs" && !$("#diff-body").childElementCount) renderDiffs();
    if (name === "transcript" && !$("#tab-transcript").childElementCount) renderTranscript();
  }

  // ------------------------------------------------------------- outputs
  function cellFiles(cell) {
    const files = cell.outputs.map((o) => ({ label: `${o.ws_rel} (${human(o.size)})`, rel: o.rel, type: o.type, binary: o.binary, size: o.size }));
    if (cell.out_md.present) files.push({ label: `final message (out.md, ${human(cell.out_md.size)})`, rel: `${cell.dir}/out.md`, type: "Markdown", binary: false, size: cell.out_md.size });
    if (cell.err_txt.present && cell.err_txt.size) files.push({ label: `stderr (err.txt, ${human(cell.err_txt.size)})`, rel: `${cell.dir}/err.txt`, type: "plain text", binary: false, size: cell.err_txt.size });
    return files;
  }

  function renderOutputs() {
    const box = $("#tab-outputs");
    box.innerHTML = "";
    if (!state.run.cells.length) {
      box.append(el("div", { class: "note", text: "This run has no cells." }));
      return;
    }
    for (const cell of state.run.cells) {
      const key = cellKey(cell);
      const files = cellFiles(cell);
      if (!(key in state.fileByCell)) state.fileByCell[key] = files.length ? files[0].rel : null;

      const col = el("div", { class: "cell-col" + (state.activeCell === key ? " active" : ""), "data-cell": key });
      col.addEventListener("mousedown", () => setActiveCell(key));

      const facts = el("div", { class: "facts" });
      const invoked = cell.invoked === null || cell.invoked === undefined ? "not analysed" : cell.invoked ? "yes" : (cell.skill_installed ? "NO" : "no (nothing installed)");
      facts.append(el("span", { class: cell.invoked ? "ok" : cell.skill_installed && cell.invoked === false ? "bad" : "", text: `invoked: ${invoked}` }));
      facts.append(el("span", { class: cell.exit_code === 0 ? "" : "bad", text: `exit: ${cell.exit_code === null ? "—" : cell.exit_code}` }));
      if (cell.cost) {
        const c = cell.cost;
        const bits = [];
        if (typeof c.total_cost_usd === "number") bits.push(`$${c.total_cost_usd.toFixed(2)}`);
        if (typeof c.duration_ms === "number") bits.push(`${(c.duration_ms / 60000).toFixed(1)} min`);
        if (typeof c.num_turns === "number") bits.push(`${c.num_turns} turns`);
        if (bits.length) facts.append(el("span", { text: bits.join(" · ") }));
      }
      facts.append(el("span", { text: `${cell.tool_calls} tool calls` }));

      const select = el("select");
      for (const f of files) select.append(el("option", { value: f.rel, text: f.label }));
      if (!files.length) select.append(el("option", { value: "", text: cell.outputs_diffed ? "(no file new or changed against the seed)" : "(no file at ws/ root)" }));
      select.value = state.fileByCell[key] || "";
      select.addEventListener("change", () => { state.fileByCell[key] = select.value; renderCellBody(cell, body, pathLine); });

      const pathLine = el("div", { class: "path mono" });
      const head = el("div", { class: "cell-head" }, [
        el("div", { class: "title", text: `${cell.arm} · trial ${cell.trial}` }),
        facts, select, pathLine,
      ]);
      const body = el("div", { class: "cell-body" });
      col.append(head, body);
      box.append(col);
      renderCellBody(cell, body, pathLine);
    }
  }

  async function renderCellBody(cell, body, pathLine) {
    const key = cellKey(cell);
    const rel = state.fileByCell[key];
    const file = cellFiles(cell).find((f) => f.rel === rel);
    body.innerHTML = "";
    if (!file) { pathLine.textContent = ""; body.append(el("div", { class: "note", text: "Nothing to show." })); return; }
    pathLine.textContent = `${file.rel} · ${human(file.size)}`;
    if (file.binary) { body.append(el("div", { class: "note", text: "binary, not shown" })); return; }
    if (file.type === "HTML") {
      body.append(el("iframe", { sandbox: "allow-scripts", src: fileUrl(file.rel), title: file.rel }));
      return;
    }
    try {
      const r = await fetch(fileUrl(file.rel));
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const text = await r.text();
      if (file.type === "Markdown" && window.marked) {
        body.append(el("div", { class: "md", html: marked.parse(text) }));
      } else {
        body.append(el("pre", { text }));
      }
    } catch (e) {
      body.append(el("div", { class: "note", text: `could not load: ${e.message}` }));
    }
  }

  function setActiveCell(key) {
    state.activeCell = key;
    for (const c of document.querySelectorAll(".cell-col")) c.classList.toggle("active", c.dataset.cell === key);
  }

  // ------------------------------------------------------------- diffs
  function diffHtml(diff) {
    if (!diff) return "<div class='note'>identical</div>";
    if (!window.Diff2Html) return `<pre class="mono">${esc(diff)}</pre>`;
    return Diff2Html.getPrettyHtml(diff, { inputFormat: "diff", outputFormat: "side-by-side", showFiles: false, matching: "lines" });
  }

  function fillArmSelects() {
    const names = state.run.arms.map((a) => a.name);
    for (const [id, i] of [["#skill-a", 0], ["#skill-b", Math.min(1, names.length - 1)]]) {
      const s = $(id); s.innerHTML = "";
      for (const n of names) s.append(el("option", { value: n, text: n }));
      s.value = names[i] || "";
      s.addEventListener("change", renderSkillDiff);
    }
    const keys = state.run.cells.map(cellKey);
    for (const [id, i] of [["#out-a", 0], ["#out-b", Math.min(1, keys.length - 1)]]) {
      const s = $(id); s.innerHTML = "";
      for (const k of keys) s.append(el("option", { value: k, text: k }));
      s.value = keys[i] || "";
      s.addEventListener("change", () => { $("#out-file").value = ""; renderOutputDiff(); });
    }
    $("#out-go").addEventListener("click", renderOutputDiff);
    $("#out-file").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); renderOutputDiff(); } });
    for (const r of document.querySelectorAll("input[name=diff-mode]")) r.addEventListener("change", renderDiffs);
  }

  function diffMode() { return $("input[name=diff-mode]:checked").value; }

  function renderDiffs() {
    const mode = diffMode();
    $("#diff-skill-controls").hidden = mode !== "skill";
    $("#diff-output-controls").hidden = mode !== "output";
    if (mode === "skill") renderSkillDiff(); else renderOutputDiff();
  }

  async function renderSkillDiff() {
    const a = $("#skill-a").value, b = $("#skill-b").value;
    const box = $("#diff-body");
    box.innerHTML = "<div class='note'>loading…</div>";
    try {
      const key = `${a}|${b}`;
      const data = state.skillDiffCache[key] || (state.skillDiffCache[key] = await api(`/api/runs/${encodeURIComponent(state.runId)}/skill-diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`));
      box.innerHTML = "";
      const changed = data.files.filter((f) => f.status !== "same").length;
      box.append(el("div", { class: "note", text: `${data.files.length} file(s) in the installed trees of ${a} and ${b}; ${changed} differ.` + (data.files.length ? "" : " (Neither arm installed anything.)") }));
      for (const f of data.files) {
        const det = el("details", { open: f.status !== "same" ? "" : null });
        det.append(el("summary", { html: `<span class="status ${esc(f.status)}">${esc(f.status)}</span> <span class="mono">${esc(f.path)}</span>${f.binary ? " (binary)" : ""}` }));
        const inner = el("div", { class: "diff-inner" });
        det.append(inner);
        const draw = () => { if (!inner.childElementCount) inner.innerHTML = f.binary ? "<div class='note'>binary — not diffed</div>" : diffHtml(f.diff); };
        det.addEventListener("toggle", () => { if (det.open) draw(); });
        if (det.open) draw();
        box.append(det);
      }
    } catch (e) {
      box.innerHTML = `<div class="error">${esc(e.message)}</div>`;
    }
  }

  async function renderOutputDiff() {
    const a = $("#out-a").value, b = $("#out-b").value, file = $("#out-file").value.trim();
    const box = $("#diff-body");
    box.innerHTML = "<div class='note'>loading…</div>";
    try {
      let url = `/api/runs/${encodeURIComponent(state.runId)}/output-diff?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`;
      if (file) url += `&file=${encodeURIComponent(file)}`;
      const data = await api(url);
      if (!file) $("#out-file").placeholder = data.a.file === data.b.file ? data.a.file : `${data.a.file} vs ${data.b.file}`;
      box.innerHTML = "";
      box.append(el("div", { class: "note mono", text: `${data.a.cell}/ws/${data.a.file}  ↔  ${data.b.cell}/ws/${data.b.file}` }));
      if (data.note) box.append(el("div", { class: "note", text: data.note }));
      box.append(el("div", { class: "diff-inner", html: data.identical ? "<div class='note'>identical</div>" : diffHtml(data.diff) }));
    } catch (e) {
      box.innerHTML = `<div class="error">${esc(e.message)}</div>`;
    }
  }

  // ------------------------------------------------------------- transcript
  async function renderTranscript() {
    const box = $("#tab-transcript");
    box.innerHTML = "";
    for (const cell of state.run.cells) {
      const col = el("div", { class: "tr-col" });
      col.append(el("h3", { text: `${cell.arm} · trial ${cell.trial} — ${cell.tool_calls} tool calls` }));
      const list = el("ol");
      col.append(list);
      box.append(col);
      try {
        const data = await api(`/api/runs/${encodeURIComponent(state.runId)}/transcript?cell=${encodeURIComponent(cellKey(cell))}`);
        for (const t of data.calls) {
          list.append(el("li", { html: `<span class="tool">${esc(t.name)}</span><span class="arg mono">${esc(t.summary)}</span>` }));
        }
        if (!data.calls.length) list.append(el("li", { text: "(no tool calls)" }));
      } catch (e) {
        list.append(el("li", { class: "error", text: e.message }));
      }
    }
  }

  // ------------------------------------------------------------- comments
  const storageKey = () => `evals-comments-${state.runId}`;

  function mirror() {
    try { localStorage.setItem(storageKey(), JSON.stringify(state.comments)); } catch (_) { /* fine */ }
  }

  async function loadComments() {
    try {
      state.comments = await api(`/api/runs/${encodeURIComponent(state.runId)}/comments`);
      $("#comment-status").textContent = `${state.comments.length} comment(s) · stored in ${state.runId}/comments.json`;
      mirror();
    } catch (e) {
      try { state.comments = JSON.parse(localStorage.getItem(storageKey()) || "[]"); } catch (_) { state.comments = []; }
      $("#comment-status").textContent = `server unavailable (${e.message}); showing the browser's copy`;
    }
    renderComments();
  }

  async function saveComments() {
    mirror();
    try {
      await api(`/api/runs/${encodeURIComponent(state.runId)}/comments`, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state.comments),
      });
      $("#comment-status").textContent = `${state.comments.length} comment(s) · saved to ${state.runId}/comments.json`;
    } catch (e) {
      $("#comment-status").textContent = `save failed (${e.message}); kept in this browser only`;
    }
    renderComments();
  }

  function currentContext() {
    const cell = state.activeCell ? state.run.cells.find((c) => cellKey(c) === state.activeCell) : null;
    let file = "";
    if (state.tab === "outputs" && cell) {
      const f = cellFiles(cell).find((x) => x.rel === state.fileByCell[cellKey(cell)]);
      file = f ? f.rel : "";
    } else if (state.tab === "diffs") {
      file = diffMode() === "skill" ? `skill-diff ${$("#skill-a").value} vs ${$("#skill-b").value}` : `output-diff ${$("#out-a").value} vs ${$("#out-b").value}${$("#out-file").value ? " " + $("#out-file").value : ""}`;
    } else if (state.tab === "transcript" && cell) {
      file = `${cell.dir}/stream.jsonl`;
    }
    const sel = window.getSelection ? String(window.getSelection()).trim() : "";
    return {
      tab: state.tab,
      arm: cell ? cell.arm : "",
      trial: cell ? String(cell.trial) : "",
      file,
      quote: sel.length > 1000 ? sel.slice(0, 1000) + "…" : sel,
    };
  }

  function openForm() {
    const ctx = currentContext();
    const form = $("#comment-form");
    form.dataset.ctx = JSON.stringify(ctx);
    $("#comment-context").textContent = [ctx.tab, ctx.arm && `${ctx.arm}/${ctx.trial}`, ctx.file].filter(Boolean).join(" · ") || "(no context)";
    $("#comment-quote").value = ctx.quote;
    $("#comment-text").value = "";
    form.hidden = false;
    $("#comment-text").focus();
  }

  function renderComments() {
    const list = $("#comment-list");
    list.innerHTML = "";
    state.comments.forEach((c, i) => {
      const li = el("li");
      li.append(el("button", { class: "del", type: "button", title: "delete", text: "×", onclick: async () => { state.comments.splice(i, 1); await saveComments(); } }));
      li.append(el("div", { class: "where", text: [c.tab, c.arm && `${c.arm}/${c.trial}`, c.file].filter(Boolean).join(" · ") }));
      if (c.quote) li.append(el("div", { class: "quote", text: c.quote }));
      li.append(el("div", { class: "text", text: c.text }));
      list.append(li);
    });
  }

  function copyBlock() {
    const run = state.run.run;
    const lines = [`=== EVAL COMMENTS run ${run.id} (skill ${run.skill || "?"}) ===`];
    state.comments.forEach((c, i) => {
      const where = [c.arm && `${c.arm}/${c.trial}`, c.file].filter(Boolean).join(" · ") || c.tab || "";
      lines.push(`[${i + 1}] ${where}`);
      if (c.quote) lines.push(`    > "${c.quote.replace(/\s*\n\s*/g, " ")}"`);
      for (const l of String(c.text).split("\n")) lines.push(`    ${l}`);
    });
    lines.push("=== END EVAL COMMENTS ===");
    return lines.join("\n") + "\n";
  }

  function wireComments() {
    $("#toggle-comments").addEventListener("click", () => $("#comments").classList.toggle("collapsed"));
    $("#comment-add").addEventListener("click", () => { $("#comments").classList.remove("collapsed"); openForm(); });
    $("#comment-cancel").addEventListener("click", () => { $("#comment-form").hidden = true; });
    $("#comment-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const ctx = JSON.parse($("#comment-form").dataset.ctx || "{}");
      const text = $("#comment-text").value.trim();
      if (!text) return;
      state.comments.push({
        id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
        created_at: new Date().toISOString(),
        tab: ctx.tab || "", arm: ctx.arm || "", trial: ctx.trial || "", file: ctx.file || "",
        quote: $("#comment-quote").value.trim(), text,
      });
      $("#comment-form").hidden = true;
      await saveComments();
    });
    $("#comment-copy").addEventListener("click", async () => {
      const block = copyBlock();
      try {
        await navigator.clipboard.writeText(block);
        $("#comment-status").textContent = "copied to clipboard";
      } catch (_) {
        // Clipboard needs a secure context; over plain http on another
        // machine it is unavailable, so fall back to a prompt to copy from.
        window.prompt("Copy the block below:", block);
      }
    });
    $("#comment-clear").addEventListener("click", async () => {
      if (!state.comments.length || !window.confirm(`Delete all ${state.comments.length} comment(s) on ${state.runId}?`)) return;
      state.comments = [];
      await saveComments();
    });
  }

  // ------------------------------------------------------------- boot
  async function boot() {
    const m = location.pathname.match(/^\/run\/([^/]+)\/?$/);
    wireComments();
    try {
      if (!m) { await renderRunList(); return; }
      state.runId = decodeURIComponent(m[1]);
      state.run = await api(`/api/runs/${encodeURIComponent(state.runId)}`);
      $("#run-view").hidden = false;
      renderHeader();
      state.activeCell = state.run.cells.length ? cellKey(state.run.cells[0]) : null;
      renderOutputs();
      fillArmSelects();
      for (const b of document.querySelectorAll("#tabs button")) b.addEventListener("click", () => setTab(b.dataset.tab));
      $("#comments").classList.remove("collapsed");
      await loadComments();
    } catch (e) {
      showError(e.message);
    }
  }

  boot();
})();
