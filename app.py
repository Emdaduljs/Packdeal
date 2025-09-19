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
from PIL import Image, ImageDraw, ImageFont

ASSETS = Path("assets")
SVG_DIR = ASSETS / "svg"
SVG_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Packaging Design Automation", layout="wide")

st.title("Packaging Design Automation — CSV → editable SVG template → Download")
st.write("Upload CSV rows, pick an SVG layout, map CSV columns to SVG `id`s, preview and download the final files.")

# ----------------- EAN13 pattern & PIL renderer (no external barcode lib) -----------------
def calculate_checksum_12(number12: str) -> str:
    s = 0
    for i, ch in enumerate(number12):
        n = int(ch)
        s += n if (i % 2 == 0) else n * 3
    check = (10 - (s % 10)) % 10
    return str(check)

def ean13_pattern(number13: str) -> str:
    # returns string of '0'/'1' bits representing full barcode (95 modules)
    # using standard L/G/R tables and parity
    codes = {
        "L": ["0001101","0011001","0010011","0111101","0100011","0110001","0101111","0111011","0110111","0001011"],
        "G": ["0100111","0110011","0011011","0100001","0011101","0111001","0000101","0010001","0001001","0010111"],
        "R": ["1110010","1100110","1101100","1000010","1011100","1001110","1010000","1000100","1001000","1110100"]
    }
    parity = {
        0:"LLLLLL",1:"LLGLGG",2:"LLGGLG",3:"LLGGGL",
        4:"LGLLGG",5:"LGGLLG",6:"LGGGLL",7:"LGLGLG",
        8:"LGLGGL",9:"LGGLGL"
    }
    # ensure digits only
    digits = "".join([c for c in number13 if c.isdigit()])
    if len(digits) == 12:
        digits = digits + calculate_checksum_12(digits)
    if len(digits) != 13:
        raise ValueError("EAN13 needs 12 or 13 digits")
    first = int(digits[0])
    pattern_left = parity[first]
    left_bits = ""
    for i in range(1,7):
        left_bits += codes[pattern_left[i-1]][int(digits[i])]
    right_bits = ""
    for i in range(7,13):
        right_bits += codes["R"][int(digits[i])]
    full = "101" + left_bits + "01010" + right_bits + "101"
    return full

def generate_ean13_data_uri(ean_value: str, bar_height_px: int = 80, module_width_px: int = None, include_human_text: bool = True) -> str:
    """
    Create a PNG data URI with the EAN-13 bars drawn using Pillow.
    - bar_height_px: height of bars in pixels (excluding human-readable text).
    - module_width_px: if None will be chosen so overall barcode width ~ 190-350px.
    """
    digits_only = "".join([c for c in ean_value if c.isdigit()])
    if len(digits_only) == 12:
        digits_only = digits_only + calculate_checksum_12(digits_only)
    if len(digits_only) != 13:
        # produce small transparent placeholder to avoid breaking
        im = Image.new("RGBA", (200, bar_height_px + 30), (255,255,255,0))
        buf = io.BytesIO(); im.save(buf, format="PNG"); return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    pattern = ean13_pattern(digits_only)  # 95 modules
    modules = len(pattern)  # should be 95

    # Decide module width if not provided
    if not module_width_px:
        # aim for width between 190 and 380 px
        target = 260
        module_width_px = max(1, int(round(target / modules)))

    quiet_modules = int(10 * (1))  # quiet zone in modules (we'll multiply by module_width_px)
    q_px = quiet_modules * module_width_px
    total_w = modules * module_width_px + 2 * q_px
    text_area = 18 if include_human_text else 0
    img_h = bar_height_px + text_area + 6

    im = Image.new("RGBA", (total_w, img_h), (255,255,255,255))
    draw = ImageDraw.Draw(im)

    # Draw bars
    x = q_px
    # Optional guard extension: first 3, center guards, last 3 - make those taller
    for i, bit in enumerate(pattern):
        if bit == "1":
            # determine if this module is part of guard sets:
            extend = False
            # left-most guard bits: module positions 0..2 (in my "pattern" indexing these are inside "101" start)
            # the standard guard indexes correspond when counting across the full 95 bits
            # For simplicity, treat the initial and final 3 modules and center 5 modules as 'guard' extenders
            if i < 3 or (46 <= i <= 48) or i >= (modules - 3):
                extend = True
            h = bar_height_px + (6 if extend else 0)
            draw.rectangle([ (x, 0), (x + module_width_px - 1, h) ], fill=(0,0,0))
        x += module_width_px

    # Human-readable text below (digits spaced)
    if include_human_text:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        except Exception:
            font = ImageFont.load_default()
        text = digits_only[0] + " " + digits_only[1:7] + " " + digits_only[7:13]
        w_text, h_text = draw.textsize(text, font=font)
        tx = (total_w - w_text) // 2
        draw.text((tx, bar_height_px + 2), text, font=font, fill=(0,0,0))

    # Convert to PNG and to data URI
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    data = buf.getvalue()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

