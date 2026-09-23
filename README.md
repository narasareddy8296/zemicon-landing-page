# Zemicon Flask Landing Cost Calculator

## What this version is for

This is the **pre-order** procurement calculator. There is deliberately no invoice upload.

The procurement team enters:
- Supplier: Element14, Mouser, UniKey, TTI, DigiKey, Waldom
- Unit price
- Quantity
- User-entered BCD percentage
- INR unit price and invoice value
- Country of origin
- Material/gross weight
- Custom clearance
- Handling
- Other charges
- Desired margin

The Flask backend calculates:
1. Total invoice value = unit price × quantity
2. Invoice value converted to INR using the exchange rate
3. DHL zone from country of origin
4. Chargeable weight
5. DHL freight from the uploaded Zemicon DHL export rate card (PDF page 1)
6. Insurance = 1.125% of the total invoice value
7. Forex = not applicable because the calculator uses INR only
8. Assessable value = invoice value + freight + insurance
9. BCD = user-entered percentage of the assessable value
10. Customs duty = BCD + SWS
11. AIDC = applicable AIDC tax base × user-entered AIDC rate
12. Import IGST = applicable IGST tax base × 18%
13. Total import duty and tax = BCD + SWS + AIDC + Import IGST + other levies
14. Subtotal = invoice value + customs assessment + import costs
15. Custom clearance, handling and other charges
16. Total landed cost
17. Customer selling price using the current 25% markup interpretation

## Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open:
http://127.0.0.1:5000

## DHL rate card

The code includes the uploaded ZEMICON ELECTRONICS DHL EXPRESS WORLDWIDE EXPORT rate card, dated 05-May-2026 (PDF page 1):
- country zones
- 0.5–30 kg non-document rates
- 30.1–70 kg multiplier
- 70.1–300 kg multiplier
- 300.1+ kg multiplier

The DHL card also states that each piece weight is rounded to the applicable 0.5 kg or 1 kg increment.

## Important customs note

The customs/assessable-value formula is kept explicit in `app.py`. It should be validated against multiple BOEs before production. The provided BOE is a historical reference, not proof that every import has identical customs treatment.

For production, move the DHL rates and duty rules to database tables with a `rate_card_version` / `effective_date`.


## Current rule clarification

The requested rules are now implemented as:
- Insurance = 1.125% × total invoice value.
- Assessable value = invoice value + freight + insurance.
- BCD = assessable value × user-entered BCD rate.
- BCD rate = any percentage from 0% to 100%.
- SWS = 10% × BCD amount.
- AIDC = applicable AIDC tax base × AIDC rate.
- Import IGST = applicable IGST tax base × IGST rate.
- Customs duty = BCD + SWS.
- Total import duty and tax = BCD + SWS + AIDC + Import IGST + other applicable levies.
