# Zemicon Landing Price Calculator

A Flask application for estimating DigiKey component landing prices. It supports manual product entry, Excel purchase-list imports, DigiKey master tariff lookup, USD-to-INR conversion, shipment charges, customs duties, and per-line landed-cost results.

The legacy Landing Cost Calculator UI and its DHL freight/customs backend have been removed. The root URL (`/`) redirects to the maintained DigiKey calculator at `/landing/v2`.

## Requirements

- Python 3.10 or newer
- Dependencies from `requirements.txt`

## Run locally

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>. The root URL redirects to the DigiKey calculator.

### Production

#### Render

Create a **Web Service** for this repository with:

- **Runtime:** Python
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `gunicorn -c gunicorn.conf.py wsgi:app`

Gunicorn binds to Render's `PORT` environment variable (and defaults to port 5000 locally). The service needs a persistent disk if you want the SQLite DigiKey master and added records to survive redeploys; otherwise Render's filesystem is ephemeral. Set `LANDING_V2_DATABASE` to a path on that disk, such as `/var/data/landing_price_v2.sqlite`, and mount the disk at `/var/data`.

On Windows:

```powershell
waitress-serve --host=0.0.0.0 --port=5000 wsgi:app
```

On Linux/Unix:

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

Use a reverse proxy and TLS for deployments beyond localhost.

## Calculator workflow

1. Select one invoice currency for the shipment. For USD, enter the live interbank USD/INR rate once; the calculator applies a 2% adjustment. INR uses an exchange rate of 1.
2. Enter each component's MPN, quantity, and per-unit price. Each product row displays Amount = quantity × per-unit price, shown in INR (USD entries are converted using the adjusted exchange rate).
3. The calculator computes insurance at 1.125% of each converted INR invoice amount.
4. If total shipment invoice value is below ₹7,000, the ₹1,200 international freight charge is allocated by each line's share of the shipment invoice. Freight is zero at or above ₹7,000.
5. Enter optional shipment-level Other charges in INR. These charges are allocated by invoice share and added to landed cost, but excluded from assessable value.
6. Review the DigiKey tariff table. BCD is calculated on each line's assessable value (invoice + insurance + allocated international freight), rounded to the nearest whole rupee, then SWS is calculated on that rounded BCD. If an MPN is not in the master, enter its BCD/SWS rates for the calculation.
7. Enter the team's margin percentage. The margin is applied to the landed cost of each line and added to the shipment selling total; the per-line selling price is shown separately. IGST remains optional and, when enabled, is calculated after margin.

Remittance, CHA/port dues, and domestic trucking are optional configured shipment charges. For zero-value invoices, allocated optional charges use quantity shares.

## DigiKey master and Excel import

The initial master workbook is `static/digikey-1.xlsx`. On first use, the calculator imports its MPN, category, HSN/CTSH, BCD, and SWS data into the operational SQLite database. Rates stored in the workbook as fractions (such as `0.1`) are imported as percentages (`10%`). Existing master records are not overwritten when duplicates are added.

The calculator accepts `.xlsx` purchase lists up to 10 MB. It searches for MPN, unit-price, and quantity columns and asks for a selection when the workbook's layout is ambiguous. Total/extended-price columns are not interpreted as unit prices; quantity defaults to 1 if missing. The shipment currency and USD exchange rate selected on the page apply to all imported rows.

The operational DigiKey master can be downloaded using **Export DigiKey master**.

## v2 HTTP endpoints

| Method and path | Purpose |
| --- | --- |
| `GET /landing/v2` | DigiKey landing-price calculator. |
| `GET /api/landing/v2/config` | List available currencies and active charge configuration. |
| `GET /api/landing/v2/product/<mpn>` | Look up an MPN in the operational DigiKey master. |
| `POST /api/landing/v2/import-excel` | Preview an uploaded `.xlsx` workbook; submit column selections when requested. |
| `POST /api/landing/v2/calculate` | Calculate line landing prices using master data and shipment rules. |
| `POST /api/landing/v2/master` | Add missing product tariff records; existing MPNs are unchanged. |
| `GET /api/landing/v2/master/export` | Export the operational master as `.xlsx`. |

The calculate request uses an `items` array with `mpn`, `quantity`, `unit_price`, and `currency` (`USD` or `INR`). For USD, provide `live_exchange_rate`; the backend applies the 2% adjustment. An unknown MPN requires `bcd_rate`; `sws_rate` defaults to 10% if omitted. Shipment-level Other charges use `other_charges_total` in INR. Optional request fields include `remittance_applicable`, `cha_applicable`, `domestic_trucking_applicable`, `margin_percent`, and `igst_enabled`. Margin is applied independently of IGST to each line's landed cost; the shipment selling total is the sum of those margin-inclusive lines. If enabled, IGST is calculated after margin.

Example:

```json
{
  "items": [
    {
      "mpn": "NCV5661DT33RKG",
      "quantity": 12,
      "unit_price": 1.193,
      "currency": "USD",
      "live_exchange_rate": 97.6854
    }
  ],
  "remittance_applicable": "no",
  "cha_applicable": "no",
  "domestic_trucking_applicable": "no",
  "other_charges_total": 250,
  "igst_enabled": "no"
}
```

The v2 API is intended for a trusted internal Procurement environment. Deploy it behind the organization's access controls before exposing the master-write endpoint.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | Flask application and root redirect to the DigiKey calculator. |
| `wsgi.py` | WSGI entry point. |
| `services/landing_price_v2/` | DigiKey master database, Excel import, API, and calculation engine. |
| `templates/landing_price_v2.html` | DigiKey calculator UI. |
| `static/landing_price_v2.js` | Product entry, live previews, and results UI. |
| `static/landing_price_v2.css` | DigiKey calculator styles. |
| `static/digikey-1.xlsx` | Source workbook used to seed the DigiKey master. |
| `tests/test_landing_price_v2.py` | Calculator and API regression tests. |
| `requirements.txt` | Python dependencies. |

Treat calculator output as an estimate, not tax or customs advice. Validate duty assumptions against applicable customs requirements and representative Bills of Entry.

Run tests from the repository root:

```powershell
python -m unittest discover -s tests -v
```
