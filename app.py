from flask import Flask, render_template, request, jsonify
from decimal import Decimal, ROUND_CEILING

app = Flask(__name__)

# Company rules supplied for this calculator.
INSURANCE_RATE = Decimal("0.01125")  # 1.125%
SWS_RATE = Decimal("0.10")            # 10% of BCD
IGST_RATE = Decimal("0.18")            # 18%

# DHL rate card: ZEMICON ELECTRONICS
# DHL Express Worldwide Export
# Ratecard as of 05-May-2026
# Values are INR.
COUNTRY_ZONES = {
    # Complete "DHL Express International Export Zoning & Import Zoning"
    # table from the supplied rate card, page 3.
    "Afghanistan": 10, "Albania": 7, "Algeria": 10, "American Samoa": 10,
    "Andorra": 7, "Angola": 10, "Anguilla": 10, "Antigua": 10,
    "Argentina": 9, "Armenia": 10, "Aruba": 10, "Australia": 6,
    "Austria": 7, "Azerbaijan": 10, "Bahamas": 10, "Bahrain": 4,
    "Bangladesh": 1, "Barbados": 10, "Belarus": 10, "Belgium": 7,
    "Belize": 10, "Benin": 10, "Bermuda": 10, "Bhutan": 1,
    "Bolivia": 9, "Bonaire": 10, "Bosnia & Herzegovina": 7, "Botswana": 10,
    "Brazil": 9, "Brunei": 5, "Bulgaria": 7, "Burkina Faso": 10,
    "Burundi": 10, "Cambodia": 5, "Cameroon": 10, "Canada": 8,
    "Canary Islands, The": 7, "Cape Verde": 10, "Cayman Islands": 10,
    "Central African Republic": 10, "Chad": 10, "Chile": 9, "China": 3,
    "Colombia": 9, "Comoros": 10, "Congo": 10, "Congo, DPR": 10,
    "Cook Islands": 10, "Costa Rica": 10, "Cote D Ivoire": 10,
    "Croatia": 7, "Cuba": 10, "Curacao": 10, "Cyprus": 7,
    "Czech Republic": 7, "Denmark": 7, "Djibouti": 10, "Dominica": 10,
    "Dominican Republic": 10, "Ecuador": 9, "Egypt": 10,
    "El Salvador": 10, "Eritrea": 10, "Estonia": 7, "Eswatini": 10,
    "Ethiopia": 10, "Falkland Islands": 10, "Faroe Islands": 10,
    "Fiji": 10, "Finland": 7, "France": 7, "French Guyana": 9,
    "Gabon": 10, "Gambia": 10, "Georgia": 10, "Germany": 7,
    "Ghana": 10, "Gibraltar": 7, "Greece": 7, "Greenland": 10,
    "Grenada": 10, "Guadeloupe": 10, "Guam": 10, "Guatemala": 10,
    "Guernsey": 7, "Guinea": 10, "Guinea-Bissau": 10,
    "Guinea-Equatorial": 10, "Guyana": 9, "Haiti": 10, "Honduras": 10,
    "Hong Kong SAR China": 2, "Hungary": 7, "Iceland": 10,
    "Indonesia": 5, "Iran": 10, "Iraq": 10, "Ireland": 7,
    "Israel": 7, "Italy": 7, "Jamaica": 10, "Japan": 5,
    "Jersey": 7, "Jordan": 4, "Kazakhstan": 10, "Kenya": 10,
    "Kiribati": 10, "Korea, Rep. Of": 5, "Korea, D.P.R Of": 10,
    "Kosovo": 7, "Kuwait": 4, "Kyrgyzstan": 10, "Laos": 5,
    "Latvia": 7, "Lebanon": 10, "Lesotho": 10, "Liberia": 10,
    "Libya": 10, "Liechtenstein": 7, "Lithuania": 7, "Luxembourg": 7,
    "Macau SAR China": 5, "Madagascar": 10, "Malawi": 10,
    "Malaysia": 2, "Maldives": 1, "Mali": 10, "Malta": 7,
    "Marshall Islands": 10, "Martinique": 10, "Mauritania": 10,
    "Mauritius": 10, "Mayotte": 10, "Mexico": 8, "Micronesia": 10,
    "Moldova, Rep. Of": 10, "Monaco": 7, "Mongolia": 10,
    "Montenegro, Rep Of": 7, "Montserrat": 10, "Morocco": 10,
    "Mozambique": 10, "Myanmar": 5, "Namibia": 10, "Nauru, Rep. Of": 10,
    "Nepal": 1, "Netherlands, The": 7, "Nevis": 10, "New Caledonia": 10,
    "New Zealand": 6, "Nicaragua": 10, "Niger": 10, "Nigeria": 10,
    "Niue": 10, "North Macedonia": 7, "Northern Mariana Islands": 10,
    "Norway": 7, "Oman": 4, "Pakistan": 4, "Palau": 10,
    "Panama": 10, "Papua New Guinea": 6, "Paraguay": 9, "Peru": 9,
    "Philippines, The": 5, "Poland": 7, "Portugal": 7, "Puerto Rico": 10,
    "Qatar": 4, "Reunion, Island Of": 10, "Romania": 7,
    "Russian Federation": 10, "Rwanda": 10, "Saint Helena": 10,
    "Samoa": 10, "San Marino": 7, "Sao Tome And Principe": 10,
    "Saudi Arabia": 4, "Senegal": 10, "Serbia, Rep. Of": 7,
    "Seychelles": 10, "Sierra Leone": 10, "Singapore": 2, "Slovakia": 7,
    "Slovenia": 7, "Solomon Islands": 10, "Somalia Hargeisa": 10,
    "Somalia Mogadishu": 10, "South Africa": 9, "South Sudan": 10,
    "Spain": 7, "Sri Lanka": 1, "St. Barthelemy": 10, "St. Eustatius": 10,
    "St. Kitts": 10, "St. Lucia": 10, "St. Maarten": 10,
    "St. Vincent": 10, "Sudan": 10, "Suriname": 9, "Sweden": 7,
    "Switzerland": 7, "Syria": 10, "Tahiti": 10, "Taiwan": 5,
    "Tajikistan": 10, "Tanzania": 10, "Thailand": 2, "Timor-Leste": 5,
    "Togo": 10, "Tonga": 10, "Trinidad And Tobago": 10, "Tunisia": 10,
    "Turkey": 7, "Turkmenistan": 10, "Turks & Caicos": 10, "Tuvalu": 10,
    "USA": 8, "Uganda": 10, "Ukraine": 10, "United Arab Emirates": 1,
    "United Kingdom": 7, "Uruguay": 9, "Uzbekistan": 10, "Vanuatu": 10,
    "Vatican City": 7, "Venezuela": 9, "Vietnam": 5,
    "Virgin Islands-British": 10, "Virgin Islands-US": 10,
    "Yemen, Rep. Of": 10, "Zambia": 10, "Zimbabwe": 10,

    # Common short names retained for existing clients and saved forms.
    "Central African Rep": 10, "Czech Rep., The": 7, "Hong Kong": 2,
    "Ireland, Rep. Of": 7, "Korea, South": 5, "Macau": 5,
    "Moldova": 10, "Netherlands": 7, "Philippines": 5, "Russia": 10,
    "Serbia": 7, "United States": 8,
}

