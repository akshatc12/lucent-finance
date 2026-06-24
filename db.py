"""SQLite persistence layer for the credit-card ledger.

The database lives in ./data/ledger.db and survives across sessions.
Duplicate detection follows the rule: a transaction is an exact duplicate when
(card_last4, txn_date, description, amount, direction) all match. Identical rows
*within the same statement* are kept (they are genuinely distinct charges);
duplicates are only skipped when re-importing the same data or an overlapping
statement period — handled by an occurrence-aware counter.
"""
import os
import sqlite3
import hashlib
import datetime as _dt

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "ledger.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS statements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    bank             TEXT,
    card_last4       TEXT,
    card_label       TEXT,
    statement_date   TEXT,
    period_start     TEXT,
    period_end       TEXT,
    due_date         TEXT,
    previous_balance REAL,
    purchases        REAL,
    payments_credits REAL,
    cash_advances    REAL,
    finance_charges  REAL,
    total_due        REAL,
    min_due          REAL,
    file_name        TEXT,
    imported_at      TEXT,
    file_sig         TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    statement_id     INTEGER REFERENCES statements(id) ON DELETE CASCADE,
    bank             TEXT,
    card_last4       TEXT,
    card_label       TEXT,
    txn_date         TEXT,
    txn_time         TEXT,
    description      TEXT,
    merchant         TEXT,
    city             TEXT,
    amount           REAL,
    direction        TEXT,
    currency         TEXT,
    foreign_amount   REAL,
    foreign_currency TEXT,
    section          TEXT,
    cardholder       TEXT,
    reward_points    INTEGER,
    ref_no           TEXT,
    is_emi           INTEGER,
    category         TEXT,
    cycle_month      TEXT,        -- YYYY-MM of the statement this txn was billed on
    dup_hash         TEXT,
    occ              INTEGER,
    created_at       TEXT
);
CREATE INDEX IF NOT EXISTS idx_txn_hash  ON transactions(dup_hash);
CREATE INDEX IF NOT EXISTS idx_txn_date  ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_cat   ON transactions(category);
"""


def _migrate(c):
    """Additive migrations for databases created by older versions."""
    cols = {r["name"] for r in c.execute("PRAGMA table_info(transactions)")}
    if "cycle_month" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN cycle_month TEXT")
    if "note" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN note TEXT")
    if "subcategory" not in cols:
        c.execute("ALTER TABLE transactions ADD COLUMN subcategory TEXT")
    # Backfill cycle_month from each transaction's statement date.
    c.execute("""
        UPDATE transactions SET cycle_month = (
            SELECT substr(COALESCE(s.statement_date, s.period_end, transactions.txn_date), 1, 7)
            FROM statements s WHERE s.id = transactions.statement_id)
        WHERE cycle_month IS NULL OR cycle_month = ''""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_txn_cycle ON transactions(cycle_month)")

    # Category catalogue: built-in defaults (ordered) plus any user-added ones.
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        name TEXT PRIMARY KEY, sort INTEGER, custom INTEGER DEFAULT 0)""")
    from categorize import CATEGORIES
    for i, name in enumerate(CATEGORIES):
        c.execute("INSERT OR IGNORE INTO categories (name, sort, custom) VALUES (?,?,0)",
                  (name, i))
    # Absorb any categories already present on transactions (e.g. older imports).
    for r in c.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL"):
        c.execute("INSERT OR IGNORE INTO categories (name, sort, custom) VALUES (?,999,1)",
                  (r["category"],))


def _conn():
    os.makedirs(DB_DIR, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        _migrate(c)


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def dup_hash(card_last4, txn_date, description, amount, direction):
    key = f"{card_last4}|{txn_date}|{(description or '').strip().upper()}|{amount}|{direction}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def file_signature(parsed):
    """A stable signature so re-importing the identical statement is a no-op."""
    s = parsed.get("summary", {})
    key = f"{parsed.get('bank')}|{parsed.get('card_last4')}|{parsed.get('statement_date')}|" \
          f"{s.get('total_due')}|{len(parsed.get('transactions', []))}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def import_statement(parsed):
    """Insert a parsed statement + its transactions, skipping exact duplicates.

    Returns a summary dict: inserted, duplicates, statement_id, already_imported.
    """
    init_db()
    sig = file_signature(parsed)
    s = parsed.get("summary", {})
    with _conn() as c:
        existing = c.execute("SELECT id FROM statements WHERE file_sig=?", (sig,)).fetchone()
        if existing:
            return {"already_imported": True, "statement_id": existing["id"],
                    "inserted": 0, "duplicates": len(parsed.get("transactions", [])),
                    "bank": parsed.get("bank"), "card_last4": parsed.get("card_last4")}

        cur = c.execute(
            """INSERT INTO statements (bank, card_last4, card_label, statement_date,
                period_start, period_end, due_date, previous_balance, purchases,
                payments_credits, cash_advances, finance_charges, total_due, min_due,
                file_name, imported_at, file_sig)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (parsed.get("bank"), parsed.get("card_last4"), parsed.get("card_label"),
             parsed.get("statement_date"), parsed.get("period_start"),
             parsed.get("period_end"), parsed.get("due_date"),
             s.get("previous_balance"), s.get("purchases"), s.get("payments_credits"),
             s.get("cash_advances"), s.get("finance_charges"), s.get("total_due"),
             s.get("min_due"), parsed.get("file_name"), _now(), sig))
        stmt_id = cur.lastrowid
        cyc = (parsed.get("statement_date") or parsed.get("period_end") or "")[:7] or None

        # occurrence-aware dedupe: count how many of each hash already exist in DB
        seen = {}
        for row in c.execute("SELECT dup_hash, COUNT(*) n FROM transactions GROUP BY dup_hash"):
            seen[row["dup_hash"]] = row["n"]

        inserted = dups = 0
        for t in parsed.get("transactions", []):
            h = dup_hash(t["card_last4"] if t.get("card_last4") else parsed.get("card_last4"),
                         t["txn_date"], t["description"], t["amount"], t["direction"])
            already = seen.get(h, 0)
            occ = already  # this row's occurrence index (0-based among DB rows)
            # skip only if a prior import already holds this occurrence
            if already > 0 and _occ_in_db(c, h, occ):
                # there is already a row with this hash & occ from a prior import
                dups += 1
                continue
            c.execute(
                """INSERT INTO transactions (statement_id, bank, card_last4, card_label,
                    txn_date, txn_time, description, merchant, city, amount, direction,
                    currency, foreign_amount, foreign_currency, section, cardholder,
                    reward_points, ref_no, is_emi, category, cycle_month, dup_hash, occ, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (stmt_id, t.get("bank"), t.get("card_last4") or parsed.get("card_last4"),
                 parsed.get("card_label"), t["txn_date"], t.get("txn_time"),
                 t["description"], t.get("merchant"), t.get("city"), t["amount"],
                 t["direction"], t.get("currency", "INR"), t.get("foreign_amount"),
                 t.get("foreign_currency"), t.get("section"), t.get("cardholder"),
                 t.get("reward_points"), t.get("ref_no"), 1 if t.get("is_emi") else 0,
                 t.get("category"), cyc, h, occ, _now()))
            seen[h] = already + 1
            inserted += 1
        return {"already_imported": False, "statement_id": stmt_id,
                "inserted": inserted, "duplicates": dups,
                "bank": parsed.get("bank"), "card_last4": parsed.get("card_last4")}


def _occ_in_db(c, h, occ):
    r = c.execute("SELECT 1 FROM transactions WHERE dup_hash=? AND occ=? LIMIT 1",
                  (h, occ)).fetchone()
    return r is not None


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _build_where(filters):
    """Shared filter clause for listing, bulk actions, and export."""
    clause = " WHERE 1=1"
    args = []
    if filters.get("search"):
        clause += " AND (UPPER(description) LIKE ? OR UPPER(merchant) LIKE ? " \
                  "OR UPPER(category) LIKE ? OR UPPER(COALESCE(subcategory,'')) LIKE ? " \
                  "OR UPPER(COALESCE(note,'')) LIKE ?)"
        s = f"%{filters['search'].upper()}%"
        args += [s, s, s, s, s]
    for col in ("category", "subcategory", "bank", "card_last4", "direction", "section"):
        if filters.get(col):
            clause += f" AND {col}=?"
            args.append(filters[col])
    if str(filters.get("is_emi", "")).lower() in ("1", "true", "yes"):
        clause += " AND is_emi=1"
    elif str(filters.get("is_emi", "")).lower() in ("0", "false", "no"):
        clause += " AND is_emi=0"
    if filters.get("month"):  # YYYY-MM billing cycle
        clause += " AND cycle_month=?"
        args.append(filters["month"])
    if filters.get("date_from"):
        clause += " AND txn_date>=?"
        args.append(filters["date_from"])
    if filters.get("date_to"):
        clause += " AND txn_date<=?"
        args.append(filters["date_to"])
    return clause, args


def list_transactions(filters=None):
    filters = filters or {}
    clause, args = _build_where(filters)
    sort = filters.get("sort", "txn_date")
    if sort not in ("txn_date", "amount", "description", "category", "merchant", "bank"):
        sort = "txn_date"
    order = "ASC" if str(filters.get("order", "desc")).lower() == "asc" else "DESC"
    q = "SELECT * FROM transactions" + clause + f" ORDER BY {sort} {order}, id {order}"
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def _ensure_category(c, name):
    c.execute("INSERT OR IGNORE INTO categories (name, sort, custom) VALUES (?,999,1)", (name,))


def update_category(txn_id, category):
    with _conn() as c:
        _ensure_category(c, category)
        c.execute("UPDATE transactions SET category=? WHERE id=?", (category, txn_id))
        return c.total_changes


def update_subcategory(txn_id, subcategory):
    with _conn() as c:
        c.execute("UPDATE transactions SET subcategory=? WHERE id=?",
                  ((subcategory or "").strip() or None, txn_id))
        return c.total_changes


def bulk_update(filters, category=None, subcategory=None):
    """Apply a category and/or subcategory to every matching transaction.

    `subcategory=""` clears the subcategory; `None` leaves it untouched.
    """
    clause, args = _build_where(filters or {})
    sets, vals = [], []
    if category:
        sets.append("category=?"); vals.append(category)
    if subcategory is not None:
        sets.append("subcategory=?"); vals.append(subcategory.strip() or None)
    if not sets:
        return 0
    with _conn() as c:
        if category:
            _ensure_category(c, category)
        c.execute(f"UPDATE transactions SET {', '.join(sets)}" + clause, vals + args)
        return c.total_changes


def update_note(txn_id, note):
    with _conn() as c:
        c.execute("UPDATE transactions SET note=? WHERE id=?", (note or None, txn_id))
        return c.total_changes


def list_subcategories():
    with _conn() as c:
        return [r["subcategory"] for r in c.execute(
            "SELECT DISTINCT subcategory FROM transactions "
            "WHERE subcategory IS NOT NULL AND subcategory<>'' ORDER BY subcategory")]


def list_categories():
    with _conn() as c:
        return [r["name"] for r in c.execute(
            "SELECT name FROM categories ORDER BY custom, sort, name")]


def add_category(name):
    name = (name or "").strip()
    if not name:
        return None
    with _conn() as c:
        _ensure_category(c, name)
    return name


def list_statements():
    with _conn() as c:
        rows = c.execute("SELECT * FROM statements ORDER BY statement_date DESC, id DESC").fetchall()
        return [dict(r) for r in rows]


def delete_statement(stmt_id):
    with _conn() as c:
        c.execute("DELETE FROM transactions WHERE statement_id=?", (stmt_id,))
        c.execute("DELETE FROM statements WHERE id=?", (stmt_id,))
        return c.total_changes


def distinct_values():
    with _conn() as c:
        def col(name):
            return [r[0] for r in c.execute(
                f"SELECT DISTINCT {name} FROM transactions WHERE {name} IS NOT NULL ORDER BY {name}")]
        return {
            "categories": col("category"),
            "subcategories": [r[0] for r in c.execute(
                "SELECT DISTINCT subcategory FROM transactions "
                "WHERE subcategory IS NOT NULL AND subcategory<>'' ORDER BY subcategory")],
            "banks": col("bank"),
            "cards": col("card_last4"),
            "months": [r[0] for r in c.execute(
                "SELECT DISTINCT cycle_month m FROM transactions WHERE cycle_month IS NOT NULL ORDER BY m DESC")],
        }


def stats_overview(card=None, month=None):
    """Aggregations powering the dashboard, organised by billing cycle.

    `card`  — restrict everything to one card (last4) when given.
    `month` — billing-cycle month (YYYY-MM). Snapshot panels (category, merchant,
              domestic/intl, totals/KPIs) scope to this cycle; the time-series
              charts always show the full timeline so trends stay visible.
    """
    with _conn() as c:
        def rows(sql, args=()):
            return [dict(r) for r in c.execute(sql, args).fetchall()]

        # ---- statement-level cycle figures (the "net payable" view) --------
        sc, sa = "", []
        if card:
            sc = " WHERE card_last4=?"
            sa = [card]
        cycles = rows(f"""
            SELECT substr(statement_date,1,7) month,
                   SUM(total_due)        total_due,
                   SUM(purchases)        purchases,
                   SUM(payments_credits) payments,
                   SUM(previous_balance) previous_balance,
                   COUNT(*)              cards
            FROM statements{sc}
            GROUP BY month ORDER BY month""", sa)

        cycles_by_card = rows(f"""
            SELECT substr(statement_date,1,7) month, bank, card_last4,
                   card_label, total_due, purchases, payments_credits payments,
                   min_due, due_date
            FROM statements{sc} ORDER BY month, card_last4""", sa)

        twc = " WHERE cycle_month IS NOT NULL" + (" AND card_last4=?" if card else "")
        cycle_counts = {r["month"]: {"n": r["n"], "debit": r["debit"],
                                     "credit": r["credit"], "refunds": r["refunds"]}
                        for r in c.execute(f"""
            SELECT cycle_month month, COUNT(*) n,
                   SUM(CASE WHEN direction='debit'  THEN amount ELSE 0 END) debit,
                   SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END) credit,
                   SUM(CASE WHEN direction='credit' AND category<>'Payments & Credits'
                            THEN amount ELSE 0 END) refunds
            FROM transactions{twc} GROUP BY month""", ([card] if card else []))}

        # ---- transaction snapshot (scoped to card + optional cycle) --------
        def where(extra=""):
            cl, a = ["1=1"], []
            if card:
                cl.append("card_last4=?"); a.append(card)
            if month:
                cl.append("cycle_month=?"); a.append(month)
            if extra:
                cl.append(extra)
            return " WHERE " + " AND ".join(cl), a

        w, a = where("direction='debit'")
        by_category = rows(f"""SELECT category, SUM(amount) total, COUNT(*) n
            FROM transactions{w} GROUP BY category ORDER BY total DESC""", a)

        w, a = where("direction='debit' AND merchant IS NOT NULL")
        by_merchant = rows(f"""SELECT merchant, SUM(amount) total, COUNT(*) n
            FROM transactions{w} GROUP BY UPPER(merchant) ORDER BY total DESC LIMIT 15""", a)

        w, a = where("direction='debit' AND section IS NOT NULL")
        dom_intl = rows(f"""SELECT section, SUM(amount) total, COUNT(*) n
            FROM transactions{w} GROUP BY section""", a)

        w, a = where()
        by_card = rows(f"""SELECT bank, card_last4, card_label,
                   SUM(CASE WHEN direction='debit' THEN amount ELSE 0 END) spend,
                   COUNT(*) n
            FROM transactions{w} GROUP BY bank, card_last4 ORDER BY spend DESC""", a)
        totals = c.execute(f"""SELECT COUNT(*) n,
                   SUM(CASE WHEN direction='debit'  THEN amount ELSE 0 END) spend,
                   SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END) credit
            FROM transactions{w}""", a).fetchone()

        # category trend over the full timeline (card-scoped, never month-scoped)
        wt = " WHERE direction='debit' AND cycle_month IS NOT NULL"
        at = []
        if card:
            wt += " AND card_last4=?"; at.append(card)
        cat_by_month = rows(f"""SELECT cycle_month month, category, SUM(amount) total
            FROM transactions{wt} GROUP BY month, category ORDER BY month""", at)

        return {
            "cycles": cycles, "cycles_by_card": cycles_by_card,
            "cycle_counts": cycle_counts,
            "by_category": by_category, "by_card": by_card,
            "by_merchant": by_merchant, "cat_by_month": cat_by_month,
            "dom_intl": dom_intl, "selected_month": month, "selected_card": card,
            "totals": {"n": totals["n"] or 0, "spend": totals["spend"] or 0,
                       "credit": totals["credit"] or 0},
        }


def reconciliation():
    """For each statement compare the parsed transaction sums to the printed
    summary figures and surface any difference."""
    out = []
    with _conn() as c:
        for st in c.execute("SELECT * FROM statements ORDER BY statement_date DESC, id DESC"):
            agg = c.execute("""
                SELECT SUM(CASE WHEN direction='debit'  THEN amount ELSE 0 END) debit,
                       SUM(CASE WHEN direction='credit' THEN amount ELSE 0 END) credit,
                       COUNT(*) n
                FROM transactions WHERE statement_id=?""", (st["id"],)).fetchone()
            debit = round(agg["debit"] or 0, 2)
            credit = round(agg["credit"] or 0, 2)
            purch = st["purchases"]
            pays = st["payments_credits"]
            d_diff = round(debit - purch, 2) if purch is not None else None
            c_diff = round(credit - pays, 2) if pays is not None else None
            ok = (d_diff is not None and abs(d_diff) <= 1.0 and
                  c_diff is not None and abs(c_diff) <= 1.0)
            out.append({
                "statement_id": st["id"], "bank": st["bank"],
                "card_last4": st["card_last4"], "card_label": st["card_label"],
                "statement_date": st["statement_date"],
                "period_start": st["period_start"], "period_end": st["period_end"],
                "txn_count": agg["n"] or 0,
                "parsed_debit": debit, "parsed_credit": credit,
                "stmt_purchases": purch, "stmt_payments_credits": pays,
                "stmt_total_due": st["total_due"], "stmt_min_due": st["min_due"],
                "debit_diff": d_diff, "credit_diff": c_diff,
                "previous_balance": st["previous_balance"],
                "status": "balanced" if ok else "review",
            })
    return out
