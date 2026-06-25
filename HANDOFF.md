# Lucent — Session Handoff

_Last updated: 2026-06-25 · current release: **v0.7.0**_

A working note for picking this project up in a fresh chat. Not a spec — see
[README.md](README.md), [CHANGELOG.md](CHANGELOG.md), and
[CONTRIBUTING.md](CONTRIBUTING.md) for the canonical docs.

## What this is
**Lucent** ("Finances, illuminated.") — a fully local, private credit-card
analytics dashboard + ledger. Parses HDFC, ICICI & Axis statement PDFs on-device,
stores them in SQLite, and presents billing-cycle analytics, a searchable
ledger, and a reconciliation engine. Nothing leaves the machine ("Private
Terminal").

## Run it
```bash
cd ~/Downloads/Projects/claude_credit_card
python3 -m pip install -r requirements.txt     # Flask, pdfplumber, openpyxl
python3 app.py                                 # http://127.0.0.1:5000
# macOS: port 5000 is AirPlay → use:  PORT=8753 python3 app.py
```

## Stack & layout
- **Backend:** Python + Flask, SQLite at `data/ledger.db` (gitignored).
- `app.py` — REST API + static serving + `.xlsx` export.
- `parsers.py` — HDFC, ICICI & Axis parsing engines (pdfplumber).
- `db.py` — schema, additive migrations, import/dedupe, queries, reconciliation, stats.
- `categorize.py` — keyword auto-categorisation.
- `static/` — `index.html`, `styles.css`, `app.js` (vanilla JS), `favicon.svg`, vendored `chart.umd.min.js`.

## Key domain logic (read before changing analytics)
- **Billing cycle is the unit, not calendar date.** Every transaction carries
  `cycle_month` = the month of the statement it was billed on. All dashboard
  rollups and the ledger month filter use `cycle_month`.
- **The bill equation (reconciles exactly):**
  `opening (previous_balance) + new spend (purchases) − payments_credits = total_due`.
  Statement-level figures live in the `statements` table; the dashboard KPIs and
  the reconciliation strip show this equation. "Opening / carried forward" =
  previous statement's closing balance.
- **Reversals/refunds are NOT offset in category spend.** Category doughnut is
  **gross debits**. Merchant refunds are auto-bucketed into **"Refunds &
  Reversals"**; genuine settlements → **"Payments & Credits"**. Both are netted
  into the bill (inside `payments_credits`) but shown separately in the ledger.
- **Parsers reconcile to the exact paisa** against printed statement totals.
  HDFC: Rupee glyph renders as `C`; credits flagged by lone `+`/`Cr`/keywords;
  jumbled summary box; EMI/Ref# wraps stitched. ICICI: date+serial concatenated
  then split; `CR` suffix = credit; intl rows wrap across 2–3 lines. Axis (Neo /
  MY Zone): **coordinate-based** — rows anchored on date+amount+Debit/Credit,
  description = detail-column words vertically nearest the anchor (long merchant
  names wrap above/below the row); totals from the payment-summary box; intl
  inferred from foreign-city markers; needs the per-statement password.
- **Dedupe** on import is occurrence-aware on `(card, date, description, amount,
  direction)` — re-importing the same/overlapping statement is safe; genuinely
  repeated same-day charges are kept.

## Feature inventory
Import portal (multi-PDF + password) · billing-cycle dashboard (bill breakdown
KPIs, Net Amount Due by cycle stacked-by-card, category mix, category trend,
spend-by-card, top merchants, domestic/intl) · ledger (search/filter/sort,
inline + **bulk** re-tagging, **custom categories**, **two-level subcategory**,
free-text **notes**) · clickable INTL/EMI pills · **chart→ledger drill-down** ·
**Excel export** · reconciliation engine.

## Open items / decisions for the next session
1. **Net-vs-gross Travel (pending user decision).** User's 4 cancelled-Georgia
   reversals (₹1,49,751, June) are bucketed in "Refunds & Reversals", so Travel
   shows **gross** (June ₹5.46L). User was offered: keep bifurcated (current) OR
   bulk-retag those 4 to "Travel" so net Travel ≈ ₹3.96L. **Awaiting their call.**
2. **No in-browser visual verification.** The preview sandbox can't read
   `~/Downloads` (macOS TCC) and no Chrome extension is connected, so changes are
   verified via the API + served files, not by rendering. Moving the repo out of
   `~/Downloads` would unblock the built-in preview tooling.
3. **`gh` keyring** still *displays* the old username `BruceWayne1219`
   cosmetically; the token/account/remote are correct (`akshatc12`).

## Repo & workflow
- Private repo: **github.com/akshatc12/lucent-finance** (MIT). `gh` installed & authed.
- Workflow (per CONTRIBUTING.md): feature branches → `--no-ff` merge → Keep-a-
  Changelog entry → SemVer tag. Commit trailer: `Co-Authored-By: Claude Opus 4.8`.
- Push:  `git push origin main && git push origin --tags`
