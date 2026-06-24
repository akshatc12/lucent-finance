"use strict";

// ---------- helpers ----------
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = async (url, opts) => {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
};
const inr = (n, dec = 0) => "₹" + (Number(n) || 0).toLocaleString("en-IN",
  { minimumFractionDigits: dec, maximumFractionDigits: dec });
const inr2 = n => inr(n, 2);
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("show");
  clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("show"), 2600);
}

const PALETTE = ["#5b8cff", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#06b6d4",
  "#ec4899", "#84cc16", "#fb923c", "#14b8a6", "#f43f5e", "#8b5cf6", "#eab308", "#64748b"];
Chart.defaults.color = "#8b97a7";
Chart.defaults.borderColor = "#262e3b";
Chart.defaults.font.family = "-apple-system,Segoe UI,Roboto,sans-serif";

let META = { all_categories: [], categories: [], banks: [], cards: [], months: [] };
const charts = {};
function draw(id, cfg) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($("#" + id), cfg);
}

// ---------- navigation ----------
$$(".nav-item").forEach(btn => btn.addEventListener("click", () => {
  $$(".nav-item").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const v = btn.dataset.view;
  $$(".view").forEach(s => s.classList.remove("active"));
  $("#view-" + v).classList.add("active");
  if (v === "dashboard") loadDashboard();
  if (v === "ledger") loadLedger();
  if (v === "reconcile") loadReconcile();
  if (v === "import") loadStatements();
}));

// ---------- meta / filters ----------
async function loadMeta() {
  META = await api("/api/filters");
  // sidebar card chips
  $("#cardChips").innerHTML = META.cards.length
    ? META.cards.map(c => `<div class="card-chip"><b>•••• ${c}</b></div>`).join("")
    : `<div class="card-chip">No cards yet</div>`;
  // dashboard selectors
  fill("#dashCard", [["", "All cards"], ...META.cards.map(c => [c, "•••• " + c])]);
  fill("#dashMonth", [["", "All cycles"], ...META.months.map(m => [m, monLabel(m)])]);
  // ledger filters
  fillOpts("#fMonth", "All statement cycles", META.months.map(m => [m, monLabel(m)]));
  fillOpts("#fCategory", "All categories", META.all_categories.map(c => [c, c]));
  fillOpts("#fBank", "All banks", META.banks.map(b => [b, b]));
  fillOpts("#fCard", "All cards", META.cards.map(c => [c, "•••• " + c]));
  populateCatSelects();
}
function fill(sel, pairs) {
  $(sel).innerHTML = pairs.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
}
function fillOpts(sel, first, pairs) {
  $(sel).innerHTML = `<option value="">${first}</option>` +
    pairs.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
}
function monLabel(m) {
  if (!m) return m;
  const [y, mo] = m.split("-");
  return new Date(y, mo - 1, 1).toLocaleString("en-US", { month: "short", year: "numeric" });
}

// ---------- dashboard ----------
$("#dashCard").addEventListener("change", loadDashboard);
$("#dashMonth").addEventListener("change", loadDashboard);

