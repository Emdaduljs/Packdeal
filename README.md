# Packaging Design Automation (Streamlit)

A small Streamlit app that converts CSV rows into finished label PNG images (with barcode) and bundles them into a ZIP for quick download. Designed to speed packaging/label production.

## Features
- Upload CSV, map fields, preview one row
- Generate barcode (EAN-13) as image and compose label with product details
- Download all generated labels as a ZIP
- Configurable label dimensions and DPI

## Run locally
1. Clone this repo
```bash
git clone https://github.com/<you>/packaging-automation.git
cd packaging-automation
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
streamlit run streamlit_app.py
