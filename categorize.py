"""Keyword-based auto-categorisation for credit-card transactions.

The user can always override the category in the ledger; this only provides a
sensible default at import time.
"""
import re

# Ordered list — first matching rule wins.
CATEGORIES = [
    "Payments & Credits",
    "Fees, Taxes & Interest",
    "Groceries",
    "Food & Dining",
    "Travel",
    "Hotels",
    "Shopping",
    "Jewellery",
    "Entertainment",
    "Health",
    "Fuel",
    "Utilities & Bills",
    "Cash & EMI",
    "Uncategorised",
]

_RULES = [
    ("Payments & Credits", r"\b(payment received|bbps payment|cc payment|bppy|neft|imps|upi.*received|received|reversal|refund|cashback|credit)\b"),
    ("Fees, Taxes & Interest", r"\b(igst|cgst|sgst|gst|markup|finance charge|interest|late payment|surcharge|fee|annual charge|tax)\b"),
    ("Groceries", r"\b(zepto|blinkit|bigbasket|big basket|grofers|dmart|d-mart|reliance fresh|fresh|grocery|instamart|jiomart|amazon in grocery|freshpik|licious|amrit)\b"),
    ("Food & Dining", r"\b(swiggy|zomato|eternal|dineout|restaurant|cafe|coffee|starbucks|dominos|mcdonald|kfc|pizza|food|kitchen|bakery|dine|barbeque|din tai fung|saffron|toast|massage food|madras|darbar|thai)\b"),
    ("Hotels", r"\b(hotel|oyo|marriott|hyatt|taj|itc|continent|resort|stay|airbnb|standard\b)\b"),
    ("Travel", r"\b(makemytrip|mmt|smartbuy|goibibo|cleartrip|ixigo|flight|emt|air ?india|indigo|vistara|irctc|uber|ola|grab|rapido|bts|metro|airport lounge|loungeone|lounge|dtac|akbar|yatra)\b"),
    ("Shopping", r"\b(amazon|flipkart|myntra|ajio|zara|westside|adidas|nike|uniqlo|hm\b|h&m|store|mall|shop|sportskart|jd sports|burberry|calvin klein|sephora|eveandboy|boots|sapphire|trend|gift shop|premium outle|decathlon|reliance digital|croma)\b"),
    ("Jewellery", r"\b(jewell|tanishq|kalyan|malabar|tissot|watch|bvlgari|cartier|gold)\b"),
    ("Entertainment", r"\b(bookmyshow|netflix|spotify|youtube|google ?play|prime video|hotstar|pvr|inox|cinema|movie|game|playstation)\b"),
    ("Health", r"\b(pharma|apollo|hospital|clinic|hiranandani|medico|chemist|1mg|pharmeasy|netmeds|diagnostic|health|spa|wellness)\b"),
    ("Fuel", r"\b(fuel|petrol|hpcl|iocl|bpcl|indian oil|bharat petroleum|hp\b|shell|gas station)\b"),
    ("Utilities & Bills", r"\b(electricity|water bill|broadband|airtel|jio|vodafone|vi\b|bsnl|recharge|dth|tata power|adani|bescom|mseb|gas bill|insurance|lic\b|ergo|lombard)\b"),
    ("Cash & EMI", r"\b(cash advance|atm|emi|loan|offus|mer emi|instal)\b"),
]


def categorise(description: str, is_credit: bool = False) -> str:
    d = (description or "").lower()
    if is_credit:
        # Payments are credits, but a refund/reversal credit is still "Payments & Credits".
        for cat, pat in _RULES:
            if cat == "Payments & Credits" and re.search(pat, d):
                return cat
        return "Payments & Credits"
    for cat, pat in _RULES:
        if re.search(pat, d):
            return cat
    return "Uncategorised"