async function loadDashboard() {
  const card = $("#dashCard").value, month = $("#dashMonth").value;
  const qs = new URLSearchParams();
  if (card) qs.set("card", card);
  if (month) qs.set("month", month);
  const stats = await api("/api/stats?" + qs);

  const cycles = stats.cycles;                       // statement-level, by cycle month
  const counts = stats.cycle_counts || {};
  // focus cycle = explicitly selected, else the most recent one
  const focusM = month || (cycles.length ? cycles[cycles.length - 1].month : null);
  const cur = cycles.find(c => c.month === focusM);
  const fIdx = cycles.findIndex(c => c.month === focusM);
  const prev = fIdx > 0 ? cycles[fIdx - 1] : null;
  const mom = (cur && prev && prev.total_due)
    ? ((cur.total_due - prev.total_due) / prev.total_due * 100) : null;
  const cnt = counts[focusM] || { n: 0 };

  const kpis = [
    [`Total payable — ${focusM ? monLabel(focusM) : "—"}`, inr(cur ? cur.total_due : 0),
      mom == null ? "net amount due this cycle" :
        `${mom >= 0 ? "▲" : "▼"} ${Math.abs(mom).toFixed(1)}% vs ${prev ? monLabel(prev.month) : ""}`,
      mom == null ? "" : (mom >= 0 ? "up" : "down")],
    ["New spend this cycle", inr(cur ? cur.purchases : 0), "purchases / debits", ""],
    ["Payments &amp; credits", inr(cur ? cur.payments : 0), "incl. reversals &amp; last bill", ""],
    ["Transactions this cycle", cnt.n || 0,
      cur && cur.previous_balance ? `carried fwd ${inr(cur.previous_balance)}` : "this billing cycle", ""],
  ];
  $("#kpis").innerHTML = kpis.map(([l, v, s, cls]) =>
    `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div>
     <div class="sub ${cls}">${s}</div></div>`).join("");

  // Headline: net amount due per cycle, stacked by card
  drawDue(stats.cycles_by_card, cycles);

  // New spend vs credits by cycle (uses transaction sums per cycle)
  const cmonths = cycles.map(c => c.month);
  draw("chMonthly", {
    type: "bar",
    data: {
      labels: cmonths.map(monLabel),
      datasets: [
        { label: "New spend", data: cmonths.map(m => (counts[m] || {}).debit || 0),
          backgroundColor: "#5b8cff", borderRadius: 5 },
        { label: "Credits/Payments", data: cmonths.map(m => (counts[m] || {}).credit || 0),
          backgroundColor: "#22c55e", borderRadius: 5 },
      ],
    },
    options: baseOpts({ stacked: false }),
  });
  $("#catScope").textContent = focusM ? "· " + monLabel(focusM) : "· all cycles";

  // Category doughnut
  const cat = stats.by_category.filter(c => c.total > 0);
  draw("chCategory", {
    type: "doughnut",
    data: {
      labels: cat.map(c => c.category),
      datasets: [{ data: cat.map(c => c.total), backgroundColor: PALETTE, borderWidth: 0 }],
    },
    options: {
      plugins: { legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => `${c.label}: ${inr(c.raw)}` } } },
      cutout: "58%",
    },
  });

  // Category trend stacked
  drawCatTrend(stats.cat_by_month);

  // By card
  draw("chCard", {
    type: "bar",
    data: {
      labels: stats.by_card.map(c => `${c.bank} •••• ${c.card_last4}`),
      datasets: [{ label: "Spend", data: stats.by_card.map(c => c.spend),
        backgroundColor: stats.by_card.map((_, i) => PALETTE[i % PALETTE.length]), borderRadius: 5 }],
    },
    options: { ...baseOpts({}), indexAxis: "y", plugins: { legend: { display: false },
      tooltip: { callbacks: { label: c => inr(c.raw) } } } },
  });

  // Top merchants
  const merch = stats.by_merchant;
  const max = Math.max(...merch.map(m => m.total), 1);
  $("#topMerchants").innerHTML = merch.length ? merch.map(m => `
    <div class="bar-row">
      <div class="bar-label">${esc(m.merchant)}</div>
      <div class="bar-amt">${inr(m.total)} · ${m.n}×</div>
      <div class="bar-track"><div class="bar-fill" style="width:${m.total / max * 100}%"></div></div>
    </div>`).join("") : `<div class="empty">No data yet</div>`;

  // Domestic vs Intl
  const di = stats.dom_intl;
  draw("chDomIntl", {
    type: "doughnut",
    data: {
      labels: di.map(d => d.section),
      datasets: [{ data: di.map(d => d.total),
        backgroundColor: ["#5b8cff", "#a855f7"], borderWidth: 0 }],
    },
    options: { cutout: "58%", plugins: { legend: { position: "right" },
      tooltip: { callbacks: { label: c => `${c.label}: ${inr(c.raw)}` } } } },
  });
}

function drawDue(byCard, cycles) {
  const months = cycles.map(c => c.month);
  const cards = [...new Set(byCard.map(r => r.card_last4))];
  const cardLabel = {};
  byCard.forEach(r => { cardLabel[r.card_last4] = `${r.bank} •••• ${r.card_last4}`; });
  const key = {};
  byCard.forEach(r => { key[r.month + "|" + r.card_last4] = r.total_due; });
  const datasets = cards.map((cd, i) => ({
    label: cardLabel[cd], data: months.map(m => key[m + "|" + cd] || 0),
    backgroundColor: PALETTE[i % PALETTE.length], borderRadius: 5,
    stack: "due",
  }));
  const totals = months.map(m => cycles.find(c => c.month === m).total_due);
  draw("chDue", {
    type: "bar",
    data: { labels: months.map(monLabel), datasets },
    options: {
      ...baseOpts({ stacked: true }),
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: {
          label: c => `${c.dataset.label}: ${inr(c.raw)}`,
          footer: items => "Total payable: " + inr(totals[items[0].dataIndex]),
        } },
      },
    },
  });
}