# DHL PDF page 1 section: "Non-documents from 0.5 KG & Documents from 2.5 KG".
# These are the export freight charges in INR for 0.5 KG through 30 KG.
# Columns: Zone 1..10.
DHL_RATES = {
0.5:[1818,2401,2528,2633,2701,2785,2586,2660,3253,3766],
1.0:[2366,2969,3157,3247,3379,3429,2989,3074,4293,4670],
1.5:[2723,3423,3642,3741,3885,3941,3392,3489,4871,5395],
2.0:[3080,3877,4127,4235,4391,4453,3795,3904,5449,6120],
2.5:[3437,4331,4618,4729,4897,4965,4198,4319,6027,6845],
3.0:[3712,4674,5021,5132,5311,5403,4570,4707,6556,7525],
3.5:[3987,5017,5424,5535,5725,5841,4942,5095,7085,8205],
4.0:[4262,5360,5827,5938,6139,6279,5314,5483,7614,8885],
4.5:[4537,5703,6230,6341,6553,6717,5686,5871,8143,9565],
5.0:[4812,6046,6633,6744,6967,7155,6058,6259,8672,10245],
5.5:[4976,6244,6918,7034,7267,7449,6358,6584,9126,10818],
6.0:[5140,6442,7203,7324,7567,7743,6658,6909,9580,11391],
6.5:[5304,6640,7488,7614,7867,8037,6958,7234,10034,11964],
7.0:[5468,6838,7773,7904,8167,8331,7258,7559,10488,12537],
7.5:[5632,7036,8058,8194,8467,8625,7558,7884,10942,13110],
8.0:[5796,7234,8343,8484,8767,8919,7858,8209,11396,13683],
8.5:[5960,7432,8628,8774,9067,9213,8158,8534,11850,14256],
9.0:[6124,7630,8913,9064,9367,9507,8458,8859,12304,14829],
9.5:[6288,7828,9198,9354,9667,9801,8758,9184,12758,15402],
10.0:[6452,8026,9483,9644,9967,10095,9058,9509,13212,15975],
10.5:[6642,8163,9706,9862,10188,10332,9271,9785,13593,16385],
11.0:[6832,8300,9929,10080,10409,10569,9484,10061,13974,16795],
11.5:[7022,8437,10152,10298,10630,10806,9697,10337,14355,17205],
12.0:[7212,8574,10375,10516,10851,11043,9910,10613,14736,17615],
12.5:[7402,8711,10598,10734,11072,11280,10123,10889,15117,18025],
13.0:[7592,8848,10821,10952,11293,11517,10336,11165,15498,18435],
13.5:[7782,8985,11044,11170,11514,11754,10549,11441,15879,18845],
14.0:[7972,9122,11267,11388,11735,11991,10762,11717,16260,19255],
14.5:[8162,9259,11490,11606,11956,12228,10975,11993,16641,19665],
15.0:[8352,9396,11713,11824,12177,12465,11188,12269,17022,20075],
15.5:[8542,9533,11936,12042,12398,12702,11401,12545,17403,20485],
16.0:[8732,9670,12159,12260,12619,12939,11614,12821,17784,20895],
16.5:[8922,9807,12382,12478,12840,13176,11827,13097,18165,21305],
17.0:[9112,9944,12605,12696,13061,13413,12040,13373,18546,21715],
17.5:[9302,10081,12828,12914,13282,13650,12253,13649,18927,22125],
18.0:[9492,10218,13051,13132,13503,13887,12466,13925,19308,22535],
18.5:[9682,10355,13274,13350,13724,14124,12679,14201,19689,22945],
19.0:[9872,10492,13497,13568,13945,14361,12892,14477,20070,23355],
19.5:[10062,10629,13720,13786,14166,14598,13105,14753,20451,23765],
20.0:[10252,10766,13943,14004,14387,14835,13318,15029,20832,24175],
21.0:[10586,11224,14406,14468,15087,15485,13963,15683,21461,25208],
22.0:[10920,11682,14869,14932,15787,16135,14608,16337,22090,26241],
23.0:[11254,12140,15332,15396,16487,16785,15253,16991,22719,27274],
24.0:[11588,12598,15795,15860,17187,17435,15898,17645,23348,28307],
25.0:[11922,13056,16258,16324,17887,18085,16543,18299,23977,29340],
26.0:[12256,13514,16721,16788,18587,18735,17188,18953,24606,30373],
27.0:[12590,13972,17184,17252,19287,19385,17833,19607,25235,31406],
28.0:[12924,14430,17647,17716,19987,20035,18478,20261,25864,32439],
29.0:[13258,14888,18110,18180,20687,20685,19123,20915,26493,33472],
30.0:[13592,15346,18573,18644,21387,21335,19768,21569,27122,34505],
}