# ----------------- SVG helpers (unchanged) -----------------
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
    out = []
    try:
        root = ET.fromstring(svg_bytes.decode("utf-8"))
    except Exception:
        root = ET.fromstring(svg_bytes)
    for el in root.iter():
        elid = el.attrib.get("id")
        if elid:
            tag = el.tag
            if '}' in tag:
                tag = tag.split('}',1)[1]
            out.append((elid, tag))
    return out

def modify_svg(svg_bytes: bytes, mapping: Dict[str,str], row: Dict[str,str],
               embed_barcode_map: Dict[str,Tuple[str,int]]) -> bytes:
    try:
        root = ET.fromstring(svg_bytes.decode("utf-8"))
    except Exception:
        root = ET.fromstring(svg_bytes)

    for csv_col, elid in mapping.items():
        value = row.get(csv_col,"")
        if not elid: continue
        el = None
        for node in root.iter():
            if node.attrib.get("id") == elid:
                el = node
                break
        if el is not None:
            if el.tag.lower().endswith("text") or '}' in el.tag and el.tag.split('}',1)[1]=='text':
                for c in list(el):
                    el.remove(c)
                el.text = str(value)
            else:
                el.attrib['data-text'] = str(value)

    for csv_col, (img_elid, height_px) in embed_barcode_map.items():
        ean_val = row.get(csv_col, "")
        if not ean_val: continue
        img_data = generate_ean13_data_uri(ean_val, bar_height_px=height_px)
        img_el = None
        for node in root.iter():
            if node.attrib.get("id") == img_elid:
                img_el = node
                break
        if img_el is not None:
            XLINK = "{http://www.w3.org/1999/xlink}href"
            if XLINK in img_el.attrib:
                img_el.attrib[XLINK] = img_data
            else:
                img_el.attrib['href'] = img_data

    svg_out = ET.tostring(root, encoding="utf-8", method="xml")
    return svg_out

# ----------------- App UI (unchanged behavior) -----------------
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
        dest = SVG_DIR / uploaded_svg.name
        dest.write_bytes(read_svg_bytes(uploaded_svg))
        st.success(f"Saved uploaded template to {dest}")
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
    svg_text = svg_bytes.decode("utf-8", errors="ignore")
    st.markdown("**SVG preview (render):**")
    st.components.v1.html(svg_text, height=400)

st.header("3. Map CSV columns to SVG element `id`s")
ids = extract_ids_from_svg(svg_bytes)
if not ids:
    st.warning("No `id` attributes found in SVG. Add ids to text elements.")
else:
    st.write("Found SVG element `id`s (id : tag):")
    st.write(ids)

csv_cols = list(rows[0].keys())

st.subheader("Map fields")
mapping: Dict[str,str] = {}
for col in csv_cols:
    mapping[col] = st.selectbox(f"CSV column → SVG id for '{col}' (text)", options=[""] + [id for (id,tag) in ids], index=0, key=f"map_{col}")

st.markdown("**Image embedding (barcode)** — map a CSV column that contains EAN13 to an `<image id='...'>` element in the SVG.")
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
    st.download_button("Download resulting SVG (preview) file", data=svg_result_bytes, file_name=f"preview_row{row_index}.svg")

st.download_button("Download this modified SVG", data=svg_result_bytes, file_name=f"row_{row_index}.svg", mime="image/svg+xml")

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

st.info("SVGs are returned as edited SVG files. Open them in Illustrator/InkScape for raster export. If you want server-side PNG export, I can add that optionally.")