function drawCatTrend(rows) {
  const months = [...new Set(rows.map(r => r.month))].sort();
  const cats = [...new Set(rows.map(r => r.category))];
  const byKey = {};
  rows.forEach(r => { byKey[r.month + "|" + r.category] = r.total; });
  const datasets = cats.map((cat, i) => ({
    label: cat, data: months.map(m => byKey[m + "|" + cat] || 0),
    backgroundColor: PALETTE[i % PALETTE.length], borderRadius: 3,
  }));
  draw("chCatTrend", {
    type: "bar",
    data: { labels: months.map(monLabel), datasets },
    options: baseOpts({ stacked: true }),
  });
}

function baseOpts({ stacked }) {
  return {
    responsive: true, maintainAspectRatio: true,
    plugins: { legend: { labels: { boxWidth: 12, font: { size: 11 } } },
      tooltip: { callbacks: { label: c => `${c.dataset.label}: ${inr(c.raw)}` } } },
    scales: {
      x: { stacked: !!stacked, grid: { display: false } },
      y: { stacked: !!stacked, ticks: { callback: v => "₹" + Number(v).toLocaleString("en-IN") } },
    },
  };
}

// ---------- ledger ----------
let ledgerSort = { sort: "txn_date", order: "desc" };
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

["#fMonth", "#fCategory", "#fBank", "#fCard", "#fDirection"].forEach(s =>
  $(s).addEventListener("change", loadLedger));
$("#fSearch").addEventListener("input", debounce(loadLedger));
$("#fClear").addEventListener("click", () => {
  ["#fSearch", "#fMonth", "#fCategory", "#fBank", "#fCard", "#fDirection"].forEach(s => $(s).value = "");
  loadLedger();
});
$$("th.sortable").forEach(th => th.addEventListener("click", () => {
  const col = th.dataset.sort;
  ledgerSort = { sort: col, order: ledgerSort.sort === col && ledgerSort.order === "desc" ? "asc" : "desc" };
  loadLedger();
}));

async function loadLedger() {
  const p = new URLSearchParams();
  const map = { search: "#fSearch", month: "#fMonth", category: "#fCategory",
    bank: "#fBank", card_last4: "#fCard", direction: "#fDirection" };
  for (const [k, sel] of Object.entries(map)) if ($(sel).value) p.set(k, $(sel).value);
  p.set("sort", ledgerSort.sort); p.set("order", ledgerSort.order);
  const { transactions } = await api("/api/transactions?" + p);
  $("#ledgerCount").textContent = `${transactions.length} transactions`;
  $("#bulkCount").textContent = transactions.length;
  $("#bulkApply").disabled = transactions.length === 0;
  const body = $("#ledgerBody");
  if (!transactions.length) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty">No transactions match.</div></td></tr>`;
    return;
  }
  const opts = META.all_categories;
  body.innerHTML = transactions.map(t => {
    const sel = `<select class="cat-select" data-id="${t.id}">` +
      opts.map(c => `<option ${c === t.category ? "selected" : ""}>${c}</option>`).join("") +
      `</select>`;
    const pills =
      (t.section === "International" ? `<span class="pill intl">INTL</span>` : "") +
      (t.is_emi ? `<span class="pill emi">EMI</span>` : "");
    const fx = t.foreign_amount ? `${t.foreign_currency} ${Number(t.foreign_amount).toLocaleString("en-IN")}` : "—";
    const amtCls = t.direction === "credit" ? "amt-credit" : "amt-debit";
    const sign = t.direction === "credit" ? "− " : "";
    return `<tr>
      <td>${t.txn_date}<div class="desc-sub">${t.cycle_month ? monLabel(t.cycle_month) + " bill" : ""}${t.txn_time && t.txn_time !== "00:00" ? " · " + t.txn_time : ""}</div></td>
      <td class="desc-cell"><div class="desc-main">${esc(t.merchant || t.description)}${pills}</div>
        <div class="desc-sub">${esc(t.city ? t.city + " · " : "")}${esc(t.cardholder || "")}${t.ref_no ? " · ref " + esc(String(t.ref_no).slice(0, 14)) : ""}</div></td>
      <td>${t.bank}<div class="desc-sub">•••• ${t.card_last4}</div></td>
      <td>${sel}</td>
      <td><input class="note-input" data-id="${t.id}" value="${esc(t.note || "")}"
            placeholder="add note / tag…" /></td>
      <td class="num">${fx}</td>
      <td class="num ${amtCls}">${sign}${inr2(t.amount)}</td>
    </tr>`;
  }).join("");
  $$(".cat-select", body).forEach(s => s.addEventListener("change", async e => {
    await api(`/api/transactions/${e.target.dataset.id}/category`,
      { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ category: e.target.value }) });
    toast("Category updated");
  }));
  $$(".note-input", body).forEach(inp => {
    const save = async e => {
      if (e.type === "keydown" && e.key !== "Enter") return;
      if (e.target.dataset.saved === e.target.value) return;
      await api(`/api/transactions/${e.target.dataset.id}/note`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ note: e.target.value }) });
      e.target.dataset.saved = e.target.value;
      toast("Note saved");
      if (e.type === "keydown") e.target.blur();
    };
    inp.dataset.saved = inp.value;
    inp.addEventListener("blur", save);
    inp.addEventListener("keydown", save);
  });
}

