import re
from decimal import Decimal, InvalidOperation

from flask import current_app

from .database import get_database


def normalize_mpn(value):
    return " ".join(str(value or "").split()).casefold()


def parse_rate(value, *, spreadsheet_fraction=False):
    raw = str(value if value is not None else "").strip()
    if not raw:
        raise ValueError("BCD and SWS rates are required.")
    has_percent = raw.endswith("%")
    raw = raw[:-1].strip() if has_percent else raw
    try:
        rate = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("BCD and SWS rates must be numeric percentages.") from exc
    if spreadsheet_fraction and not has_percent and Decimal("0") < rate <= Decimal("1"):
        rate *= Decimal("100")
    if not rate.is_finite() or not Decimal("0") <= rate <= Decimal("100"):
        raise ValueError("BCD and SWS rates must be between 0% and 100%.")
    return rate


def _format_hsn(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_master_record(record, *, source="User Added", spreadsheet_fraction=False):
    mpn = " ".join(str(record.get("mpn", "") or "").split())
    category = " ".join(str(record.get("category", "") or "").split())
    hsn = _format_hsn(record.get("hsn", record.get("hsn_code")))
    if not mpn:
        raise ValueError("MPN is required.")
    if not category:
        raise ValueError(f"Component category is required for {mpn}.")
    if not hsn or not re.fullmatch(r"[A-Za-z0-9-]{2,16}", hsn):
        raise ValueError(f"Valid HSN / CTSH is required for {mpn}.")
    bcd = parse_rate(record.get("bcd"), spreadsheet_fraction=spreadsheet_fraction)
    sws = parse_rate(record.get("sws"), spreadsheet_fraction=spreadsheet_fraction)
    return {
        "mpn": mpn,
        "mpn_norm": normalize_mpn(mpn),
        "category": category,
        "hsn_code": hsn,
        "bcd_rate": str(bcd),
        "sws_rate": str(sws),
        "source": source,
    }


def lookup_mpn(mpn):
    normalized = normalize_mpn(mpn)
    if not normalized:
        return None
    database = get_database()
    return database.execute(
        "SELECT mpn, category, hsn_code, bcd_rate, sws_rate, source "
        "FROM digikey_master WHERE mpn_norm = ?",
        (normalized,),
    ).fetchone()


def add_master_records(records):
    database = get_database()
    inserted = []
    existing = []
    with database:
        for record in records:
            normalized = normalize_master_record(record)
            cursor = database.execute(
                """
                INSERT OR IGNORE INTO digikey_master
                    (mpn_norm, mpn, category, hsn_code, bcd_rate, sws_rate, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized["mpn_norm"],
                    normalized["mpn"],
                    normalized["category"],
                    normalized["hsn_code"],
                    normalized["bcd_rate"],
                    normalized["sws_rate"],
                    normalized["source"],
                ),
            )
            (inserted if cursor.rowcount else existing).append(normalized["mpn"])
    return {"created": inserted, "already_present": existing}


def list_master_records():
    database = get_database()
    return database.execute(
        """
        SELECT mpn, category, hsn_code, bcd_rate, sws_rate, source
        FROM digikey_master
        ORDER BY mpn_norm
        """
    ).fetchall()
