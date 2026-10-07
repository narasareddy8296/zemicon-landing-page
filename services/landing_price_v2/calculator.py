from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP

from .master_lookup import lookup_mpn


CENT = Decimal("0.01")
RUPEE = Decimal("1")
SUPPORTED_CURRENCIES = {"INR", "USD"}
USD_RATE_ADJUSTMENT = Decimal("1.02")
DEFAULT_SWS_RATE = Decimal("10")
INSURANCE_RATE = Decimal("0.01125")


def _decimal(value, field, *, minimum=None, allow_zero=True):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if not number.is_finite() or (minimum is not None and number < minimum):
        raise ValueError(f"{field} must be at least {minimum}.")
    if not allow_zero and number <= 0:
        raise ValueError(f"{field} must be greater than zero.")
    return number


def _money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _percentage(value, field):
    rate = _decimal(value, field, minimum=Decimal("0"))
    if rate > Decimal("100"):
        raise ValueError(f"{field} must be between 0% and 100%.")
    return rate


def _bool(value, field):
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"yes", "true", "1"}:
            return True
        if normalized in {"no", "false", "0"}:
            return False
    raise ValueError(f"{field} must be Yes or No.")


def _allocate(amount, weights):
    amount = _money(amount)
    if not weights:
        return []
    total_weight = sum(weights, Decimal("0"))
    if total_weight <= 0:
        weights = [Decimal("1")] * len(weights)
        total_weight = Decimal(len(weights))
    total_cents = int((amount / CENT).to_integral_value(rounding=ROUND_HALF_UP))
    raw_cents = [Decimal(total_cents) * weight / total_weight for weight in weights]
    allocated_cents = [int(value.to_integral_value(rounding=ROUND_DOWN)) for value in raw_cents]
    remainder = total_cents - sum(allocated_cents)
    order = sorted(
        range(len(weights)),
        key=lambda index: (raw_cents[index] - allocated_cents[index], -index),
        reverse=True,
    )
    for index in order[:remainder]:
        allocated_cents[index] += 1
    return [CENT * cents for cents in allocated_cents]