// bulk tag, new category, export
function populateCatSelects() {
  $("#bulkCat").innerHTML = META.all_categories.map(c => `<option>${esc(c)}</option>`).join("");
}
$("#bulkApply").addEventListener("click", async () => {
  const cat = $("#bulkCat").value;
  const map = { search: "#fSearch", month: "#fMonth", category: "#fCategory",
    bank: "#fBank", card_last4: "#fCard", direction: "#fDirection" };
  const filters = {};
  for (const [k, sel] of Object.entries(map)) if ($(sel).value) filters[k] = $(sel).value;
  const n = +$("#bulkCount").textContent;
  if (!confirm(`Set category to "${cat}" for all ${n} matching transaction(s)?`)) return;
  const r = await api("/api/transactions/bulk-category",
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: cat, filters }) });
  toast(`Updated ${r.updated} transaction(s)`);
  await loadLedger();
});
$("#newCat").addEventListener("click", async () => {
  const name = prompt("New category name (e.g. \"Refunds & Reversals\"):");
  if (!name || !name.trim()) return;
  const r = await api("/api/categories",
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim() }) });
  META.all_categories = r.categories;
  populateCatSelects();
  fillOpts("#fCategory", "All categories", META.all_categories.map(c => [c, c]));
  $("#bulkCat").value = r.added;
  toast(`Added category "${r.added}"`);
  await loadLedger();           // refresh inline dropdowns with the new option
});
$("#exportBtn").addEventListener("click", () => {
  const p = new URLSearchParams();
  const map = { search: "#fSearch", month: "#fMonth", category: "#fCategory",
    bank: "#fBank", card_last4: "#fCard", direction: "#fDirection" };
  for (const [k, sel] of Object.entries(map)) if ($(sel).value) p.set(k, $(sel).value);
  p.set("sort", ledgerSort.sort); p.set("order", ledgerSort.order);
  window.location = "/api/export.xlsx?" + p.toString();
});

// ---------- reconciliation ----------
async function loadReconcile() {
  const { reconciliation } = await api("/api/reconciliation");
  const el = $("#reconCards");
  if (!reconciliation.length) { el.innerHTML = `<div class="empty">Import a statement to reconcile.</div>`; return; }
  el.innerHTML = reconciliation.map(r => {
    const metric = (label, val, diff) => {
      const d = diff == null ? "" :
        `<div class="m-diff ${Math.abs(diff) <= 1 ? "ok" : "bad"}">${diff === 0 ? "✓ exact match" :
          (diff > 0 ? "+" : "") + inr2(diff) + " vs statement"}</div>`;
      return `<div class="recon-metric"><div class="m-label">${label}</div>
        <div class="m-val">${val == null ? "—" : inr2(val)}</div>${d}</div>`;
    };
    return `<div class="recon">
      <div class="recon-top">
        <div class="recon-title">${r.bank} •••• ${r.card_last4}
          <small>${r.card_label || ""} · ${r.statement_date || ""}</small></div>
        <div class="status ${r.status}">${r.status === "balanced" ? "✓ Balanced" : "⚠ Needs review"}</div>
      </div>
      <div class="recon-grid">
        ${metric("Parsed debits", r.parsed_debit, r.debit_diff)}
        ${metric("Statement purchases", r.stmt_purchases, null)}
        ${metric("Parsed credits", r.parsed_credit, r.credit_diff)}
        ${metric("Statement payments/credits", r.stmt_payments_credits, null)}
        ${metric("Previous balance", r.previous_balance, null)}
        ${metric("Total amount due", r.stmt_total_due, null)}
        ${metric("Minimum due", r.stmt_min_due, null)}
        <div class="recon-metric"><div class="m-label">Transactions</div>
          <div class="m-val">${r.txn_count}</div>
          <div class="m-diff">${r.period_start || "?"} → ${r.period_end || "?"}</div></div>
      </div>
    </div>`;
  }).join("");
}

