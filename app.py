# app.py
import base64
import io
import os
import zipfile
import csv
import streamlit as st
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from PIL import Image
import barcode
from barcode.writer import ImageWriter

ASSETS = Path("assets")
SVG_DIR = ASSETS / "svg"
SVG_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Packaging Design Automation", layout="wide")

st.title("Packaging Design Automation — CSV → editable SVG template → Download")
st.write("Upload CSV rows, pick an SVG layout, map CSV columns to SVG `id`s, preview and download the final files.")

# --- Helpers --------------------------------------------------------------
def read_csv_file(uploaded_file) -> List[Dict[str,str]]:
    uploaded_file.seek(0)
    text = io.TextIOWrapper(uploaded_file, encoding="utf-8")
    reader = csv.DictReader(text)
    rows = [ {k: (v if v is not None else "") for k,v in r.items()} for r in reader ]
    text.detach()
    uploaded_file.seek(0)
    return rows

def list_svg_templates() -> List[Path]:
    return sorted([p for p in SVG_DIR.glob("*.svg")])

def read_svg_bytes(path_or_bytes) -> bytes:
    if isinstance(path_or_bytes, (bytes, bytearray)):
        return bytes(path_or_bytes)
    elif hasattr(path_or_bytes, "read"):
        path_or_bytes.seek(0)
        return path_or_bytes.read()
    else:
        return Path(path_or_bytes).read_bytes()

def extract_ids_from_svg(svg_bytes: bytes) -> List[Tuple[str,str]]:
    """Return list of (id, tag) found in the SVG (search all elements for id attr)."""
    out = []
    try:
        root = ET.fromstring(svg_bytes.decode("utf-8"))
    except Exception:
        root = ET.fromstring(svg_bytes)
    for el in root.iter():
        elid = el.attrib.get("id")
        if elid:
            # strip namespace from tag
            tag = el.tag
            if '}' in tag:
                tag = tag.split('}',1)[1]
            out.append((elid, tag))
    return out

def generate_ean13_data_uri(ean_value: str, bar_height_px: int = 80) -> str:
    """Return data URI (PNG) for EAN13 barcode using python-barcode."""
    ean_clean = "".join([c for c in ean_value if c.isdigit()])
    if len(ean_clean) == 12:
        # python-barcode will compute checksum if given 12-digit
        pass
    EAN = barcode.get_barcode_class('ean13')
    writer = ImageWriter()
    options = {
        "module_height": bar_height_px,
        "font_size": 16,
        "text_distance": 5,
        "quiet_zone": 6.0
    }
    rv = EAN(ean_clean, writer=writer)
    bio = io.BytesIO()
    rv.write(bio, options)
    bio.seek(0)
    png = bio.read()
    b64 = base64.b64encode(png).decode("ascii")
    return "data:image/png;base64," + b64

def modify_svg(svg_bytes: bytes, mapping: Dict[str,str], row: Dict[str,str],
               embed_barcode_map: Dict[str,Tuple[str,int]]) -> bytes:
    """
    mapping: CSV_column -> SVG_element_id (text)
    embed_barcode_map: CSV_column -> (svg_element_id_for_image, barcode_height_px)
    """
    try:
        root = ET.fromstring(svg_bytes.decode("utf-8"))
    except Exception:
        root = ET.fromstring(svg_bytes)

    # Replace text nodes
    for csv_col, elid in mapping.items():
        value = row.get(csv_col,"")
        if not elid: continue
        # find element with that id
        el = None
        for node in root.iter():
            if node.attrib.get("id") == elid:
                el = node
                break
        if el is not None:
            # set text content - if text element contains tspan children, clear them and set text
            if el.tag.lower().endswith("text") or '}' in el.tag and el.tag.split('}',1)[1]=='text':
                # remove children
                for c in list(el):
                    el.remove(c)
                el.text = str(value)
            else:
                # for other elements (rect/text placeholders), set a 'data-text' attr as fallback
                el.attrib['data-text'] = str(value)

    # embed barcodes into mapped image elements
    for csv_col, (img_elid, height_px) in embed_barcode_map.items():
        ean_val = row.get(csv_col, "")
        if not ean_val: continue
        img_data = generate_ean13_data_uri(ean_val, bar_height_px=height_px)
        # find image element
        img_el = None
        for node in root.iter():
            if node.attrib.get("id") == img_elid:
                img_el = node
                break
        if img_el is not None:
            # set href attribute — try both xlink and plain
            # xlink namespace
            XLINK = "{http://www.w3.org/1999/xlink}href"
            if XLINK in img_el.attrib:
                img_el.attrib[XLINK] = img_data
            else:
                # many SVGs use plain 'href' (no xlink)
                img_el.attrib['href'] = img_data

    # produce bytes
    svg_out = ET.tostring(root, encoding="utf-8", method="xml")
    return svg_out

