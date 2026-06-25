"""Bank-specific statement parsing engines for HDFC (Diners/other), ICICI and
Axis (Neo / MY Zone / other).

Each parser returns a dict:
  {
    "bank": "HDFC" | "ICICI" | "AXIS",
    "card_last4": "1960",
    "card_label": "Diners Black Credit Card",
    "statement_date": "2026-06-17",      # ISO or None
    "period_start": "2026-05-18",
    "period_end":   "2026-06-17",
    "due_date":     "2026-07-07",
    "summary": { previous_balance, purchases, payments_credits,
                 cash_advances, finance_charges, total_due, min_due },
    "transactions": [ { txn_date, txn_time, description, merchant, city,
                        amount, direction, currency, foreign_amount,
                        foreign_currency, section, cardholder,
                        reward_points, ref_no, is_emi }, ... ]
  }

Parsing is layout-based via pdfplumber. The HDFC font renders the Rupee glyph as
"C"; ICICI renders it as a back-tick "`". Both are handled. Axis renders a real
"₹" but wraps long merchant names across the row, so it is parsed from word
coordinates instead of the flat text stream.
"""
import re
import datetime as _dt

import pdfplumber

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 3-letter foreign currency codes we may see on international rows.
_FX = {"USD", "THB", "EUR", "GBP", "AED", "SGD", "JPY", "AUD", "CHF",
       "CAD", "HKD", "MYR", "IDR", "VND", "LKR", "NPR", "CNY", "KRW"}


def _to_float(s: str):
    if s is None:
        return None
    s = s.replace(",", "").replace("`", "").replace("C", "").strip()
    s = s.replace("₹", "")
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _iso_dmy(d, m, y):
    try:
        return _dt.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def _iso_from_text_date(text):
    """Parse '07 Jul, 2026' / 'July 3, 2026' / 'May 16, 2026' -> ISO date."""
    if not text:
        return None
    text = text.strip().strip(".")
    # '07 Jul, 2026'
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})\,?\s+(\d{4})", text)
    if m:
        mon = _MONTHS.get(m.group(2)[:3].lower())
        if mon:
            return _iso_dmy(m.group(1), mon, m.group(3))
    # 'July 3, 2026'
    m = re.search(r"([A-Za-z]{3,})\s+(\d{1,2})\,?\s+(\d{4})", text)
    if m:
        mon = _MONTHS.get(m.group(1)[:3].lower())
        if mon:
            return _iso_dmy(m.group(2), mon, m.group(3))
    return None


def _read_pages(path, password=None):
    pages = []
    with pdfplumber.open(path, password=password) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return pages


def _read_doc(path, password=None):
    """Read text *and* positioned words per page in a single open.

    HDFC/ICICI parse from the flat text stream; Axis statements lay long
    merchant names out as multi-line cells centred on the date/amount row, so
    that parser reconstructs rows from word coordinates instead.
    """
    texts, word_pages = [], []
    with pdfplumber.open(path, password=password) as pdf:
        for p in pdf.pages:
            texts.append(p.extract_text() or "")
            word_pages.append(p.extract_words(use_text_flow=False))
    return texts, word_pages


def detect_bank(pages):
    head = "\n".join(pages[:2]).lower()
    if "axis" in head:
        return "AXIS"
    if "icici" in head:
        return "ICICI"
    if "hdfc" in head or "diners" in head:
        return "HDFC"
    # Fallback heuristics on transaction shape
    if re.search(r"\d{2}/\d{2}/\d{4}\s+\d{9,}", head):
        return "ICICI"
    return "HDFC"


# Amount near the end of an HDFC row: "C 1,962.00" optionally "Cr"
_HDFC_AMT = re.compile(r"[C₹]\s*([\d,]+\.\d{2})\s*(Cr)?\s*l?\s*$", re.I)
_HDFC_TXN = re.compile(r"^(\d{2}/\d{2}/\d{4})\s*\|\s*(\d{2}:\d{2})\s+(.*)$")
_HDFC_CREDIT_KW = re.compile(
    r"\b(payment|bppy|reversal|refund|cashback|received|credit)\b", re.I)


