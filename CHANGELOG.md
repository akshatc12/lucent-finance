# Changelog

All notable changes to **Lucent** are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/akshatc19/lucent-finance/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/akshatc19/lucent-finance/releases/tag/v0.5.0
[0.4.0]: https://github.com/akshatc19/lucent-finance/releases/tag/v0.4.0
[0.3.0]: https://github.com/akshatc19/lucent-finance/releases/tag/v0.3.0
[0.2.0]: https://github.com/akshatc19/lucent-finance/releases/tag/v0.2.0
[0.1.0]: https://github.com/akshatc19/lucent-finance/releases/tag/v0.1.0
