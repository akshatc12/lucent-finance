<div align="center">
  <img src="assets/banner.svg" alt="Lucent — finances, illuminated." width="100%" />
  <p>
    <img alt="version" src="https://img.shields.io/badge/version-0.9.0-6d5cff" />
    <img alt="license" src="https://img.shields.io/badge/license-MIT-22c55e" />
    <img alt="python" src="https://img.shields.io/badge/python-3.9%2B-blue" />
    <img alt="private" src="https://img.shields.io/badge/%F0%9F%94%92-Private%20Terminal-1d2430" />
  </p>
</div>

**Lucent** is a fully local, self-hosted **Private Terminal** for your credit
cards. It parses HDFC, ICICI and Axis statement PDFs on your machine, stores
everything in a local SQLite database, and gives you billing-cycle analytics, a
searchable ledger, and a reconciliation engine. **No data ever leaves your
device.**

## Features

- **Import portal** — drag-and-drop one or more statement PDFs, with a secure
  password field for encrypted statements. Bank is auto-detected. Exact
  duplicate transactions `(date, description, amount, card)` are skipped on
  import so overlapping statements never double-count.
- **Billing-cycle dashboard** — everything is organised by the statement it was
  billed on, not the calendar date. Headline **Net Amount Due by billing cycle**
  (total payable, stacked by card), cycle-aware KPIs with month-over-month
  deltas, plus category mix, a **two-level Category → Subcategory donut**,
  category trend, spend by card, top merchants, and domestic-vs-international.
  Card filter and a **multi-select billing-cycle picker** scope every panel; the
  cycle bar charts scroll horizontally as statements accumulate.
- **Transaction ledger** — an expandable search and a single-row filter bar
  (cycle multi-select / category / subcategory / bank / card / direction /
  section / EMI), a sortable grid with **inline category dropdowns**, a
  **searchable subcategory combobox** backed by a real catalogue, **bulk
  re-tagging** of an entire search result, **custom categories**, and
  **free-text personal notes/tags** — type _“refund”_ (or _reversed_ / _ignore_)
  on a since-refunded charge to **net it out of the spend donuts** (the row stays
  in the ledger, dimmed and badged). INTL and EMI badges, foreign amounts.
- **Excel export** — download the current ledger view as a styled `.xlsx`.
- **Reconciliation engine** — for every imported statement, compares the parsed
  transaction sums against the printed statement totals (purchases, payments,
  total due, minimum due) and flags any discrepancy. Sample statements reconcile
  to the exact paisa.

## Tech

- **Backend:** Python + Flask, SQLite (`data/ledger.db`)
- **Parsing:** `pdfplumber` (layout-aware) with hand-tuned engines per bank
- **Export:** `openpyxl`
- **Frontend:** vanilla JS + Chart.js (vendored locally — works offline)

## Setup & run

**Easiest (macOS):** double-click **`run.command`** in Finder (drag it to your
Dock to keep it handy). It finds a free port, starts the server, and opens your
browser automatically — nothing to remember.

From a terminal:

```bash
git clone https://github.com/akshatc12/lucent-finance.git
cd lucent-finance
python3 -m pip install -r requirements.txt      # Flask + pdfplumber + openpyxl
python3 app.py                                  # auto-picks a free port, prints the URL
```

`app.py` defaults to port **8753** and automatically hops to the next free port
if it's busy, **always skipping macOS AirPlay's :5000 / :7000** — so launching
never clashes with AirPlay or a stale instance. Pin a port with
`PORT=9000 python3 app.py`. (AirPlay Receiver can also be turned off in System
Settings → General → AirDrop & Handoff.)

## Parsing engines

Each engine returns a normalized statement (card, dates, summary block) plus a
list of transactions. Highlights of the bank-specific handling:

- **HDFC (Diners/other):** the Rupee glyph renders as `C`; pdfplumber lays the
  summary box out non-linearly. Domestic vs international sections and add-on
  cardholders are tracked. Credits/reversals are detected by a lone `+` before
  the amount, an explicit `Cr`, or payment keywords. Wrapped `Ref#` lines and
  EMI conversions are handled. Multi-line descriptions are stitched back
  together.
- **ICICI (Sapphiro/other):** date and serial number are concatenated in the
  raw text and split apart; the reliable bottom summary line drives totals;
  credits carry a `CR` suffix. International rows that wrap across 2–3 visual
  lines (foreign amount / `THB` / INR) are re-joined using a column-aware
  completion test.
- **Axis (Neo / MY Zone / other):** two layouts are handled. The full e-mailed
  statement is parsed from word coordinates so the bank's *merchant-category*
  column is split out cleanly from the description; it provides the real
  statement period, generation date and per-transaction foreign-currency amounts
  (e.g. `( THB 846.00 )`), and international spend is taken straight from those.
  The cut-down Axis-app export (no statement date; long names wrap above/below
  the centred row) is still supported as a fallback, anchored on its
  date + amount + Debit/Credit token.

## Data & privacy

Everything is stored in `data/ledger.db` on this machine. Delete a statement
(and its transactions) from the Import tab, or delete the `data/` folder to
start fresh. PDFs are parsed in memory and are never written to disk or sent
anywhere.

## Project layout

```
run.command       double-click launcher (macOS): free port + opens browser
app.py            Flask app: REST API + static serving + Excel export + launcher
parsers.py        HDFC, ICICI & Axis parsing engines
db.py             SQLite schema, import/dedupe, queries, reconciliation
categorize.py     keyword-based auto-categorisation
static/           index.html, styles.css, app.js, favicon.svg, chart.umd.min.js
data/ledger.db    local database (created on first import — gitignored)
```

## Contributing & changelog

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch/merge workflow and
[CHANGELOG.md](CHANGELOG.md) for release history.

## License

[MIT](LICENSE) © 2026 Akshat Chaurasia
