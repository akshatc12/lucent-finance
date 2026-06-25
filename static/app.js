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

function hexToRgb(h) {
  const m = h.replace("#", "");
  return { r: parseInt(m.slice(0, 2), 16), g: parseInt(m.slice(2, 4), 16), b: parseInt(m.slice(4, 6), 16) };
}
// progressively lighten a base colour for nested (subcategory) ring slices
function shade(hex, i, n) {
  const f = n <= 1 ? 0 : Math.min(0.62, 0.1 + 0.55 * (i / n));
  const c = hexToRgb(hex), mix = v => Math.round(v + (255 - v) * f);
  return `rgb(${mix(c.r)},${mix(c.g)},${mix(c.b)})`;
}

// Make a bar chart that lives in a .chart-scroll wrapper widen with its data so
// stacks stay readable as billing cycles accumulate (scrolls when it overflows).
function sizeScroll(canvasId, count, per = 78) {
  const inner = $("#" + canvasId).parentElement, box = inner.parentElement;
  const avail = box.clientWidth || 600;
  inner.style.width = Math.max(count * per, avail) + "px";
}

// ---------- reusable dropdown: multi-select + searchable/creatable combobox ----------
let _openDD = null;
document.addEventListener("click", e => {
  if (_openDD && !_openDD.el.contains(e.target) && !_openDD.panel.contains(e.target)) _openDD.close();
});
// panels are position:fixed, so close on scroll to avoid a stale position
window.addEventListener("scroll", () => { if (_openDD) _openDD.close(); }, true);
class Dropdown {
  constructor(el, opts = {}) {
    this.el = typeof el === "string" ? $(el) : el;
    this.o = Object.assign({ multi: false, searchable: false, creatable: false,
      placeholder: "Select…", allLabel: "All", emptyText: "No matches" }, opts);
    this.items = [];
    this.sel = this.o.multi ? new Set() : "";
    this.el.classList.add("dd");
    if (!this.o.multi) this.el.classList.add("dd-single");
    this.el.innerHTML = `<button type="button" class="dd-btn"><span class="dd-label"></span><span class="dd-caret">▾</span></button>`;
    this.btn = $(".dd-btn", this.el);
    this.panel = null;
    this.btn.addEventListener("click", e => { e.stopPropagation(); this.toggle(); });
    this._label();
  }
  setOptions(items) {
    this.items = items.map(it => typeof it === "string" ? { value: it, label: it } : it);
    if (this.o.multi) {
      const vals = new Set(this.items.map(i => i.value));
      [...this.sel].forEach(v => { if (!vals.has(v)) this.sel.delete(v); });
    }
    if (this.panel) this._list();
    this._label();
    return this;
  }
  value() { return this.o.multi ? [...this.sel] : this.sel; }
  set(v) {
    this.sel = this.o.multi ? new Set(Array.isArray(v) ? v : (v ? [v] : [])) : (v || "");
    if (this.panel) this._list();
    this._label();
    return this;
  }
  _labelFor(v) { const it = this.items.find(i => i.value === v); return it ? it.label : v; }
  _label() {
    const lab = $(".dd-label", this.btn);
    if (this.o.multi) {
      const n = this.sel.size;
      this.btn.classList.toggle("placeholder", !n);
      lab.textContent = !n ? this.o.allLabel
        : n <= 2 ? [...this.sel].map(v => this._labelFor(v)).join(", ") : `${n} selected`;
    } else {
      this.btn.classList.toggle("placeholder", !this.sel);
      lab.textContent = this.sel ? this._labelFor(this.sel) : this.o.placeholder;
    }
  }
  _build() {
    this.panel = document.createElement("div");
    this.panel.className = "dd-panel";
    let html = this.o.searchable ? `<input class="dd-search" placeholder="Search…" />` : "";
    html += `<div class="dd-list"></div>`;
    if (this.o.multi) html += `<div class="dd-actions"><button class="dd-mini" data-act="all">Select all</button><button class="dd-mini" data-act="none">Clear</button></div>`;
    this.panel.innerHTML = html;
    this.el.appendChild(this.panel);
    this.search = $(".dd-search", this.panel);
    this.list = $(".dd-list", this.panel);
    if (this.search) this.search.addEventListener("input", () => this._list());
    $$(".dd-mini", this.panel).forEach(b => b.addEventListener("click", e => {
      e.stopPropagation();
      if (b.dataset.act === "all") this.items.forEach(i => this.sel.add(i.value)); else this.sel.clear();
      this._list(); this._label(); this._emit();
    }));
    this._list();
  }
  _list() {
    const q = ((this.search && this.search.value) || "").trim().toLowerCase();
    const matches = this.items.filter(i => !q || i.label.toLowerCase().includes(q));
    let html = matches.map(i => {
      const on = this.o.multi ? this.sel.has(i.value) : this.sel === i.value;
      return `<div class="dd-opt${on ? " sel" : ""}" data-v="${esc(i.value)}"><span class="dd-check">${on ? "✓" : ""}</span><span>${esc(i.label)}</span></div>`;
    }).join("");
    const exact = this.items.some(i => i.label.toLowerCase() === q);
    if (this.o.creatable && q && !exact)
      html += `<div class="dd-opt dd-create" data-create="1"><span class="dd-check"></span><span>+ Create “${esc(this.search.value.trim())}”</span></div>`;
    if (!html) html = `<div class="dd-empty">${this.o.emptyText}</div>`;
    this.list.innerHTML = html;
    $$(".dd-opt", this.list).forEach(opt => opt.addEventListener("click", async e => {
      e.stopPropagation();
      if (opt.dataset.create) {
        const name = this.search.value.trim();
        const created = this.o.onCreate ? await this.o.onCreate(name) : name;
        if (created) this._pick(created);
        return;
      }
      this._pick(opt.dataset.v);
    }));
  }
  _pick(v) {
    if (this.o.multi) { this.sel.has(v) ? this.sel.delete(v) : this.sel.add(v); this._list(); }
    else { this.sel = v; this.close(); }
    this._label(); this._emit();
  }
  _emit() { if (this.o.onChange) this.o.onChange(this.value()); }
  toggle() { this.el.classList.contains("open") ? this.close() : this.open(); }
  open() {
    if (_openDD && _openDD !== this) _openDD.close();
    if (!this.panel) this._build();
    this.el.classList.add("open");
    _openDD = this;
    // position the fixed panel against the button (flip up if low on space)
    const r = this.btn.getBoundingClientRect(), below = window.innerHeight - r.bottom;
    this.panel.style.left = Math.min(r.left, window.innerWidth - 332) + "px";
    this.panel.style.minWidth = r.width + "px";
    if (below < 340 && r.top > below) {
      this.panel.style.top = "auto"; this.panel.style.bottom = (window.innerHeight - r.top + 5) + "px";
    } else {
      this.panel.style.bottom = "auto"; this.panel.style.top = (r.bottom + 5) + "px";
    }
    if (this.search) { this.search.value = ""; this._list(); this.search.focus(); }
  }
  close() { this.el.classList.remove("open"); if (_openDD === this) _openDD = null; }
}
let dashMonthDD, fMonthDD, bulkSubDD;

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
  // multi-select billing-cycle pickers (dashboard + ledger)
  const monthItems = META.months.map(m => ({ value: m, label: monLabel(m) }));
  if (!dashMonthDD) {
    dashMonthDD = new Dropdown("#dashMonth",
      { multi: true, searchable: true, allLabel: "All cycles", onChange: loadDashboard });
    fMonthDD = new Dropdown("#fMonth",
      { multi: true, searchable: true, allLabel: "All cycles", onChange: loadLedger });
  }
  dashMonthDD.setOptions(monthItems);
  fMonthDD.setOptions(monthItems);
  // ledger filters
  fillOpts("#fCategory", "All categories", META.all_categories.map(c => [c, c]));
  fillOpts("#fBank", "All banks", META.banks.map(b => [b, b]));
  fillOpts("#fCard", "All cards", META.cards.map(c => [c, "•••• " + c]));
  const subs = META.all_subcategories || [];
  fillOpts("#fSubcategory", "All subcategories", subs.map(s => [s, s]));
  if (!bulkSubDD) {
    bulkSubDD = new Dropdown("#bulkSub", { searchable: true, creatable: true,
      placeholder: "subcategory (optional)", emptyText: "Type to create", onCreate: createSubcategory });
  }
  bulkSubDD.setOptions(subItems(subs));
  populateCatSelects();
}