def _hdfc_section(line):
    l = line.strip().lower()
    if l.startswith("domestic transaction"):
        return "Domestic"
    if l.startswith("international transaction"):
        return "International"
    return None


def _is_cardholder(line):
    s = line.strip()
    if not (3 <= len(s) <= 40):
        return False
    if not re.fullmatch(r"[A-Z][A-Z .]+", s):
        return False
    # Exclude statement headers that are all caps
    bad = ("DATE", "DOMESTIC", "INTERNATIONAL", "TOTAL", "PAGE", "HDFC",
           "TRANSACTION", "AMOUNT", "REWARDS", "IMPORTANT", "GST", "HSN",
           "MINIMUM", "POINTS", "REDEEM", "BANK", "DUE", "OVER", "CURRENT")
    return not any(b in s for b in bad)


def parse_hdfc(pages, file_name=""):
    text = "\n".join(pages)
    summary = {}

    # ---- card / dates --------------------------------------------------
    last4 = None
    m = re.search(r"(\d{4,6}[X]{4,}\d{4})", text)
    if m:
        last4 = re.sub(r"[^\d]", "", m.group(1))[-4:]
    label = "HDFC Credit Card"
    m = re.search(r"([A-Za-z ]+Credit Card) Statement", text)
    if m:
        label = m.group(1).strip()

    stmt_date = _iso_from_text_date(_after(text, r"Statement Date"))
    period = re.search(r"(\d{1,2}\s+[A-Za-z]{3,}\,?\s+\d{4})\s*-\s*"
                       r"(\d{1,2}\s+[A-Za-z]{3,}\,?\s+\d{4})", text)
    period_start = _iso_from_text_date(period.group(1)) if period else None
    period_end = _iso_from_text_date(period.group(2)) if period else None
    due_date = None
    # ---- summary block (pdfplumber lays HDFC out as a jumbled box) ------
    # 4-value row: prev dues / payments-credits / purchases / finance charges
    row = re.search(r"[C₹`]([\d,]+\.\d{2})\s+[C₹`]([\d,]+\.\d{2})\s*\+\s*"
                    r"[C₹`]([\d,]+\.\d{2})\s*\+\s*[C₹`]([\d,]+\.\d{2})\s*=?",
                    text)
    if row:
        summary["previous_balance"] = _to_float(row.group(1))
        summary["payments_credits"] = _to_float(row.group(2))
        summary["purchases"] = _to_float(row.group(3))
        summary["finance_charges"] = _to_float(row.group(4))
    summary["cash_advances"] = 0.0
    # total amount due sits alone on an underscore-prefixed line
    mtot = re.search(r"(?m)^_+\s*[C₹`]([\d,]+\.\d{2})\s*$", text)
    summary["total_due"] = _to_float(mtot.group(1)) if mtot else None
    # limits row ends with: ... <MIN DUE> <DUE DATE>
    mlim = re.search(r"[C₹`]([\d,]+\.\d{2})\s+(\d{1,2}\s+[A-Za-z]{3,}\,?\s+\d{4})",
                     text)
    if mlim:
        summary["min_due"] = _to_float(mlim.group(1))
        due_date = _iso_from_text_date(mlim.group(2))
    else:
        summary["min_due"] = None
    if summary.get("total_due") is None and summary.get("purchases") is not None:
        summary["total_due"] = round(
            (summary.get("previous_balance") or 0) + (summary["purchases"] or 0)
            - (summary.get("payments_credits") or 0)
            + (summary.get("finance_charges") or 0), 2)

    # ---- transactions --------------------------------------------------
    txns = []
    section = "Domestic"
    cardholder = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        sec = _hdfc_section(raw)
        if sec:
            section = sec
            i += 1
            continue
        mt = _HDFC_TXN.match(raw.strip())
        if not mt:
            if _is_cardholder(raw):
                cardholder = raw.strip()
            i += 1
            continue
        date_s, time_s, rest = mt.groups()
        # join wrapped continuation lines until we find the trailing amount
        buf = rest
        j = i + 1
        while not _HDFC_AMT.search(buf) and j < len(lines):
            nxt = lines[j].strip()
            if _HDFC_TXN.match(nxt) or _hdfc_section(nxt) or _is_cardholder(nxt):
                break
            buf = (buf + " " + nxt).strip()
            j += 1
        am = _HDFC_AMT.search(buf)
        if not am:
            i += 1
            continue
        amount = _to_float(am.group(1))
        # HDFC marks credits/reversals with a lone "+" right before the amount
        # ("+ C 83,329.00"), an explicit "Cr", or a payment/credit keyword.
        lone_plus = bool(re.search(r"\+\s*[C₹`]\s*[\d,]+\.\d{2}\s*l?\s*$", buf))
        is_credit = bool(am.group(2)) or lone_plus or bool(_HDFC_CREDIT_KW.search(buf))
        body = buf[:am.start()].strip()
        i = j
        # HDFC often orphans the Ref# digits on the following line:
        #   "...-RATE 18.0 -27 (Ref# C 36.90 l"  /  "09999999980517014966299)"
        if "(Ref#" in body and ")" not in body and i < len(lines):
            orphan = re.match(r"^([0-9A-Z]+)\)\s*$", lines[i].strip())
            if orphan:
                body = body.replace("(Ref#", "(Ref# " + orphan.group(1) + ")")
                i += 1

        d, mth, y = date_s.split("/")
        txn = _build_txn(
            txn_date=_iso_dmy(d, mth, y), txn_time=time_s,
            body=body, amount=amount, is_credit=is_credit,
            section=section, cardholder=cardholder, bank="HDFC")
        if txn["amount"] is not None:
            txns.append(txn)

    return {
        "bank": "HDFC", "card_last4": last4 or "----", "card_label": label,
        "statement_date": stmt_date, "period_start": period_start,
        "period_end": period_end, "due_date": due_date,
        "summary": summary, "transactions": txns, "file_name": file_name,
    }


