# Changelog

All notable changes to **Lucent** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] — 2026-06-25
### Added
- **Axis Bank statement parsing** — supports the Neo and MY Zone consumer cards
  (and other variants sharing the same layout). Reconciles to the exact paisa:
  Opening balance + debits − credits = Total Payment Due.
- The Axis parser is **coordinate-based**: long merchant names wrap to several
  physical lines that straddle the (vertically-centred) date/amount/direction
  row, so rows are rebuilt from word positions rather than the flat text stream.
  Each row's description is the detail-column text vertically nearest its anchor.
- International spend on Axis cards (no explicit section in the statement) is
  inferred from foreign-city / "Foreign Currency" markers for the Domestic-vs-
  International breakdown.
### Changed
- Auto-categorisation: **MB PAYMENT** (Axis mobile-banking bill payment) is now
  recognised as **Payments & Credits**; added keyword coverage for Nykaa, Blink
  Commerce (Blinkit), EaseMyTrip and InterGlobe Aviation.
- HDFC/ICICI parsing is unchanged — text extraction is identical; all eight
  existing sample statements still reconcile to the paisa (regression-tested).

## [0.6.0] — 2026-06-24
### Added
- **Bill breakdown** on the dashboard — KPIs now follow the statement's own
  equation (Opening balance + New spend − Payments & credits = **Total
  payable**), with an explicit reconciliation strip so the bill always adds up.
  Clarifies that "carried forward" is last statement's closing balance.
- Reversals/refunds for the cycle are surfaced inline (e.g. "incl. ₹1,49,751
  reversals") so gross spend vs. net is transparent.
- Doughnut charts now show a **scope + total** tag in their header.
### Fixed
- **Category / Domestic-vs-Intl doughnuts were mislabeled** with the latest
  cycle while actually showing all-cycle data. The scope label now matches the
  data: "All cycles" when no cycle is selected, otherwise the chosen cycle.
### Changed
- Credit auto-categorisation now buckets genuine bill payments as **Payments &
  Credits** and merchant refunds/reversals as **Refunds & Reversals** (a new
  default category), instead of lumping everything together.

## [0.5.0] — 2026-06-24
### Added
- **Two-level tagging** — each transaction now has a free-text **subcategory**
  alongside its category (e.g. Travel → Hotel, Shopping → Vacation), editable
  inline with autocomplete and settable in bulk. Subcategory is searchable,
  filterable, and included in the Excel export.
- **Clickable tags** — the INTL and EMI badges in the ledger filter the grid to
  international / EMI transactions in one click. New Section and EMI filters back
  them.
- **Chart drill-down** — clicking a sector of the "Spend by Category" or
  "Domestic vs International" doughnut opens the ledger filtered to that slice,
  carrying the dashboard's current card/cycle context.

## [0.4.0] — 2026-06-24
### Changed
- **Rebrand to Lucent** — _"Finances, illuminated."_ New name, wordmark, and
  violet→cyan identity across the app.
- Privacy is now surfaced as a **"Private Terminal"** badge in the sidebar.
### Added
- SVG favicon / app icon (lumen mark).
- Repository scaffolding: license, changelog, contributing guide, `.gitignore`
  that excludes all local financial data.

## [0.3.0] — 2026-06-24
### Added
- **Bulk tagging** — apply a category to every transaction in the current
  ledger search/filter set in one action.
- **Custom categories** — create your own categories (e.g. "Refunds &
  Reversals") that appear everywhere instantly.
- **Per-transaction notes** — free-text personal tags (e.g. "Croma Refrigerator
  EMI installment"); notes are searchable.
- **Excel export** — download the current ledger view as a styled `.xlsx`.

## [0.2.0] — 2026-06-24
### Changed
- Reorganised analytics around the **billing cycle** instead of the calendar
  date: each transaction is tagged to the statement it was billed on.
- Dashboard headline is now **Net Amount Due by billing cycle** (total payable,
  stacked by card) rather than spend-vs-payments.
### Fixed
- Dashboard card/cycle filters now actually filter every panel.

## [0.1.0] — 2026-06-24
### Added
- Local-first **HDFC** and **ICICI** statement parsing engines (pdfplumber),
  reconciling to the exact paisa against printed statement totals.
- SQLite persistence with occurrence-aware duplicate detection on import.
- Dashboard (KPIs + month-over-month charts), searchable/sortable transaction
  ledger with inline re-tagging, and a reconciliation engine.
- Import portal with statement-password support; all processing stays local.

[Unreleased]: https://github.com/akshatc12/lucent-finance/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.7.0
[0.6.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.6.0
[0.5.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.5.0
[0.4.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.4.0
[0.3.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.3.0
[0.2.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.2.0
[0.1.0]: https://github.com/akshatc12/lucent-finance/releases/tag/v0.1.0