// subcategory option list with a leading "clear" entry for single comboboxes
function subItems(subs) {
  return [{ value: "", label: "— none —" }, ...subs.map(s => ({ value: s, label: s }))];
}

// persist a brand-new subcategory to the DB list, then refresh every picker
async function createSubcategory(name) {
  const r = await api("/api/subcategories",
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }) });
  META.all_subcategories = r.subcategories;
  refreshSubcats();
  return r.added;
}

// shared ledger filter map (id ↔ query key) used by list, bulk, and export.
// Billing cycle (month) is a multi-select dropdown, handled separately.
const FMAP = { search: "#fSearch", category: "#fCategory",
  subcategory: "#fSubcategory", bank: "#fBank", card_last4: "#fCard",
  direction: "#fDirection", section: "#fSection", is_emi: "#fEmi" };
function currentFilters() {
  const f = {};
  for (const [k, sel] of Object.entries(FMAP)) if ($(sel) && $(sel).value) f[k] = $(sel).value;
  const months = fMonthDD ? fMonthDD.value() : [];
  if (months.length) f.month = months.join(",");
  return f;
}

// Drill from a chart sector into a filtered ledger view, carrying the
// dashboard's current card/cycle context.
function drillToLedger(extra) {
  Object.values(FMAP).forEach(s => $(s).value = "");
  fMonthDD.set(dashMonthDD ? dashMonthDD.value() : []);   // carry cycle context
  if ($("#dashCard").value) $("#fCard").value = $("#dashCard").value;
  if (extra.category != null) $("#fCategory").value = extra.category;
  if (extra.section != null) $("#fSection").value = extra.section;
  $$(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === "ledger"));
  $$(".view").forEach(s => s.classList.remove("active"));
  $("#view-ledger").classList.add("active");
  loadLedger();
  toast("Filtered ledger" + (extra.category ? ` · ${extra.category}` : "") +
        (extra.section ? ` · ${extra.section}` : ""));
}
const drillOpts = pick => ({
  onClick: (e, els, chart) => { if (els.length) drillToLedger(pick(chart.data.labels[els[0].index])); },
  onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
});
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