# --- UI --------------------------------------------------------------
st.header("1. Upload CSV (rows to generate)")
uploaded_csv = st.file_uploader("Upload CSV (first row header)", type=["csv"])
if not uploaded_csv:
    st.info("Upload a CSV file first (sample in repo).")
    st.stop()

rows = read_csv_file(uploaded_csv)
if not rows:
    st.error("CSV has no rows or invalid format.")
    st.stop()
st.success(f"Loaded {len(rows)} rows")

# Show preview (first 5)
st.subheader("CSV preview")
st.dataframe(rows[:5])

st.header("2. Pick or upload an SVG template")
col1, col2 = st.columns([2,1])

with col2:
    st.write("Available templates in `assets/svg/`")
    templates = list_svg_templates()
    options = ["(upload new SVG)"] + [p.name for p in templates]
    tpl_choice = st.selectbox("Select template", options)

    uploaded_svg = st.file_uploader("Or upload an SVG template here (will appear in dropdown)", type=["svg"])
    if uploaded_svg:
        # save uploaded file to assets/svg for convenience
        dest = SVG_DIR / uploaded_svg.name
        dest.write_bytes(read_svg_bytes(uploaded_svg))
        st.success(f"Saved uploaded template to {dest}")
        # refresh choices
        templates = list_svg_templates()
        options = ["(upload new SVG)"] + [p.name for p in templates]
        tpl_choice = uploaded_svg.name

with col1:
    st.write("Template preview / selection")
    if tpl_choice == "(upload new SVG)":
        st.info("Upload then select the template from the dropdown.")
        st.stop()
    template_path = SVG_DIR / tpl_choice
    if not template_path.exists():
        st.error("Selected template file not found on server (re-upload).")
        st.stop()
    svg_bytes = template_path.read_bytes()
    # show preview in an HTML container
    svg_text = svg_bytes.decode("utf-8", errors="ignore")
    st.markdown("**SVG preview (render):**")
    st.components.v1.html(svg_text, height=400)

# --- extract ids and mapping UI ---
st.header("3. Map CSV columns to SVG element `id`s")
ids = extract_ids_from_svg(svg_bytes)
if not ids:
    st.warning("No `id` attributes found in SVG. To map text, ensure SVG text elements have `id` attributes in Illustrator or Inkscape.")
else:
    st.write("Found SVG element `id`s (id : tag):")
    st.write(ids)

csv_cols = list(rows[0].keys())

st.subheader("Map fields")
mapping: Dict[str,str] = {}
for col in csv_cols:
    mapping[col] = st.selectbox(f"CSV column → SVG id for '{col}' (text)", options=[""] + [id for (id,tag) in ids], index=0, key=f"map_{col}")

st.markdown("**Image embedding (barcode)** — map a CSV column that contains EAN13 to an `<image id='...'>` element in the SVG (the script will embed a PNG data URI).")
embed_barcode_map = {}
for col in csv_cols:
    img_el = st.selectbox(f"CSV column → image-id for '{col}' (barcode) (optional)", options=[""] + [id for (id,tag) in ids], index=0, key=f"embed_{col}")
    if img_el:
        height_px = st.number_input(f"Barcode target height px for column '{col}'", value=80, min_value=10, key=f"embed_h_{col}")
        embed_barcode_map[col] = (img_el, int(height_px))

st.header("4. Preview a row and generate files")
row_index = st.number_input("Preview row index", min_value=0, max_value=len(rows)-1, value=0, step=1)
row = rows[int(row_index)]

svg_result_bytes = modify_svg(svg_bytes, mapping, row, embed_barcode_map)
st.subheader("Preview — resulting SVG (row {})".format(row_index))
try:
    st.components.v1.html(svg_result_bytes.decode("utf-8"), height=400)
except Exception:
    # fallback: show as downloadable file
    st.download_button("Download resulting SVG (preview) file", data=svg_result_bytes, file_name=f"preview_row{row_index}.svg")

# single SVG download
st.download_button("Download this modified SVG", data=svg_result_bytes, file_name=f"row_{row_index}.svg", mime="image/svg+xml")

# batch generate all rows -> zip
if st.button("Generate all rows and download ZIP of SVGs"):
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as z:
        for i, r in enumerate(rows):
            out_svg = modify_svg(svg_bytes, mapping, r, embed_barcode_map)
            name = r.get(next(iter(r.keys()),"row"), f"row{i+1}")
            name_san = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
            z.writestr(f"{i+1}_{name_san}.svg", out_svg)
    mem.seek(0)
    st.success("Generated ZIP with all templates.")
    st.download_button("Download generated SVGs (ZIP)", data=mem, file_name="generated_svgs.zip", mime="application/zip")

st.info("Note: The SVGs are edited inline and returned as SVG files. Open them in Illustrator/InkScape for raster export or printing. If you want raster (PNG) output server-side, I can add an optional `cairosvg` conversion step (requires additional dependency and system libs).")