# From 30.1 KG: INR per KG, by zone.
DHL_MULTIPLIERS = [
    (Decimal("30.1"), Decimal("70"), [439,497,600,602,706,708,666,714,874,1118]),
    (Decimal("70.1"), Decimal("300"), [421,471,570,579,672,673,656,721,853,1089]),
    (Decimal("300.1"), Decimal("99999"), [423,476,574,584,678,680,661,739,869,1098]),
]

def ceil_half_kg(weight: Decimal) -> Decimal:
    # DHL card: each piece weight rounded up to nearest 0.5 kg / 1 kg as applicable.
    return (weight * 2).to_integral_value(rounding=ROUND_CEILING) / Decimal("2")

def get_dhl_freight(weight: Decimal, zone: int):
    if weight <= 0:
        return Decimal("0"), Decimal("0")

    if weight <= Decimal("30"):
        chargeable = ceil_half_kg(weight)
        # Exact card rows are 0.5 increments through 20, then whole kg 21-30.
        if chargeable > Decimal("20"):
            chargeable = chargeable.to_integral_value(rounding=ROUND_CEILING)
        if chargeable not in DHL_RATES:
            return chargeable, Decimal("0")
        return chargeable, Decimal(str(DHL_RATES[float(chargeable)][zone - 1]))

    for low, high, rates in DHL_MULTIPLIERS:
        if low <= weight <= high:
            chargeable = weight.to_integral_value(rounding=ROUND_CEILING)
            return chargeable, Decimal(str(rates[zone - 1])) * chargeable

    return weight, Decimal("0")

