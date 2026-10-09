from io import BytesIO
from pathlib import Path

from flask import current_app, jsonify, render_template, request, send_file
from openpyxl import Workbook

from . import landing_v2
from .calculator import SUPPORTED_CURRENCIES, calculate_landing_price
from .database import get_active_charge_config
from .digikey_api import DigiKeyAPIError, lookup_product_details
from .excel_import import (
    MAX_IMPORT_ROWS,
    SUPPORTED_UPLOAD_FORMATS,
    inspect_upload,
    normalize_upload,
)
from .master_lookup import add_master_records, list_master_records, lookup_mpn


MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@landing_v2.get("/landing/v2")
def calculator_page():
    return render_template(
        "landing_price_v2.html",
        currencies=sorted(SUPPORTED_CURRENCIES),
        charges=get_active_charge_config(),
    )


@landing_v2.get("/api/landing/v2/config")
def landing_config():
    return jsonify(
        {
            "ok": True,
            "currencies": sorted(SUPPORTED_CURRENCIES),
            "charges": get_active_charge_config(),
        }
    )


@landing_v2.get("/api/landing/v2/product/<path:mpn>")
def product_lookup(mpn):
    product = lookup_mpn(mpn)
    if product is None:
        return jsonify({"found": False, "mpn": " ".join(mpn.split())})
    return jsonify(
        {
            "found": True,
            "mpn": product["mpn"],
            "category": product["category"],
            "hsn": product["hsn_code"],
            "bcd": float(product["bcd_rate"]),
            "sws": float(product["sws_rate"]),
            "source": product["source"],
        }
    )


@landing_v2.get("/api/landing/v2/digikey-product/<path:mpn>")
def digikey_product_lookup(mpn):
    """Fetch manufacturer, category and description without exposing credentials."""
    normalized_mpn = " ".join(mpn.split())
    if not normalized_mpn:
        return jsonify({"found": False, "mpn": ""})
    requested_currency = request.args.get("currency", "").strip().upper()
    if requested_currency and requested_currency not in SUPPORTED_CURRENCIES:
        return jsonify({"ok": False, "error": "DigiKey price currency must be USD or INR."}), 400
    try:
        result = lookup_product_details(normalized_mpn, requested_currency=requested_currency or None)
    except DigiKeyAPIError as exc:
        current_app.logger.warning("DigiKey product lookup failed: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        current_app.logger.exception("DigiKey product lookup failed")
        return jsonify({"ok": False, "error": "DigiKey product lookup is temporarily unavailable."}), 502
    return jsonify({"found": bool(result["matches"]), "mpn": normalized_mpn, **result})


@landing_v2.post("/api/landing/v2/master")
def create_master_products():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Send product details as JSON."}), 400
    records = payload.get("items")
    if records is None:
        records = [payload]
    if not isinstance(records, list) or not records:
        return jsonify({"ok": False, "error": "At least one product record is required."}), 400
    if len(records) > MAX_IMPORT_ROWS or any(not isinstance(item, dict) for item in records):
        return jsonify({"ok": False, "error": "Invalid product record list."}), 400
    try:
        result = add_master_records(records)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": True, **result})


@landing_v2.get("/api/landing/v2/master/export")
def export_master_products():
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("DigiKey Master")
    worksheet.append(["MPN", "Category", "HSN / CTSH", "BCD (%)", "SWS (%)", "Source"])
    for record in list_master_records():
        worksheet.append(
            [
                record["mpn"],
                record["category"],
                record["hsn_code"],
                float(record["bcd_rate"]),
                float(record["sws_rate"]),
                record["source"],
            ]
        )
    content = BytesIO()
    workbook.save(content)
    content.seek(0)
    return send_file(
        content,
        as_attachment=True,
        download_name="digikey-master.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@landing_v2.post("/api/landing/v2/import-excel")
def import_excel():
    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"ok": False, "error": "Excel uploads are limited to 10 MB."}), 413
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "Choose an Excel workbook to upload."}), 400
    suffix = Path(upload.filename).suffix.casefold()
    if suffix not in SUPPORTED_UPLOAD_FORMATS:
        return jsonify({"ok": False, "error": "Upload an .xlsx, .xls, .csv, .tsv, .txt, or text-based .pdf BOM file."}), 400

    selection = {}
    for key in ("sheet", "header_row", "mpn_column", "unit_price_column", "quantity_column", "currency_column"):
        value = request.form.get(key)
        if value is not None and value != "":
            selection[key] = value
    if request.form.get("default_currency"):
        selection["default_currency"] = request.form["default_currency"].strip().upper()

    try:
        workbook_stream = normalize_upload(upload.stream, upload.filename)
        imported = inspect_upload(workbook_stream, selection or None)
        if imported.get("needs_selection"):
            imported["ok"] = True
            return jsonify(imported)
        if len(imported["items"]) > MAX_IMPORT_ROWS:
            raise ValueError(f"Excel files are limited to {MAX_IMPORT_ROWS} line items.")
        for item in imported["items"]:
            if item["currency"] not in SUPPORTED_CURRENCIES:
                raise ValueError(
                    f"Unsupported currency '{item['currency']}'. Imported prices must be USD or INR."
                )
            product = lookup_mpn(item["mpn"])
            item["master"] = (
                {
                    "found": True,
                    "category": product["category"],
                    "hsn": product["hsn_code"],
                    "bcd": float(product["bcd_rate"]),
                    "sws": float(product["sws_rate"]),
                }
                if product
                else {"found": False}
            )
        imported["ok"] = True
        return jsonify(imported)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        current_app.logger.warning("Unable to read uploaded landing calculator workbook: %s", exc)
        return jsonify({"ok": False, "error": "Could not read the uploaded .xlsx workbook."}), 400


@landing_v2.post("/api/landing/v2/calculate")
def calculate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "Send calculation inputs as JSON."}), 400
    try:
        result = calculate_landing_price(payload, get_active_charge_config())
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if result.get("missing_mpns"):
        return jsonify(result), 422
    return jsonify(result)
