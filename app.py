# streamlit_app.py
import io
import zipfile
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter

from utils import mm_to_px, render_label_image

ASSETS_DIR = Path("assets")
SAMPLES_DIR = Path("samples")

st.set_page_config(page_title="Packaging Design Automation", layout="wide",
                   page_icon=str(ASSETS_DIR / "logo.png"))

st.markdown("""
# Packaging Design Automation
**From CSV data ➝ to finished label ➝ in minutes.**  
This is what modern automation looks like. Who else wants to reduce manual design work?
""")

# left column: mockup + info
col1, col2 = st.columns([1.6, 1])
with col1:
    try:
        mockup = Image.open(ASSETS_DIR / "mockup_screen.png")
        st.image(mockup, use_column_width=True)
    except Exception:
        st.info("Provide `assets/mockup_screen.png` to show product mockup.")

with col2:
    st.markdown("### Quick steps")
    st.markdown("""
    1. Upload a CSV with fields (example provided).
    2. Map CSV columns to template fields (Brand / Name / Price / EAN).
    3. Preview and generate label images (PNG).
    4. Download all generated labels as a ZIP.
    """)
    with st.expander("Download sample CSV"):
        st.download_button("Download sample CSV", data=open(SAMPLES_DIR / "sample_data.csv","rb"), file_name="sample_data.csv", mime="text/csv")

st.markdown("---")

# Uploader and options
uploaded = st.file_uploader("Upload CSV file", type=["csv"], accept_multiple_files=False)
if not uploaded:
    st.info("Upload a CSV or download the sample and modify it.")
    st.stop()

try:
    df = pd.read_csv(uploaded, dtype=str).fillna("")
except Exception as e:
    st.error(f"Failed to read CSV: {e}")
    st.stop()

st.success(f"Loaded {len(df)} rows from `{uploaded.name}`")

# Show small dataframe preview
st.dataframe(df.head(10), use_container_width=True)

# Column mapping UI
st.markdown("### Map CSV columns to label fields")
cols = list(df.columns)
col_brand = st.selectbox("Brand column", options=cols, index=0)
col_name = st.selectbox("Product name column", options=cols, index=min(1, len(cols)-1))
col_price = st.selectbox("Price column", options=cols, index=min(2, len(cols)-1))
col_ean = st.selectbox("EAN (13) column", options=cols, index=min(3, len(cols)-1))

# Label options
st.markdown("### Label options")
label_width_mm = st.number_input("Label width (mm)", value=80.0, min_value=10.0, step=1.0)
label_height_mm = st.number_input("Label height (mm)", value=50.0, min_value=10.0, step=1.0)
dpi = st.selectbox("DPI (print quality)", options=[150, 300, 600], index=1)
font_path_input = st.text_input("Optional TTF font path (leave blank to use default)", value="")

# Preview single row
row_index = st.number_input("Preview row index (0-based)", value=0, min_value=0, max_value=max(0, len(df)-1), step=1)
sample_row = df.iloc[row_index].to_dict()

st.markdown("#### Preview")
preview_img = render_label_image(
    brand=sample_row.get(col_brand, ""),
    name=sample_row.get(col_name, ""),
    price=sample_row.get(col_price, ""),
    ean=sample_row.get(col_ean, ""),
    width_mm=label_width_mm,
    height_mm=label_height_mm,
    dpi=dpi,
    font_path=font_path_input or None
)
st.image(preview_img, use_column_width=False)
st.markdown("---")

# Generate all labels
if st.button("Generate labels for all rows"):
    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, row in df.iterrows():
            brand = row.get(col_brand, "")
            name = row.get(col_name, "")
            price = row.get(col_price, "")
            ean = row.get(col_ean, "")
            img = render_label_image(brand, name, price, ean, label_width_mm, label_height_mm, dpi, font_path_input or None)

            bio = io.BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)
            filename = f"label_{idx+1}_{brand[:20].replace(' ','_')}.png"
            zf.writestr(filename, bio.read())
    buffer_zip.seek(0)
    st.success("Generated images for all rows.")
    st.download_button("Download labels (ZIP)", data=buffer_zip, file_name="labels.zip", mime="application/zip")
