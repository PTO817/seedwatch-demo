# Seedwatch — retail price monitoring

A portfolio demonstration of a Python dashboard for comparing observed retail prices with minimum advertised price (MAP) thresholds.

**All products, prices, and history in this demo are synthetic.** Retailer names illustrate coverage, and links lead to retailer homepages. No company database, credentials, or live collection code is included.

## Explore the app

- **Overview:** See pricing observations and collection coverage.
- **Listings:** Filter by product, retailer, and collection status; export a CSV.
- **Product history:** Compare sample prices against the MAP recorded at each check.
- **Collection activity:** Learn how the working application handles new checks, duplicates, manual review, and failures. Live checks are disabled here.

The design distinguishes a past price observation from a successful current check. Missing prices are not treated as zero or automatically marked compliant. Below-MAP flags are observations for review, not legal conclusions.

## Implementation

Python, Streamlit, pandas, and SQLite. The demo creates its sample database on first launch. Configuration is fixed to demo mode; private project environment settings cannot enable production access.

The separate working application includes retailer collectors and daily duplicate protection. Hosted collection and Windows behavior are separate validation tasks; this public demo does not claim to perform either.

## Run locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Publish on Streamlit Community Cloud

1. Upload this folder's contents to a separate GitHub repository named `seedwatch-demo`.
2. Sign in at https://share.streamlit.io and choose Create app.
3. Choose the repository, branch `main`, and entrypoint `app.py`.
4. Choose Python 3.13 in advanced settings. No secrets or environment variables are required.
5. Deploy, test all four pages, and add the verified live URL to this README and the repository's About section.

Use the supplied Streamlit website address; a custom domain is not required. This package has not been deployed yet.
