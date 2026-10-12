# Seedwatch

**Retail price monitoring, built around a real problem at work.**

[Try the live demo](https://seedwatch-demo.streamlit.app/) · [My portfolio](https://pierre-nubah-portfolio.pierrenubah.chatgpt.site/) · [LinkedIn](https://www.linkedin.com/in/pierre-nubah-175520275/)

## Why I built it

While working at Amazing Herbs, I noticed how difficult it was for my boss to keep up with retailer pricing alongside his other responsibilities. Checking product pages one at a time took attention away from other work, and comparing prices across retailers meant keeping track of a lot of separate information.

I built Seedwatch to bring that work into one place: check prices, see which listings need attention, and keep a history of what changed. It started as a way to help someone I work with and grew as my boss shared what would make it more useful day to day.

One of his most important requests was being able to add products and retailers himself. That shaped the catalog tools, manual price entry, and listing checks you can explore in this demo.

## What Seedwatch does

The private application tracks more than 100 product listings across eight retailers, including Amazing Herbs, Amazon, GNC, and Vitacost. Automatic collection is available for supported sources; listings that cannot be checked reliably remain available for manual review.

Seedwatch compares observed prices with **minimum advertised price (MAP)**—the company's advertised-price guideline for a product—and highlights prices below that threshold for review.

With the app, a user can:

- **Find listings that need attention:** see below-MAP prices, outdated observations, and listings requiring manual checks.
- **Compare the same product across retailers:** view color-coded price history alongside MAP.
- **Manage the catalog:** add or edit products, register retailers, and attach product pages.
- **Record a manual check:** save a price and notes about the seller or offer when automation is unavailable.
- **Download Excel reports:** take pricing results and history into a spreadsheet.
- **Set up weekly checks:** the private app supports Sunday checks while Seedwatch is running and its host computer is awake.
- **Manage storage:** clean up eligible troubleshooting files while keeping product and price history.

## Take a look around

**[Open Seedwatch in your browser →](https://seedwatch-demo.streamlit.app/)**

No installation is needed. A few places to start:

1. Open **Overview** to see retailer coverage and listings needing attention.
2. Visit **Product history**, choose a product, and compare its prices across retailers.
3. In **Manage catalog → Record a manual price**, choose a listing without a saved check for today, enter a price and offer notes, and confirm the product details. Your observation will appear in your sample workspace.
4. Open **Reports** and download an Excel workbook.

The demo follows the private app's layout and workflows, using **fictional products and prices**. These are examples, not claims about actual retailer pricing. Each visitor gets a separate temporary workspace, so your edits do not affect anyone else's data. Company data is not included. Price checks and listing tests are simulated, and schedule controls do not run background jobs.

## What I built and learned

I used **Python, Streamlit, SQLite, and pandas** to connect price collection, a product catalog, historical records, and a usable dashboard.

The hardest part has been making the results useful and trustworthy. A price only helps if it belongs to the right product and size, and a failed check should never look like a successful one. That led me to add product confirmation, duplicate-check protection, visible freshness labels, and a manual review path.

This project has also taught me to listen to the person using what I build. Features such as retailer comparisons, catalog editing, and Excel downloads came from conversations about the actual work—not just what I thought would look good on a dashboard.

## What I'm working on next

I'm exploring ways to make new retailer setup easier and improve reliable automated access, including supported integrations where available. Retailer access restrictions remain a limitation, so manual checks are still an important part of the workflow.

## Run the demo locally

From a complete copy of this repository, install the dependencies and start the app:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Keep the release files together. The app checks that its supporting files match before it starts.

---

Built by **Pierre Nubah**, an Information Systems student at Kennesaw State University, bringing business and technology together to make everyday work easier.