def money(v):
    return float(v.quantize(Decimal("0.01"), rounding=ROUND_CEILING))

def money_decimal(v):
    return v.quantize(Decimal("0.01"), rounding=ROUND_CEILING)

@app.route("/")
def index():
    return render_template(
        "index.html",
        suppliers=["Element14", "Mouser", "UniKey", "TTI", "DigiKey", "Waldom"],
        countries=sorted(COUNTRY_ZONES.keys()),
        rules={
            "insurance": "1.125% of Invoice Value",
            "forex": "Not applicable - INR only",
            "assessable_value": "Invoice Value + Insurance + Freight",
            "bcd": "0% to 50% selectable",
            "sws": "10% on BCD",
            "igst": "18% on (Assessable Value + BCD + SWS)",
        },
    )

@app.post("/api/calculate")
def calculate():
    data = request.get_json(force=True)

    try:
        # Commercial invoice in INR
        currency = "INR"
        supplier = str(data.get("supplier", "")).strip()
        is_element14 = supplier.lower() == "element14"

        weight = Decimal(str(data.get("weight", 0)))
        origin = data.get("origin", "")
        bcd_rate_percent = Decimal(str(data.get("bcd_rate", "0")))
        shipping_charges = Decimal(str(data.get("shipping_charges", 0)))
        if shipping_charges < 0:
            shipping_charges = Decimal("0")

        insurance_applicable = data.get("insurance_applicable", True)
        if isinstance(insurance_applicable, str):
            insurance_applicable = insurance_applicable.lower() in ["true", "1", "yes"]

        use_custom_freight = data.get("use_custom_freight", False)
        if isinstance(use_custom_freight, str):
            use_custom_freight = use_custom_freight.lower() in ["true", "1", "yes"]
        custom_freight = data.get("custom_freight", 0)

        if not (Decimal("0") <= bcd_rate_percent <= Decimal("100")):
            raise ValueError("BCD rate must be between 0% and 50%.")

        clearance = Decimal(str(data.get("custom_clearance", 0)))
        handling = Decimal(str(data.get("handling", 0)))
        other = Decimal(str(data.get("other_charges", 0)))
        margin = Decimal(str(data.get("margin", 0)))

        if weight < 0:
            weight = Decimal("0")

        zone = COUNTRY_ZONES.get(origin, 8)
        if not is_element14 and not COUNTRY_ZONES.get(origin):
            raise ValueError("Country of origin is not mapped to a DHL import zone.")

        # Multi-part commercial invoice parsing
        raw_items = data.get("items")
        parsed_items = []
        total_product_inr = Decimal("0")
        total_quantity = Decimal("0")

        if raw_items and isinstance(raw_items, list) and len(raw_items) > 0:
            for idx, it in enumerate(raw_items, 1):
                p_name = str(it.get("part_name", "") or it.get("part_number", f"Part #{idx}")).strip()
                p_price = Decimal(str(it.get("unit_price", 0)))
                p_qty = Decimal(str(it.get("quantity", 0)))
                if p_price < 0 or p_qty <= 0:
                    raise ValueError(f"Price and quantity for '{p_name}' must be positive.")
                line_total = p_price * p_qty
                total_product_inr += line_total
                total_quantity += p_qty
                parsed_items.append({
                    "part_name": p_name,
                    "unit_price": money(p_price),
                    "quantity": int(p_qty) if p_qty % 1 == 0 else float(p_qty),
                    "line_total": money(line_total),
                    "_raw_line_total": line_total,
                    "_raw_qty": p_qty,
                })
            if total_quantity <= 0 or total_product_inr <= 0:
                raise ValueError("Total quantity and invoice value must be greater than zero.")
            product_inr = total_product_inr
            quantity = total_quantity
            unit_price = product_inr / quantity
        else:
            unit_price = Decimal(str(data.get("unit_price", 0)))
            quantity = Decimal(str(data.get("quantity", 0)))
            if unit_price < 0 or quantity <= 0:
                raise ValueError("Unit price and quantity must be greater than zero.")
            product_inr = unit_price * quantity
            total_quantity = quantity
            parsed_items = [{
                "part_name": "Part #1",
                "unit_price": money(unit_price),
                "quantity": int(quantity) if quantity % 1 == 0 else float(quantity),
                "line_total": money(product_inr),
                "_raw_line_total": product_inr,
                "_raw_qty": quantity,
            }]

        if is_element14:
            # Element14 Domestic Vendor Order:
            # No shipping charges, DHL freight, insurance, or import IGST.
            # Only Invoice Value + 9% CGST + 9% SGST on Invoice Value.
            freight = Decimal("0")
            chargeable_weight = Decimal("0")
            shipping_charges = Decimal("0")
            insurance = Decimal("0")
            forex = Decimal("0")
            assessable_base = product_inr
            bcd = Decimal("0")
            sws = Decimal("0")
            igst = Decimal("0")
            igst_base = Decimal("0")
            cgst = product_inr * Decimal("0.09")
            sgst = product_inr * Decimal("0.09")
            total_gst = cgst + sgst
            customs_duty = Decimal("0")
            customs_assessment = money_decimal(total_gst)
            total_import_duty_tax = customs_assessment
            clearance = Decimal("0")
            handling = Decimal("0")
            other = Decimal("0")
            import_cost = Decimal("0")
            landed_cost = product_inr + total_gst
            unit_landed_cost = landed_cost / quantity
        else:
            # Standard International Import BOE workflow for all other suppliers:
            # 2. Freight & Insurance
            if use_custom_freight and custom_freight is not None:
                freight = Decimal(str(custom_freight))
                chargeable_weight = weight
            elif weight <= 0:
                chargeable_weight, freight = Decimal("0"), Decimal("0")
            else:
                chargeable_weight, freight = get_dhl_freight(weight, zone)

            insurance = (product_inr * INSURANCE_RATE) if insurance_applicable else Decimal("0")
            forex = Decimal("0")

            # 3. Assessable Value (CIF Customs Valuation)
            # Assessable Value = Invoice Value + Insurance + Shipping Charges + DHL Freight
            assessable_base = product_inr + freight + insurance + shipping_charges

            # 4. Customs Assessment (Bill of Entry)
            # BCD = Assessable Value × BCD Rate (0% to 50%)
            bcd = assessable_base * (bcd_rate_percent / Decimal("100"))

            # SWS = 10% of BCD
            sws = bcd * SWS_RATE

            # Import GST: IGST (18%) and Statutory GST (9% CGST + 9% SGST on IGST charges)
            # Base = Assessable Value + BCD + SWS
            igst_base = assessable_base + bcd + sws
            igst = igst_base * IGST_RATE
            cgst = igst * Decimal("0.09")
            sgst = igst * Decimal("0.09")
            total_gst = cgst + sgst

            customs_duty = bcd + sws
            customs_assessment = (
                money_decimal(bcd) + money_decimal(sws) + money_decimal(igst) + money_decimal(total_gst)
            )
            total_import_duty_tax = customs_assessment

            # 5. Import Operational Costs
            # Includes shipping charges, DHL freight, insurance, clearance, handling, other
            import_cost = clearance + handling + shipping_charges + freight + insurance + other + forex

            # 6. Landing Cost (Total Cost to Company)
            # Landing price includes product invoice, customs duties, total GST (CGST + SGST), and import costs
            landed_cost = product_inr + customs_assessment + import_cost
            unit_landed_cost = landed_cost / quantity

        # 7. Margin & Customer Quotation
        zemicon_margin = landed_cost * (margin / Decimal("100"))
        selling_price = landed_cost + zemicon_margin
        unit_selling_price = selling_price / quantity

        # 8. Apportion per-part landed cost & quotation selling price
        applicable_charges_total = Decimal("0") if is_element14 else (shipping_charges + freight + insurance + bcd + sws + import_cost)

        for it in parsed_items:
            share = it["_raw_line_total"] / product_inr if product_inr > 0 else Decimal("0")
            item_landed = landed_cost * share
            item_selling = selling_price * share
            p_qty = it["_raw_qty"]
            it["invoice_value"] = money(it["_raw_line_total"])
            it["assessable_value"] = money(assessable_base * share)
            it["igst"] = money(igst * share)
            it["cgst"] = money(cgst * share)
            it["sgst"] = money(sgst * share)
            it["total_gst"] = money(total_gst * share)
            it["applicable_charges"] = money(Decimal("0")) if is_element14 else money(applicable_charges_total * share)
            it["landed_cost"] = money(item_landed)
            it["unit_landed_cost"] = money(item_landed / p_qty) if p_qty > 0 else money(0)
            it["selling_price"] = money(item_selling)
            it["unit_selling_price"] = money(item_selling / p_qty) if p_qty > 0 else money(0)
            del it["_raw_line_total"]
            del it["_raw_qty"]

        return jsonify({
            "ok": True,
            "supplier": supplier,
            "is_element14": bool(is_element14),
            "zone": zone,
            "bcd_rate": float(bcd_rate_percent),
            "gross_weight": float(weight),
            "chargeable_weight": money(chargeable_weight),
            "shipping_charges": money(shipping_charges),
            "freight": money(freight),
            "total_shipping_and_freight": money(shipping_charges + freight),
            "product_value_inr": money(product_inr),
            "total_quantity": int(total_quantity) if total_quantity % 1 == 0 else float(total_quantity),
            "items": parsed_items,
            "insurance": money(insurance),
            "insurance_applicable": bool(insurance_applicable),
            "forex": money(forex),
            "assessable_base": money(assessable_base),
            "bcd": money(bcd),
            "sws": money(sws),
            "igst_base": money(igst_base),
            "igst": money(igst),
            "cgst": money(cgst),
            "sgst": money(sgst),
            "total_gst": money(total_gst),
            "customs_duty": money(customs_duty),
            "customs_assessment": money(customs_assessment),
            "total_import_duty_tax": money(total_import_duty_tax),
            "custom_clearance": money(clearance),
            "handling": money(handling),
            "other_charges": money(other),
            "import_cost": money(import_cost),
            "applicable_charges_total": money(applicable_charges_total),
            "landed_cost": money(landed_cost),
            "unit_landed_cost": money(unit_landed_cost),
            "zemicon_margin": money(zemicon_margin),
            "selling_price": money(selling_price),
            "unit_selling_price": money(unit_selling_price),
            "customer_quotation": money(selling_price),
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

@app.get("/api/dhl/rate")
def dhl_rate():
    try:
        origin = request.args.get("origin", "")
        weight = Decimal(request.args.get("weight", "0"))
        zone = COUNTRY_ZONES.get(origin)
        if not zone:
            raise ValueError("Unknown DHL origin zone")
        chargeable, freight = get_dhl_freight(weight, zone)
        return jsonify({
            "ok": True,
            "origin": origin,
            "zone": zone,
            "chargeable_weight": money(chargeable),
            "freight": money(freight),
            "currency": "INR",
            "rate_card": "Zemicon DHL Express Worldwide Export - 05-May-2026",
            "rate_section": "Non-documents from 0.5 KG & Documents from 2.5 KG",
        })
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