def _build_txn(*, txn_date, txn_time, body, amount, is_credit, section,
               cardholder, bank, reward_points=None, foreign_amount=None,
               foreign_currency=None):
    # Reward markers like "+ 15" / "- 1120" embedded in HDFC body
    ref = None
    mref = re.search(r"\(Ref#\s*([^)]+)\)", body)
    if mref:
        ref = mref.group(1).strip()
        body = body[:mref.start()].strip()
    # drop any leftover unclosed "(Ref#" fragment
    body = re.sub(r"\(Ref#.*$", "", body).strip()
    if reward_points is None:
        mr = re.search(r"([+-])\s*(\d{1,5})\b", body)
        if mr:
            reward_points = int(mr.group(2)) * (1 if mr.group(1) == "+" else -1)
    # strip reward markers and trailing currency tokens from the merchant text
    body = re.sub(r"[+-]\s*\d{1,5}\b", " ", body)
    # international foreign amount tokens, e.g. "USD 5.00" / "THB 287.00"
    if foreign_amount is None:
        mf = re.search(r"\b(" + "|".join(_FX) + r")\s+([\d,]+\.?\d*)", body)
        if mf:
            foreign_currency = mf.group(1)
            foreign_amount = _to_float(mf.group(2))
            body = (body[:mf.start()] + " " + body[mf.end():]).strip()
    is_emi = bool(re.match(r"^(EMI|MER EMI|OFFUS EMI|CT |MMT |EMT )", body.strip(), re.I)) \
        or body.strip().upper().startswith("EMI")
    body = re.sub(r"\s*[+\-]\s*$", "", body)
    desc = re.sub(r"\s{2,}", " ", body).strip(" -|+").strip()
    merchant, city = _split_merchant_city(desc)

    from categorize import categorise
    return {
        "txn_date": txn_date, "txn_time": txn_time, "description": desc or "(unknown)",
        "merchant": merchant, "city": city, "amount": amount,
        "direction": "credit" if is_credit else "debit",
        "currency": "INR", "foreign_amount": foreign_amount,
        "foreign_currency": foreign_currency, "section": section,
        "cardholder": cardholder, "reward_points": reward_points,
        "ref_no": ref, "is_emi": is_emi,
        "category": categorise(desc, is_credit),
        "bank": bank,
    }


