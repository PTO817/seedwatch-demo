# Seedwatch

**[Open the live demo →](https://seedwatch-demo.streamlit.app/)**

### Retail price monitoring with clear history and collection status

Seedwatch helps a team review retailer prices against minimum advertised price (MAP) thresholds, identify observations that need attention, and track price history in one dashboard.

This repository contains the **public portfolio demo** of a separate working price-monitoring application. The demo uses synthetic products and prices so visitors can explore the workflow without accessing company information.

## Try the demo

The demo is deployed on Streamlit Community Cloud. No installation is needed to use the hosted version.

A quick walkthrough:

1. **Overview:** Review the below-MAP observations and retailer coverage.
2. **Listings:** Search `DEMO-001`, filter by retailer or collection status, and export the results.
3. **Product history:** Select a listing to compare its sample prices with the MAP recorded at each check.
4. **Collection activity:** Click **Run sample check** to see accepted prices, manual-review cases, and a missing-price example. Run it again to see duplicate protection, or reset it to start over.

**All displayed products, prices, and history are synthetic.** Retailer names illustrate the interface; retailer links open homepages. The simulated checks make no retailer requests and are not evidence of current retailer prices or availability.

## The problem

Checking multiple retailer pages manually makes it difficult to maintain a consistent price history or tell whether a saved price is still current. Retailers also present different product identifiers, purchase options, and access restrictions.

Seedwatch brings pricing observations and collection status into the same view. A previous successful observation remains visible even when a new check cannot obtain a price.

## Design decisions

- **Price and collection status are separate.** A saved price does not mean a listing was successfully checked today.
- **Missing prices stay missing.** A failed check does not become a zero-dollar price or an automatic “OK.”
- **Comparisons retain their context.** History compares each observed price with the MAP recorded at that check.
- **Manual review is explicit.** Listings that cannot be checked automatically remain visible for follow-up.
- **The public demo is isolated.** It contains no company database, credentials, browser profiles, or live collector code. Demo mode cannot be changed through environment settings.

## Public demo and working application

| Capability | This public demo | Separate working application |
|---|---|---|
| Dashboard, filters, history, CSV export | Synthetic data | Company catalog and saved observations |
| Price checks | Scripted simulation | Retailer-specific collectors |
| Duplicate handling | Per browser session | Daily database checks |
| Seller and delivery context | Not validated by the simulation | Retained where supported by the collector |
| Data storage | Generated sample SQLite database | Local SQLite database and collection reports |

The private application has completed live checks on macOS, including GNC, Amazon, and Whole Foods through the dashboard. Windows deployment remains to be validated. Shared remote access and scheduled collection are not yet configured.

Simulation results are isolated to each visitor's session. They do not update the Overview, Listings, or Product history sample data. The scripted retailer outcomes demonstrate application behavior, not current access conditions.

## Technology

- **Python:** Application and data-handling logic.
- **Streamlit:** Interactive dashboard and session-based simulation.
- **pandas:** Filtering, tables, charts, and CSV export.
- **SQLite:** Generated sample catalog and price history.
- **Streamlit Community Cloud:** Hosted public demo.

## Run locally

Use Python 3.13. From the repository folder:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No secrets, retailer accounts, or external database setup are required. The sample database is generated on first launch.

## Validation

Local Streamlit app tests covered the four pages, SKU filtering, history display, simulated outcomes, repeat-run duplicate handling, reset behavior, retailer selection, and isolation between visitor sessions. The simulation was also checked to leave the sample database unchanged.

These checks validate the demo workflow; they do not validate live retailer access or production deployment.