async function loadDashboard() {
  const card = $("#dashCard").value;
  const selMonths = dashMonthDD ? dashMonthDD.value() : [];
  const qs = new URLSearchParams();
  if (card) qs.set("card", card);
  if (selMonths.length) qs.set("month", selMonths.join(","));
  const stats = await api("/api/stats?" + qs);

  const cycles = stats.cycles;                       // statement-level, by cycle month
  const counts = stats.cycle_counts || {};
  // focus = the selected cycle(s); when none selected, the most recent one.
  let focus;
  if (selMonths.length) focus = cycles.filter(c => selMonths.includes(c.month));
  else { const last = cycles[cycles.length - 1]; focus = last ? [last] : []; }
  const sum = (arr, k) => arr.reduce((a, c) => a + (c[k] || 0), 0);
  const opening = sum(focus, "previous_balance");
  const spend = sum(focus, "purchases");
  const pay = sum(focus, "payments");
  const due = sum(focus, "total_due");
  const cnt = { n: focus.reduce((a, c) => a + ((counts[c.month] || {}).n || 0), 0) };
  const refunds = focus.reduce((a, c) => a + ((counts[c.month] || {}).refunds || 0), 0);
  // month-over-month only makes sense for a single focused cycle
  let mom = null, prevLbl = "";
  if (focus.length === 1) {
    const fi = cycles.findIndex(c => c.month === focus[0].month);
    const prev = fi > 0 ? cycles[fi - 1] : null;
    if (prev && prev.total_due) { mom = (focus[0].total_due - prev.total_due) / prev.total_due * 100; prevLbl = monLabel(prev.month); }
  }
  const cycLbl = focus.length === 1 ? monLabel(focus[0].month)
    : focus.length > 1 ? `${focus.length} cycles` : "—";

  // KPIs follow the statement's own equation: opening + spend − payments = due
  const kpis = [
    ["Opening balance", inr(opening), "carried in from last bill", ""],
    ["+ New spend", inr(spend), "gross purchases this cycle", ""],
    ["− Payments &amp; credits", inr(pay),
      refunds ? `incl. ${inr(refunds)} reversals` : "payments + credits", ""],
    [`= Total payable · ${cycLbl}`, inr(due),
      mom == null ? (focus.length > 1 ? "summed across selected cycles" : "the bill generated this cycle") :
        `${mom >= 0 ? "▲" : "▼"} ${Math.abs(mom).toFixed(1)}% vs ${prevLbl}`,
      mom == null ? "" : (mom >= 0 ? "up" : "down")],
  ];
  $("#kpis").innerHTML = kpis.map(([l, v, s, cls], i) =>
    `<div class="kpi${i === 3 ? " kpi-due" : ""}"><div class="label">${l}</div>
     <div class="value">${v}</div><div class="sub ${cls}">${s}</div></div>`).join("");

  // Reconciliation strip — makes the arithmetic explicit
  const recon = Math.abs(opening + spend - pay - due) <= 1;
  $("#billEqn").innerHTML = focus.length
    ? `<span class="eq-part">${inr(opening)} <i>opening</i></span><span class="eq-op">+</span>
       <span class="eq-part">${inr(spend)} <i>new spend</i></span><span class="eq-op">−</span>
       <span class="eq-part">${inr(pay)} <i>payments &amp; credits</i></span><span class="eq-op">=</span>
       <span class="eq-part eq-due">${inr(due)} <i>total payable</i></span>
       <span class="eq-check">${recon ? "✓ reconciles" : "⚠ check"}</span>
       <span class="eq-meta">· ${cnt.n || 0} txns · ${cycLbl} bill</span>`
    : `<span class="eq-meta">Import a statement to see your bill breakdown.</span>`;

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
    options: baseOpts({ stacked: false, scroll: true }),
  });
  sizeScroll("chMonthly", cmonths.length, 64);

  // Category doughnut — scope label reflects the ACTUAL data scope
  const scopeLbl = selMonths.length
    ? (selMonths.length === 1 ? monLabel(selMonths[0]) : `${selMonths.length} cycles`)
    : "All cycles";
  const cat = stats.by_category.filter(c => c.total > 0);
  const catTotal = cat.reduce((s, c) => s + c.total, 0);
  $("#catScope").textContent = `${scopeLbl} · ${inr(catTotal)} total`;
  draw("chCategory", {
    type: "doughnut",
    data: {
      labels: cat.map(c => c.category),
      datasets: [{ data: cat.map(c => c.total), backgroundColor: PALETTE, borderWidth: 0 }],
    },
    options: {
      ...drillOpts(label => ({ category: label })),
      plugins: { legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => `${c.label}: ${inr(c.raw)} — click to view` } } },
      cutout: "58%",
    },
  });

  // Two-level Category → Subcategory donut
  $("#catSubScope").textContent = `${scopeLbl} · ${inr(catTotal)} total`;
  drawCatSub(stats.by_cat_sub || []);

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
  const diTotal = di.reduce((s, d) => s + d.total, 0);
  $("#diScope").textContent = `${scopeLbl} · ${inr(diTotal)} total`;
  draw("chDomIntl", {
    type: "doughnut",
    data: {
      labels: di.map(d => d.section),
      datasets: [{ data: di.map(d => d.total),
        backgroundColor: ["#5b8cff", "#a855f7"], borderWidth: 0 }],
    },
    options: { ...drillOpts(label => ({ section: label })), cutout: "58%",
      plugins: { legend: { position: "right" },
        tooltip: { callbacks: { label: c => `${c.label}: ${inr(c.raw)} — click to view` } } } },
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
      ...baseOpts({ stacked: true, scroll: true }),
      plugins: {
        legend: { labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: {
          label: c => `${c.dataset.label}: ${inr(c.raw)}`,
          footer: items => "Total payable: " + inr(totals[items[0].dataIndex]),
        } },
      },
    },
  });
  sizeScroll("chDue", months.length);
}