_CITY_HINTS = ["MUMBAI", "BANGALORE", "BENGALURU", "GURGAON", "NEW DELHI",
               "DELHI", "CHENNAI", "HYDERABAD", "PUNE", "KOLKATA", "NOIDA",
               "AHMEDABAD", "BANGKOK", "SAMUTPRAKAN", "PHUKET", "PATHU",
               "WANGMAI", "LUMPHINI", "MAHARASHTRA"]


def _split_merchant_city(desc):
    if not desc:
        return desc, None
    up = desc.upper()
    for c in _CITY_HINTS:
        idx = up.rfind(c)
        if idx > 0:
            return desc[:idx].strip(), desc[idx:idx + len(c)].title()
    return desc, None


def _after(text, label):
    m = re.search(label + r"\s*[:\-]?\s*\n?\s*([A-Za-z0-9 ,]+)", text)
    return m.group(1) if m else None


def _amt_after(text, label):
    m = re.search(label + r"\s*[:\-]?\s*\n?\s*[C₹`]?\s*([\d,]+\.\d{2})",
                  text, re.I)
    return _to_float(m.group(1)) if m else None


def _hdfc_summary_row(text, idx):
    """The 4-value row: prev dues / payments / purchases / finance charges."""
    m = re.search(r"PREVIOUS STATEMENT DUES.*?FINANCE CHARGES\s*\n"
                  r"([C₹`][\d,]+\.\d{2})\s+([C₹`][\d,]+\.\d{2})\s+"
                  r"([C₹`][\d,]+\.\d{2})\s+([C₹`][\d,]+\.\d{2})",
                  text, re.S)
    if not m:
        return None
    return _to_float(m.group(idx + 1))


# ---------------------------------------------------------------------------
# ICICI
# ---------------------------------------------------------------------------

_ICICI_TXN = re.compile(r"(\d{2}/\d{2}/\d{4})\s+(\d{8,})\s+(.*)$")
_DEC = re.compile(r"[\d,]+\.\d{2}")
_INTL_MARK = re.compile(r"\b[A-Z]{2}\*")
_CONT_OK = re.compile(r"^[\d,A-Z*&.\s/-]+$")