// ---------- import ----------
let pendingFiles = [];
const dz = $("#dropzone"), fileInput = $("#fileInput");
dz.addEventListener("click", () => fileInput.click());
dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("drag"); });
dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
dz.addEventListener("drop", e => {
  e.preventDefault(); dz.classList.remove("drag");
  addFiles([...e.dataTransfer.files]);
});
fileInput.addEventListener("change", () => addFiles([...fileInput.files]));

function addFiles(files) {
  files.filter(f => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"))
    .forEach(f => { if (!pendingFiles.some(p => p.name === f.name && p.size === f.size)) pendingFiles.push(f); });
  renderFileList();
}
function renderFileList() {
  $("#fileList").innerHTML = pendingFiles.map((f, i) =>
    `<div class="file-item"><span>📄 ${esc(f.name)} <span class="muted">(${(f.size / 1024).toFixed(0)} KB)</span></span>
     <span class="rm" data-i="${i}">✕</span></div>`).join("");
  $("#importBtn").disabled = pendingFiles.length === 0;
  $$(".rm", $("#fileList")).forEach(x => x.addEventListener("click", () => {
    pendingFiles.splice(+x.dataset.i, 1); renderFileList();
  }));
}
$("#importBtn").addEventListener("click", async () => {
  if (!pendingFiles.length) return;
  const btn = $("#importBtn"); btn.disabled = true; btn.textContent = "Importing…";
  const fd = new FormData();
  pendingFiles.forEach(f => fd.append("files", f));
  fd.append("password", $("#pw").value);
  try {
    const { results } = await api("/api/import", { method: "POST", body: fd });
    $("#importResults").innerHTML = results.map(r => r.ok
      ? `<div class="res ok">✓ <b>${esc(r.file)}</b> — ${r.bank} •••• ${r.card_last4}: ` +
        (r.already_imported ? "already imported (skipped)" :
          `${r.inserted} imported, ${r.duplicates} duplicates skipped`) + `</div>`
      : `<div class="res err">✕ <b>${esc(r.file)}</b> — ${esc(r.error)}</div>`).join("");
    if (results.some(r => r.ok && !r.already_imported)) {
      pendingFiles = []; renderFileList(); $("#pw").value = "";
      await loadMeta(); await loadStatements();
      toast("Import complete");
    }
  } catch (e) {
    $("#importResults").innerHTML = `<div class="res err">✕ ${esc(e.message)}</div>`;
  } finally { btn.disabled = false; btn.textContent = "Import statements"; }
});

async function loadStatements() {
  const { statements } = await api("/api/statements");
  const body = $("#stmtBody");
  if (!statements.length) {
    body.innerHTML = `<tr><td colspan="7"><div class="empty">No statements imported yet.</div></td></tr>`;
    return;
  }
  body.innerHTML = statements.map(s => `<tr>
    <td>${s.bank}</td>
    <td>${s.card_label || ""}<div class="desc-sub">•••• ${s.card_last4}</div></td>
    <td>${s.statement_date || "—"}</td>
    <td>${s.period_start || "?"} → ${s.period_end || "?"}</td>
    <td class="num">${s.total_due == null ? "—" : inr2(s.total_due)}</td>
    <td><span class="desc-sub">${(s.imported_at || "").replace("T", " ")}</span></td>
    <td><button class="btn danger" data-del="${s.id}">Delete</button></td>
  </tr>`).join("");
  $$("[data-del]", body).forEach(b => b.addEventListener("click", async () => {
    if (!confirm("Delete this statement and its transactions?")) return;
    await api("/api/statements/" + b.dataset.del, { method: "DELETE" });
    await loadMeta(); await loadStatements(); toast("Statement deleted");
  }));
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- boot ----------
(async function init() {
  await loadMeta();
  await loadDashboard();
})();