// concentric doughnut: inner ring = category, outer ring = subcategory
function drawCatSub(rows) {
  const order = [], map = {};
  rows.forEach(r => {
    if (!map[r.category]) { map[r.category] = { cat: r.category, total: 0, subs: [] }; order.push(map[r.category]); }
    map[r.category].total += r.total; map[r.category].subs.push(r);
  });
  order.sort((a, b) => b.total - a.total);
  const inner = { data: [], colors: [], labels: [] };
  const outer = { data: [], colors: [], labels: [] };
  order.forEach((c, ci) => {
    const base = PALETTE[ci % PALETTE.length];
    inner.data.push(c.total); inner.colors.push(base); inner.labels.push(c.cat);
    const subs = [...c.subs].sort((a, b) => b.total - a.total);
    subs.forEach((s, si) => {
      outer.data.push(s.total);
      outer.colors.push(shade(base, si, subs.length));
      outer.labels.push(`${c.cat} · ${s.subcategory}`);
    });
  });
  if (!inner.data.length) {
    if (charts.chCatSub) charts.chCatSub.destroy();
    return;
  }
  draw("chCatSub", {
    type: "doughnut",
    data: { datasets: [
      { data: inner.data, backgroundColor: inner.colors, _labels: inner.labels,
        borderColor: "#161b24", borderWidth: 1, weight: 1 },
      { data: outer.data, backgroundColor: outer.colors, _labels: outer.labels,
        borderColor: "#161b24", borderWidth: 1, weight: 1.5 },
    ] },
    options: {
      cutout: "38%",
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: {
          label: ctx => `${(ctx.dataset._labels || [])[ctx.dataIndex]}: ${inr(ctx.raw)}`,
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
    options: baseOpts({ stacked: true, scroll: true }),
  });
  sizeScroll("chCatTrend", months.length, 64);
}

function baseOpts({ stacked, scroll }) {
  return {
    responsive: true, maintainAspectRatio: !scroll,
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

["#fCategory", "#fSubcategory", "#fBank", "#fCard", "#fDirection",
 "#fSection", "#fEmi"].forEach(s => $(s).addEventListener("change", loadLedger));

// expandable search: click the magnifier to slide the field open
const searchBox = $("#searchBox"), fSearchEl = $("#fSearch");
$("#searchToggle").addEventListener("click", () => {
  const open = searchBox.classList.toggle("open");
  if (open) fSearchEl.focus();
  else if (fSearchEl.value) { fSearchEl.value = ""; searchBox.classList.remove("active"); loadLedger(); }
});
fSearchEl.addEventListener("input", debounce(() => {
  searchBox.classList.toggle("active", !!fSearchEl.value);
  loadLedger();
}));
fSearchEl.addEventListener("blur", () => { if (!fSearchEl.value) searchBox.classList.remove("open"); });

$("#fClear").addEventListener("click", () => {
  Object.values(FMAP).forEach(s => $(s).value = "");
  fMonthDD.set([]);
  searchBox.classList.remove("open", "active");
  loadLedger();
});
$$("th.sortable").forEach(th => th.addEventListener("click", () => {
  const col = th.dataset.sort;
  ledgerSort = { sort: col, order: ledgerSort.sort === col && ledgerSort.order === "desc" ? "asc" : "desc" };
  loadLedger();
}));

async function loadLedger() {
  const p = new URLSearchParams(currentFilters());
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
      (t.section === "International"
        ? `<span class="pill intl clickpill" data-fk="section" data-fv="International" title="Filter to international">INTL</span>` : "") +
      (t.is_emi
        ? `<span class="pill emi clickpill" data-fk="is_emi" data-fv="1" title="Filter to EMI">EMI</span>` : "");
    const fx = t.foreign_amount ? `${t.foreign_currency} ${Number(t.foreign_amount).toLocaleString("en-IN")}` : "—";
    const amtCls = t.direction === "credit" ? "amt-credit" : "amt-debit";
    const sign = t.direction === "credit" ? "− " : "";
    return `<tr>
      <td>${t.txn_date}<div class="desc-sub">${t.cycle_month ? monLabel(t.cycle_month) + " bill" : ""}${t.txn_time && t.txn_time !== "00:00" ? " · " + t.txn_time : ""}</div></td>
      <td class="desc-cell"><div class="desc-main">${esc(t.merchant || t.description)}${pills}</div>
        <div class="desc-sub">${esc(t.city ? t.city + " · " : "")}${esc(t.cardholder || "")}${t.ref_no ? " · ref " + esc(String(t.ref_no).slice(0, 14)) : ""}</div></td>
      <td>${t.bank}<div class="desc-sub">•••• ${t.card_last4}</div></td>
      <td><div class="cat-cell">${sel}
        <div class="dd dd-inline dd-single sub-dd" data-id="${t.id}"
             data-sub="${esc(t.subcategory || "")}"></div></div></td>
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
  // searchable, DB-backed subcategory combobox per row (replaces datalist)
  $$(".sub-dd", body).forEach(el => {
    const id = el.dataset.id;
    const dd = new Dropdown(el, { searchable: true, creatable: true,
      placeholder: "+ subcategory", emptyText: "Type to create", onCreate: createSubcategory,
      onChange: async val => {
        await api(`/api/transactions/${id}/subcategory`,
          { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ subcategory: val }) });
        toast(val ? "Subcategory saved" : "Subcategory cleared");
      } });
    dd.setOptions(subItems(META.all_subcategories));
    dd.set(el.dataset.sub);
  });
  $$(".clickpill", body).forEach(p => p.addEventListener("click", e => {
    e.stopPropagation();
    const sel = e.target.dataset.fk === "section" ? "#fSection" : "#fEmi";
    $(sel).value = e.target.dataset.fv;
    loadLedger();
  }));
}

// refresh every subcategory picker after the DB list changes
function refreshSubcats() {
  const subs = META.all_subcategories || [];
  if (bulkSubDD) bulkSubDD.setOptions(subItems(subs));
  const cur = $("#fSubcategory").value;
  fillOpts("#fSubcategory", "All subcategories", subs.map(s => [s, s]));
  $("#fSubcategory").value = cur;
}

// bulk tag, new category, export
function populateCatSelects() {
  $("#bulkCat").innerHTML = `<option value="">— category —</option>` +
    META.all_categories.map(c => `<option>${esc(c)}</option>`).join("");
}
$("#bulkApply").addEventListener("click", async () => {
  const cat = $("#bulkCat").value;
  const sub = (bulkSubDD ? bulkSubDD.value() : "").trim();
  if (!cat && !sub) { toast("Pick a category or a subcategory"); return; }
  const n = +$("#bulkCount").textContent;
  const what = [cat && `category “${cat}”`, sub && `subcategory “${sub}”`]
    .filter(Boolean).join(" + ");
  if (!confirm(`Set ${what} for all ${n} matching transaction(s)?`)) return;
  const payload = { filters: currentFilters() };
  if (cat) payload.category = cat;
  if (sub) payload.subcategory = sub;          // only sent when provided
  const r = await api("/api/transactions/bulk-category",
    { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload) });
  toast(`Updated ${r.updated} transaction(s)`);
  if (bulkSubDD) bulkSubDD.set("");
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
  const p = new URLSearchParams(currentFilters());
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