def parse_icici(pages, file_name=""):
    text = "\n".join(pages)
    summary = {}

    last4 = None
    m = re.search(r"(\d{4}[X]{4,}\d{4})", text)
    if m:
        last4 = re.sub(r"[^\d]", "", m.group(1))[-4:]

    stmt_date = _iso_from_text_date(_after(text, r"STATEMENT DATE"))
    period = re.search(r"Statement period\s*:\s*([A-Za-z]+ \d{1,2}, \d{4})\s*to\s*"
                       r"([A-Za-z]+ \d{1,2}, \d{4})", text)
    period_start = _iso_from_text_date(period.group(1)) if period else None
    period_end = _iso_from_text_date(period.group(2)) if period else None
    due = re.search(r"PAYMENT DUE DATE.*?\n.*?([A-Za-z]+ \d{1,2}, \d{4})",
                    text, re.S)
    due_date = _iso_from_text_date(due.group(1)) if due else None
    if not stmt_date:
        # statement date is the 2nd date on the page header block
        ds = re.findall(r"([A-Za-z]+ \d{1,2}, \d{4})", text)
        if len(ds) >= 2:
            due_date = due_date or _iso_from_text_date(ds[0])
            stmt_date = _iso_from_text_date(ds[1])

    # bottom summary line is the reliable source
    sm = re.search(r"Previous Balance\s+Purchases\s*/\s*Charges\s+Cash Advances\s+"
                   r"Payments\s*/\s*Credits\s*\n[`₹]?([\d,]+\.\d{2})\s+"
                   r"[`₹]?([\d,]+\.\d{2})\s+[`₹]?([\d,]+\.\d{2})\s+"
                   r"[`₹]?([\d,]+\.\d{2})", text)
    if sm:
        summary["previous_balance"] = _to_float(sm.group(1))
        summary["purchases"] = _to_float(sm.group(2))
        summary["cash_advances"] = _to_float(sm.group(3))
        summary["payments_credits"] = _to_float(sm.group(4))
        summary["total_due"] = round(
            (summary["previous_balance"] or 0) + (summary["purchases"] or 0)
            + (summary["cash_advances"] or 0) - (summary["payments_credits"] or 0), 2)
    summary.setdefault("finance_charges", None)
    # Total / minimum due appear as an adjacent pair of back-tick values in the
    # credit-summary box, e.g.  `20,860.00\n`2,39,602.82
    pair = re.search(r"`([\d,]+\.\d{2})\s*\n`([\d,]+\.\d{2})", text)
    if pair:
        a, b = _to_float(pair.group(1)), _to_float(pair.group(2))
        summary["min_due"] = min(a, b)
        summary.setdefault("total_due", max(a, b))
    else:
        summary.setdefault("total_due", None)
        summary.setdefault("min_due", None)

    label = "ICICI Sapphiro Credit Card" if "sapphiro" in (file_name or "").lower() \
        else "ICICI Credit Card"

    # ---- transactions --------------------------------------------------
    txns = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        mt = _ICICI_TXN.search(lines[i])
        if not mt:
            i += 1
            continue
        date_s, serno, rest = mt.groups()
        buf = rest.strip()
        j = i + 1
        while not _icici_complete(buf) and j < len(lines):
            nxt = lines[j].strip()
            if _ICICI_TXN.search(nxt) or not _CONT_OK.match(nxt) or len(nxt) > 60:
                break
            buf = (buf + " " + nxt).strip()
            j += 1
        i = j if j > i + 1 else i + 1

        txn = _parse_icici_body(date_s, serno, buf)
        if txn:
            txns.append(txn)

    return {
        "bank": "ICICI", "card_last4": last4 or "----", "card_label": label,
        "statement_date": stmt_date, "period_start": period_start,
        "period_end": period_end, "due_date": due_date,
        "summary": summary, "transactions": txns, "file_name": file_name,
    }


def _icici_complete(buf):
    """A buffer is a complete txn when it ends with an INR amount, and for
    international rows only after the foreign currency code has appeared."""
    bs = buf.strip().rstrip("R").rstrip("C").strip()  # tolerate trailing 'CR'
    if not re.search(r"[\d,]+\.\d{2}\s*(CR)?$", buf.strip()):
        return False
    if _INTL_MARK.search(buf):
        # need a foreign currency token before the final number
        return any(fx in buf for fx in _FX)
    return True