def calculate_landing_price(payload, config):
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("At least one line item is required.")

    lines = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Line {index} must be an object.")
        mpn = " ".join(str(item.get("mpn", "") or "").split())
        if not mpn:
            raise ValueError(f"MPN is required on line {index}.")
        quantity = _decimal(item.get("quantity"), f"Quantity for {mpn}", minimum=Decimal("0"), allow_zero=False)
        unit_price = _decimal(item.get("unit_price"), f"Unit price for {mpn}", minimum=Decimal("0"))
        currency = str(item.get("currency", payload.get("currency", "INR")) or "").strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency '{currency}' for {mpn}. Choose USD or INR.")
        if currency == "INR":
            exchange_rate = Decimal("1")
            live_exchange_rate = None
        else:
            raw_rate = item.get("live_exchange_rate")
            if raw_rate in (None, ""):
                raise ValueError("Enter the live interbank USD/INR exchange rate.")
            live_exchange_rate = _decimal(
                raw_rate,
                "Live interbank USD/INR exchange rate",
                minimum=Decimal("0"),
                allow_zero=False,
            )
            exchange_rate = live_exchange_rate * USD_RATE_ADJUSTMENT
        product = lookup_mpn(mpn)
        if product is None:
            category = " ".join(str(item.get("category", "") or "").split())
            bcd_rate = _percentage(item.get("bcd_rate"), f"BCD rate for {mpn}")
            sws_rate = _percentage(
                item.get("sws_rate", DEFAULT_SWS_RATE),
                f"SWS rate for {mpn}",
            )
            source = "Manually entered (MPN not in DigiKey master)"
            hsn_code = ""
        else:
            category = product["category"]
            bcd_rate = Decimal(product["bcd_rate"])
            sws_rate = Decimal(product["sws_rate"])
            source = product["source"]
            hsn_code = product["hsn_code"]
        line_invoice = _money(quantity * unit_price * exchange_rate)
        line_invoice_currency = _money(quantity * unit_price)
        lines.append(
            {
                "mpn": product["mpn"] if product else mpn,
                "category": category,
                "hsn": hsn_code,
                "bcd_rate": bcd_rate,
                "sws_rate": sws_rate,
                "quantity": quantity,
                "unit_price": unit_price,
                "currency": currency,
                "live_exchange_rate_inr": live_exchange_rate,
                "exchange_rate_inr": exchange_rate,
                "line_invoice_currency": line_invoice_currency,
                "line_invoice_inr": line_invoice,
                "source": source,
            }
        )

    total_invoice = sum((line["line_invoice_inr"] for line in lines), Decimal("0"))
    allocation_weights = [line["line_invoice_inr"] for line in lines]
    if total_invoice <= 0:
        allocation_weights = [line["quantity"] for line in lines]

    threshold = Decimal(config["DIGIKEY_FREE_SHIPPING_THRESHOLD_INR"])
    international_freight = (
        Decimal(config["DIGIKEY_INTERNATIONAL_FREIGHT_INR"])
        if total_invoice < threshold
        else Decimal("0")
    )
    remittance = (
        Decimal(config["REMITTANCE_CHARGE_INR"])
        if _bool(payload.get("remittance_applicable", False), "Remittance applicability")
        else Decimal("0")
    )
    cha = (
        Decimal(config["CHA_PORT_DUES_INR"])
        if _bool(payload.get("cha_applicable", False), "CHA applicability")
        else Decimal("0")
    )
    domestic = (
        Decimal(config["DOMESTIC_TRUCKING_INR"])
        if _bool(payload.get("domestic_trucking_applicable", False), "Domestic trucking applicability")
        else Decimal("0")
    )
    shipment_charges = {
        "international_freight": _money(international_freight),
        "remittance": _money(remittance),
        "cha_port_dues": _money(cha),
        "domestic_trucking": _money(domestic),
    }
    allocated = {
        key: _allocate(amount, allocation_weights)
        for key, amount in shipment_charges.items()
    }
    other_charges_total = _money(
        _decimal(payload.get("other_charges_total", 0), "Other charges", minimum=Decimal("0"))
    )
    allocated["other_charges"] = _allocate(other_charges_total, allocation_weights)

    igst_enabled = _bool(payload.get("igst_enabled", False), "IGST option")
    margin_rate = _percentage(payload.get("margin_percent", 0), "Margin percentage")
    if margin_rate >= Decimal("100"):
        raise ValueError("Margin percentage must be less than 100%.")
    igst_rate = Decimal(config["IGST_RATE_PERCENT"])

    result_lines = []
    for index, line in enumerate(lines):
        charges = {
            key: values[index]
            for key, values in allocated.items()
        }
        insurance = _money(line["line_invoice_inr"] * INSURANCE_RATE)
        assessable_value = _money(
            line["line_invoice_inr"] + insurance + charges["international_freight"]
        )
        bcd_amount = (
            assessable_value * line["bcd_rate"] / Decimal("100")
        ).quantize(RUPEE, rounding=ROUND_HALF_UP)
        sws_amount = _money(bcd_amount * line["sws_rate"] / Decimal("100"))
        base_landed = _money(
            line["line_invoice_inr"]
            + insurance
            + sum(charges.values(), Decimal("0"))
            + bcd_amount
            + sws_amount
        )
        per_unit_landing = _money(base_landed / line["quantity"])
        margin_amount = _money(base_landed * margin_rate / Decimal("100"))
        margin_inclusive = _money(base_landed + margin_amount)
        per_unit_selling = _money(margin_inclusive / line["quantity"])
        igst_amount = _money(margin_inclusive * igst_rate / Decimal("100")) if igst_enabled else Decimal("0")
        final_with_igst = _money(margin_inclusive + igst_amount) if igst_enabled else None

        result_line = {
            "mpn": line["mpn"],
            "quantity": float(line["quantity"]),
            "unit_price": float(line["unit_price"]),
            "unit_price_inr": float(_money(line["unit_price"] * line["exchange_rate_inr"])),
            "currency": line["currency"],
            "live_exchange_rate_inr": (
                float(line["live_exchange_rate_inr"])
                if line["live_exchange_rate_inr"] is not None
                else None
            ),
            "exchange_rate_inr": float(line["exchange_rate_inr"]),
            "line_invoice_currency": float(line["line_invoice_currency"]),
            "line_invoice_inr": float(line["line_invoice_inr"]),
            "insurance": float(insurance),
            "assessable_value": float(assessable_value),
            "category": line["category"],
            "hsn": line["hsn"],
            "bcd_rate": float(line["bcd_rate"]),
            "bcd_amount": float(bcd_amount),
            "sws_rate": float(line["sws_rate"]),
            "sws_amount": float(sws_amount),
            **{key: float(value) for key, value in charges.items()},
            "base_landed_cost": float(base_landed),
            "per_unit_landing_price": float(per_unit_landing),
            "margin_percent": float(margin_rate),
            "margin_amount": float(margin_amount),
            "margin_inclusive_value": float(margin_inclusive),
            "per_unit_selling_price": float(per_unit_selling),
            "source": line["source"],
            "trace": [
                f"Product tariff source: {line['source']}.",
                f"Category: {line['category'] or 'Not provided'}; HSN/CTSH: {line['hsn'] or 'Not provided'}.",
                (
                    f"Live interbank rate {line['live_exchange_rate_inr']} INR/USD plus 2% "
                    f"gives {line['exchange_rate_inr']} INR/USD."
                    if line["currency"] == "USD"
                    else "Unit price entered in INR; exchange rate is 1."
                ),
                f"Quantity {line['quantity']} × unit price {line['unit_price']} {line['currency']} "
                f"= {line['line_invoice_currency']} {line['currency']}; at "
                f"{line['exchange_rate_inr']} INR/{line['currency']} = "
                f"₹{line['line_invoice_inr']}.",
                f"Insurance 1.125% of invoice INR: ₹{insurance}.",
                "Allocated shipment charges: "
                + ", ".join(f"{key.replace('_', ' ')} ₹{value}" for key, value in charges.items())
                + ".",
                f"Assessable value (invoice + insurance + allocated freight) ₹{assessable_value}.",
                f"BCD {line['bcd_rate']}% of assessable value: ₹{bcd_amount}.",
                f"SWS {line['sws_rate']}% of BCD: ₹{sws_amount}.",
                f"Base landed cost ₹{base_landed}; per-unit landing price ₹{per_unit_landing}.",
                f"Margin {margin_rate}% of landed cost: ₹{margin_amount}; selling value ₹{margin_inclusive}; per-unit selling price ₹{per_unit_selling}.",
            ],
        }
        if igst_enabled:
            result_line.update(
                {
                    "igst_rate": float(igst_rate),
                    "igst": float(igst_amount),
                    "final_price_including_igst": float(final_with_igst),
                    "per_unit_final_price_including_igst": float(
                        _money(final_with_igst / line["quantity"])
                    ),
                }
            )
        result_lines.append(result_line)

    totals = {
        "total_invoice_inr": _money(total_invoice),
        "insurance": _money(
            sum((Decimal(str(line["insurance"])) for line in result_lines), Decimal("0"))
        ),
        "assessable_value": _money(
            sum((Decimal(str(line["assessable_value"])) for line in result_lines), Decimal("0"))
        ),
        "international_freight": _money(international_freight),
        "remittance": _money(remittance),
        "cha_port_dues": _money(cha),
        "domestic_trucking": _money(domestic),
        "other_charges": other_charges_total,
        "total_shipment_charges": _money(
            sum(shipment_charges.values(), Decimal("0"))
            + sum(
                (Decimal(str(line["insurance"])) for line in result_lines),
                Decimal("0"),
            )
            + other_charges_total
        ),
        "base_landed_cost": _money(
            sum((Decimal(str(line["base_landed_cost"])) for line in result_lines), Decimal("0"))
        ),
        "margin_percent": margin_rate,
        "margin_amount": _money(
            sum((Decimal(str(line["margin_amount"])) for line in result_lines), Decimal("0"))
        ),
        "margin_inclusive_value": _money(
            sum(
                (Decimal(str(line["margin_inclusive_value"])) for line in result_lines),
                Decimal("0"),
            )
        ),
        "igst_enabled": igst_enabled,
        "free_shipping_threshold_inr": float(threshold),
    }
    if igst_enabled:
        totals["igst"] = _money(
            sum((Decimal(str(line["igst"])) for line in result_lines), Decimal("0"))
        )
        totals["final_price_including_igst"] = _money(
            sum(
                (Decimal(str(line["final_price_including_igst"])) for line in result_lines),
                Decimal("0"),
            )
        )
    return {
        "ok": True,
        "currency": "INR",
        "shipment_charges": {
            **{key: float(value) for key, value in shipment_charges.items()},
            "insurance": float(totals["insurance"]),
            "other_charges": float(other_charges_total),
        },
        "totals": {key: float(value) if isinstance(value, Decimal) else value for key, value in totals.items()},
        "items": result_lines,
    }
