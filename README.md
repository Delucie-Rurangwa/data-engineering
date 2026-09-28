# Veridi Logistics: Last Mile Delivery Audit

## A. Executive Summary
Of 96,470 delivered orders, 8.1% arrived after the promised date and 4.4% were more than 5 days late, so this is not a nationwide failure but a regional one: the Northeast runs at 14.3% late versus 7.5% for the rest of Brazil, with Alagoas (23.9%), Maranhao (19.7%) and Piaui (16.0%) worst, and high-volume Rio de Janeiro at 13.5%. Late delivery clearly drives bad reviews: On Time orders average 4.29 stars, Late orders 3.46 and Super Late orders 1.79. The CEO's "wrong estimates" hunch is half right: nationally we over-pad (median promise 23 days vs 10 actual), but in 13 states, including the Northeast and Rio, the promise is too tight, and extending estimates only there would cut the late rate from 8.1% to 5.6% without changing operations.

## B. Project Links
- **Repository:** https://github.com/Delucie-Rurangwa/data-engineering
- **Notebook:** https://github.com/Delucie-Rurangwa/data-engineering/blob/main/veridi_last_mile_audit.ipynb (HTML export with charts: `veridi_last_mile_audit.html`, also in this repo)
- **Dashboard:** https://data-engineering-bvgnsnuqzcxys9ahtuaift.streamlit.app/
- **Presentation:** https://drive.google.com/file/d/1qUFZlkmLV-2Dr7cMSPhllvHtcox05U9f/view?usp=sharing (PDF/PPTX also in this repo)

## C. Technical Explanation
**Data cleaning**
- Joined `orders` + `customers` (many-to-one on `customer_id`), reviews and the first-item product category (one-to-one after aggregation) using pandas `validate=` on every merge, plus an assertion that the master table still has 99,441 rows (= orders table), so no join duplicated rows.
- 547 orders had more than one review, so reviews were collapsed to one row per order (mean score) before joining. Orders with several items use the category of item 1.
- Only orders with status `delivered` and a delivery date are analysed (96,470). The other 2,971 (shipped, canceled, unavailable, invoiced, processing, created, approved, plus 8 delivered without a date) are flagged in `exclusion_reason` and excluded.
- `Days_Difference = estimated - actual delivery` (negative = late). On Time >= 0 days, Late = 0 to 5 days late, Super Late = more than 5 days late.
- Product categories translated to English with `product_category_name_translation.csv`; unmatched become "unknown". Categories under 200 orders are hidden from rankings. 0.7% of delivered orders have no review and are ignored in sentiment metrics.
- Remoteness = km from Sao Paulo (assumed hub) to each state capital, correlated with % late (r = 0.15, weak).

**Candidate's Choice: Promise Accuracy Gap**
For each state I compare the median promised delivery time with the median actual time and compute a "safe promise" (90th percentile of actual delivery days). Promises are only ever extended where too tight, never shortened. This matters because the CEO suspects we are over-promising: it shows exactly how many days of padding each state needs (e.g. Alagoas +8.6, Sergipe +6.5, Rio +5.4) and simulates the outcome (late rate 8.1% to 5.6%), giving a low-cost fix that does not depend on faster shipping.

## How to run (VS Code)
1. Put the 6 Olist CSVs next to `veridi_audit.py` (they are git-ignored, do not commit them).
2. `py -3.13 -m pip install -r requirements.txt` (use `python` instead of `py -3.13` on Mac/Linux).
3. `py -3.13 veridi_audit.py` (charts go to `charts/`, summary CSVs are regenerated), or open the `.ipynb` in VS Code and Run All.
4. `py -3.13 -m streamlit run app.py` for the dashboard, then open the "Deploy" button in the browser tab to publish it publicly on Streamlit Community Cloud.

## Repo contents
`veridi_audit.py` (single-file analysis script), `veridi_last_mile_audit.ipynb` + `.html` export (notebook deliverable), `Veridi_Delivery_Audit.pptx` + `.pdf` (presentation), `app.py` + `requirements.txt` (dashboard), `charts/` (static PNGs), and the three summary CSVs the dashboard reads. Raw Olist CSVs are excluded via `.gitignore`.