def _parse_icici_body(date_s, serno, buf):
    d, m, y = date_s.split("/")
    txn_date = _iso_dmy(d, m, y)
    is_credit = bool(re.search(r"\bCR\b\s*$", buf))
    body = re.sub(r"\bCR\b\s*$", "", buf).strip()

    nums = list(_DEC.finditer(body))
    intl = _INTL_MARK.search(body)
    foreign_amount = foreign_currency = reward_points = None
    section = "International" if intl else "Domestic"

    if not nums:
        return None
    amount = _to_float(nums[-1].group(0))      # INR is always the last decimal

    if intl:
        fxm = re.search(r"\b(" + "|".join(_FX) + r")\b", body)
        if fxm:
            foreign_currency = fxm.group(1)
        # reward points: integer right after the country marker
        rp = re.search(r"[A-Z]{2}\*\s+(\d{1,5})\b", body)
        if rp:
            reward_points = int(rp.group(1))
        # foreign amount: number just before currency code / last-but-one
        fa = re.search(r"[A-Z]{2}\*\s+\d{1,5}\s+([\d,]*\.?\d+)", body)
        if fa:
            foreign_amount = _to_float(fa.group(1) if "." in fa.group(1)
                                       else fa.group(1) + ".00")
        cut = body[:intl.start()].strip()
    else:
        # domestic: "... IN <points> <amount>"
        rp = re.search(r"\bIN\b\s+(\d{1,5})\s+[\d,]+\.\d{2}\s*$", body)
        if rp:
            reward_points = int(rp.group(1))
        cut = re.sub(r"\bIN\b\s+\d{1,5}\s+[\d,]+\.\d{2}\s*$", "", body).strip()
        cut = re.sub(r"\s+[\d,]+\.\d{2}\s*$", "", cut).strip()

    cut = re.sub(r"\b[A-Z]{2}\*", "", cut).strip()
    desc = re.sub(r"\s{2,}", " ", cut).strip()
    is_emi = "emi" in desc.lower()
    merchant, city = _split_merchant_city(desc)

    from categorize import categorise
    return {
        "txn_date": txn_date, "txn_time": None,
        "description": desc or "(unknown)", "merchant": merchant, "city": city,
        "amount": amount, "direction": "credit" if is_credit else "debit",
        "currency": "INR", "foreign_amount": foreign_amount,
        "foreign_currency": foreign_currency, "section": section,
        "cardholder": None, "reward_points": reward_points,
        "ref_no": serno, "is_emi": is_emi,
        "category": categorise(desc, is_credit), "bank": "ICICI",
    }


# ---------------------------------------------------------------------------
# Axis (Neo / MY Zone and other consumer cards)
# ---------------------------------------------------------------------------
#
# Axis statements are laid out as a bordered table with four columns:
#   date | transaction details | amount (INR) | debit/credit
# pdfplumber's flat text stream is unreliable here because a long merchant name
# wraps to several physical lines that straddle the (vertically-centred) date /
# amount / direction row — e.g. "4384 BOOTS-SIAM PREMIUM" sits *above* the row
# and "O,SAMUTPRAKAN" *below* it. So we rebuild each row from word coordinates:
# every transaction has exactly one date triple, one amount and one Debit/Credit
# token sharing a y-position; the description is whichever detail-column words
# are vertically nearest that anchor row.

# Column x0 bands (points). The template is stable across Axis card variants.
_AX_DATE_MAXX = 130      # date column ends here
_AX_DESC_MINX = 130      # transaction-details column
_AX_DESC_MAXX = 345
_AX_AMT_MINX = 345       # amount column (₹ + number)
_AX_AMT_MAXX = 448
_AX_DIR_MINX = 448       # Debit / Credit column

_AX_DATE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3})\s+'(\d{2})$")
_AX_NUM = re.compile(r"^₹?\s*([\d,]+\.\d{2})$")
# Foreign cities/markers seen on Axis international spends (statement has no
# explicit Domestic/International section, so we infer it).
_AX_FOREIGN = ("BANGKOK", "SAMUTPRAKAN", "PHUKET", "PATTAYA", "CHIANG",
               "SINGAPORE", "DUBAI", "ABU DHABI", "LONDON", "PARIS", "NEW YORK",
               "BALI", "KUALA LUMPUR", "TOKYO", "HONG KONG", "COLOMBO",
               "KATHMANDU", "MALDIVES", "NUSA", "DENPASAR")


def _ax_date(day, mon, yy):
    m = _MONTHS.get(mon[:3].lower())
    if not m:
        return None
    return _iso_dmy(day, m, 2000 + int(yy))


def _ax_lines(words):
    """Cluster a page's words into visual rows by their `top` coordinate."""
    if not words:
        return []
    ws = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines, cur, cur_top = [], [], None
    for w in ws:
        if cur_top is None or abs(w["top"] - cur_top) <= 4:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append((cur_top, cur))
            cur, cur_top = [w], w["top"]
    if cur:
        lines.append((cur_top, cur))
    return lines


def parse_axis(pages, word_pages, file_name=""):
    text = "\n".join(pages)
    summary = {}

    # ---- card / variant / dates ---------------------------------------
    variant = "Credit"
    mv = re.search(r"Axis Bank\s+(.+?)\s+Card\s+Monthly Statement", text, re.I)
    if mv:
        variant = mv.group(1).strip()
    label = f"Axis {variant} Credit Card"

    last4 = None
    mc = re.search(r"Credit Card Number\s*:?\s*(\d{4}[X]{4,}\d{4})", text)
    if mc:
        last4 = re.sub(r"[^\d]", "", mc.group(1))[-4:]

    # Payment summary: "₹ <total due> ₹ <min due> <due date>"
    mp = re.search(r"Total Payment Due.*?\n\s*₹\s*([\d,]+\.\d{2})\s+"
                   r"₹\s*([\d,]+\.\d{2})\s+(\d{1,2}\s+[A-Za-z]{3}\s+'\d{2})",
                   text, re.S)
    due_date = None
    if mp:
        summary["total_due"] = _to_float(mp.group(1))
        summary["min_due"] = _to_float(mp.group(2))
        dm = _AX_DATE.match(mp.group(3).strip())
        if dm:
            due_date = _ax_date(*dm.groups())

    # "Jun 2026   ₹ <credit limit>   ₹ <opening balance>"
    stmt_month = None
    mo = re.search(r"Selected Statement Month.*?\n\s*([A-Za-z]{3,}\s+\d{4})\s+"
                   r"₹\s*([\d,]+\.\d{2})\s+₹\s*([\d,]+\.\d{2})", text, re.S)
    if mo:
        stmt_month = mo.group(1).strip()
        summary["previous_balance"] = _to_float(mo.group(3))   # opening balance
    summary.setdefault("previous_balance", None)

    # statement date: explicit "Date: DD/MM/YYYY" (loan page) else month start
    stmt_date = None
    md = re.search(r"Date\s*:\s*(\d{2})/(\d{2})/(\d{4})", text)
    if md:
        stmt_date = _iso_dmy(md.group(1), md.group(2), md.group(3))
    elif stmt_month:
        mm = re.match(r"([A-Za-z]{3,})\s+(\d{4})", stmt_month)
        if mm:
            mon = _MONTHS.get(mm.group(1)[:3].lower())
            if mon:
                stmt_date = _iso_dmy(1, mon, mm.group(2))

    # ---- transactions (coordinate-based) ------------------------------
    txns = []
    for words in word_pages:
        lines = _ax_lines(words)
        anchors = []   # (top, amount, is_credit, txn_date)
        for top, lws in lines:
            date_txt = " ".join(w["text"] for w in lws
                                if w["x0"] < _AX_DATE_MAXX).strip()
            dm = _AX_DATE.match(date_txt)
            amt = None
            for w in lws:
                if _AX_AMT_MINX <= w["x0"] < _AX_AMT_MAXX:
                    nm = _AX_NUM.match(w["text"])
                    if nm:
                        amt = _to_float(nm.group(1))
            direction = None
            for w in lws:
                if w["x0"] >= _AX_DIR_MINX and w["text"] in ("Debit", "Credit"):
                    direction = w["text"]
            # A real transaction row carries all three: date, amount, direction.
            if dm and amt is not None and direction:
                anchors.append({"top": top, "amount": amt,
                                "is_credit": direction == "Credit",
                                "txn_date": _ax_date(*dm.groups())})
        if not anchors:
            continue

        # Assign every detail-column word to its vertically-nearest anchor row.
        tops = [a["top"] for a in anchors]
        lo, hi = min(tops), max(tops)
        buckets = {a["top"]: [] for a in anchors}
        for w in words:
            if not (_AX_DESC_MINX <= w["x0"] < _AX_DESC_MAXX):
                continue
            if not (lo - 14 <= w["top"] <= hi + 14):
                continue
            nearest = min(anchors, key=lambda a: abs(a["top"] - w["top"]))
            if abs(nearest["top"] - w["top"]) <= 14:
                buckets[nearest["top"]].append(w)

        for a in anchors:
            dws = sorted(buckets[a["top"]], key=lambda w: (round(w["top"], 1), w["x0"]))
            desc = re.sub(r"\s{2,}", " ", " ".join(w["text"] for w in dws)).strip()
            txns.append(_build_axis_txn(a["txn_date"], desc, a["amount"],
                                        a["is_credit"]))

    # purchases / payments are the parsed debit & credit sums (reconciles 1:1)
    summary["purchases"] = round(sum(t["amount"] for t in txns
                                     if t["direction"] == "debit"), 2)
    summary["payments_credits"] = round(sum(t["amount"] for t in txns
                                            if t["direction"] == "credit"), 2)
    summary.setdefault("cash_advances", 0.0)
    summary.setdefault("finance_charges", None)
    summary.setdefault("total_due", None)
    summary.setdefault("min_due", None)

    return {
        "bank": "AXIS", "card_last4": last4 or "----", "card_label": label,
        "statement_date": stmt_date, "period_start": None,
        "period_end": stmt_date, "due_date": due_date,
        "summary": summary, "transactions": txns, "file_name": file_name,
    }


def _build_axis_txn(txn_date, desc, amount, is_credit):
    ref = None
    mref = re.search(r"#(\S+)", desc)
    if mref:
        ref = mref.group(1)
        desc = (desc[:mref.start()] + desc[mref.end():]).strip()
    desc = re.sub(r"\s{2,}", " ", desc).strip(" ,")
    merchant, city = _axis_merchant_city(desc)
    up = desc.upper()
    section = "International" if (
        (city and city.upper() in _AX_FOREIGN) or "FOREIGN CURRENCY" in up
    ) else "Domestic"
    is_emi = "emi" in desc.lower()

    from categorize import categorise
    return {
        "txn_date": txn_date, "txn_time": None,
        "description": desc or "(unknown)", "merchant": merchant, "city": city,
        "amount": amount, "direction": "credit" if is_credit else "debit",
        "currency": "INR", "foreign_amount": None, "foreign_currency": None,
        "section": section, "cardholder": None, "reward_points": None,
        "ref_no": ref, "is_emi": is_emi,
        "category": categorise(desc, is_credit), "bank": "AXIS",
    }


def _axis_merchant_city(desc):
    """Axis prints details as 'MERCHANT,CITY' — split on the last comma."""
    if not desc or "," not in desc:
        return desc or None, None
    merchant, city = desc.rsplit(",", 1)
    merchant, city = merchant.strip(), city.strip()
    # A trailing comma fragment with no real city -> keep whole as merchant.
    if not city or not re.search(r"[A-Za-z]", city):
        return desc, None
    return merchant or desc, city.title()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_statement(path, password=None, file_name=None):
    pages, word_pages = _read_doc(path, password=password)
    bank = detect_bank(pages)
    fn = file_name or (path if isinstance(path, str) else "statement.pdf")
    if bank == "AXIS":
        return parse_axis(pages, word_pages, file_name=fn)
    if bank == "ICICI":
        return parse_icici(pages, file_name=fn)
    return parse_hdfc(pages, file_name=fn)
