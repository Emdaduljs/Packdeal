# app.py
# -*- coding: utf-8 -*-
import io
import os
import re
import json
import base64
import zipfile
from pathlib import Path
import math
import pandas as pd
import streamlit as st
from lxml import etree
import cairosvg

# barcode utils (make sure your utils.py exposes these functions):
# - mm_to_px(mm)
# - render_barcode_svg_text(ean: str) -> str   # returns SVG markup (no white background if possible)
# - render_barcode_png_bytes(...) (not required anymore but may exist)
import utils
from PIL import Image as PILImage

# ---------- App config ----------
APP_TITLE = "Cuda Automation Layout"
ICON_PATH = "icon.png"
MAIN_BG = "cudamain.png"
SIDEBAR_BG = "cudapanel.png"

st.set_page_config(page_title=APP_TITLE,
                   page_icon=ICON_PATH if Path(ICON_PATH).exists() else None,
                   layout="wide")
st.title(APP_TITLE)

# ---------- Utility: embed background images via CSS ----------
def _b64_if_exists(path: str):
    p = Path(path)
    if not p.exists():
        return None
    data = p.read_bytes()
    return base64.b64encode(data).decode("ascii")

_main_b64 = _b64_if_exists(MAIN_BG)
_side_b64 = _b64_if_exists(SIDEBAR_BG)

custom_css = "<style>"
if _main_b64:
    custom_css += f"""
    .stApp {{
      background-image: url("data:image/png;base64,{_main_b64}");
      background-size: cover;
      background-repeat: no-repeat;
      background-attachment: local;
    }}
    """
if _side_b64:
    custom_css += f"""
    [data-testid="stSidebar"] > div:first-child {{
      background-image: url("data:image/png;base64,{_side_b64}");
      background-size: cover;
      background-repeat: no-repeat;
      background-attachment: local;
    }}
    """
custom_css += """
#floating_preview img { display:block; max-height:90vh; }
.upload-card {
  background: rgba(255,255,255,0.92);
  padding: 14px;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  margin-bottom: 10px;
}
.upload-card h3 { margin: 0 0 6px 0; }
"""
custom_css += "</style>"
st.markdown(custom_css, unsafe_allow_html=True)

# ---------- Auth (simple) ----------
USERS = {"Emdaduljs": "123", "Test1": "1234", "Test2": "12345", "Test3": "123456"}

with st.sidebar:
    if Path("ui_logo.png").exists():
        st.image("ui_logo.png", width=440)
    st.subheader("🔒 Login")
    username = st.selectbox("Username", list(USERS.keys()), key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    if password != USERS.get(username):
        st.warning("❌ Invalid username or password. Please login to continue.")
        st.stop()
    role = "Editor" if username == "Emdaduljs" else "User"
    st.success(f"✅ {role} ({username})")

# ---------- Helpers & SVG sanitization ----------
SVG_NS = "http://www.w3.org/2000/svg"

def _decode_bytes(b: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode("utf-8", errors="ignore")

def sanitize_for_preview(svg_bytes: bytes) -> str:
    if not svg_bytes:
        raise ValueError("Empty SVG input")
    raw = _decode_bytes(svg_bytes)
    raw = raw.lstrip("\ufeff")
    raw = re.sub(r"<!DOCTYPE[^>[]*(\[[^\]]*\])?>", "", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r"<!ENTITY[^>]*>", "", raw, flags=re.IGNORECASE | re.DOTALL)
    raw = re.sub(r'(<\/?)([A-Za-z0-9_]+):([A-Za-z0-9_\-]+)', lambda m: f"{m.group(1)}{m.group(2)}_{m.group(3)}", raw)
    raw = re.sub(r'(\s)([A-Za-z0-9_]+):([A-Za-z0-9_\-]+)=', lambda m: f"{m.group(1)}{m.group(2)}_{m.group(3)}=", raw)
    raw = re.sub(r'\s+xmlns:[a-zA-Z0-9_]+="[^"]+"', '', raw)
    raw = re.sub(r"&([A-Za-z0-9_]+);", lambda m: f"&{m.group(1)};" if m.group(1) in ("lt","gt","amp","quot","apos") else "", raw)

    parser = etree.XMLParser(ns_clean=True, recover=True, remove_blank_text=True)
    try:
        root = etree.fromstring(raw.encode("utf-8"), parser=parser)
    except Exception:
        m = re.search(r"(<svg\b[^>]*>.*?</svg>)", raw, flags=re.DOTALL | re.IGNORECASE)
        if m:
            frag = m.group(1)
            root = etree.fromstring(frag.encode("utf-8"), parser=parser)
        else:
            raise

    # ensure <svg> element
    if not (isinstance(root.tag, str) and root.tag.lower().endswith("svg")):
        cand = root.find(".//{http://www.w3.org/2000/svg}svg") or root.find(".//svg")
        if cand is not None:
            root = cand
        else:
            found = None
            for el in root.iter():
                if isinstance(el.tag, str) and el.tag.lower().endswith("svg"):
                    found = el
                    break
            if found is None:
                raise ValueError("No <svg> element found")
            root = found

    if not root.get("xmlns"):
        root.set("xmlns", SVG_NS)
    if "version" not in root.attrib:
        root.set("version", "1.1")

    # try to set viewBox if missing using width/height
    if "viewBox" not in root.attrib:
        w = root.get("width"); h = root.get("height")
        if w and h:
            try:
                wn = float(re.match(r"^\s*([0-9.+-eE]+)", w).group(1))
                hn = float(re.match(r"^\s*([0-9.+-eE]+)", h).group(1))
                root.set("viewBox", f"0 0 {wn} {hn}")
            except Exception:
                pass

    # normalize inline style
    for el in root.iter():
        style = el.get("style")
        if style:
            parts = [p.strip() for p in style.split(";") if p.strip()]
            seen = {}
            for p in parts:
                if ":" in p:
                    k, v = p.split(":", 1)
                    seen[k.strip()] = v.strip()
            el.set("style", "; ".join(f"{k}: {v}" for k, v in seen.items()))

    out = etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=False).decode("utf-8")
    return out

def ensure_svg_size(svg_text: str) -> str:
    if "width=" in svg_text and "height=" in svg_text:
        return svg_text
    m = re.search(r'viewBox="\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*"', svg_text)
    if m:
        w, h = m.group(3), m.group(4)
        return re.sub(r"<svg", f"<svg width='{w}' height='{h}'", svg_text, count=1)
    return re.sub(r"<svg", "<svg width='1000' height='1000'", svg_text, count=1)

def render_svg_to_png(svg_text: str, scale: float = 1.0) -> bytes:
    svg_text = ensure_svg_size(svg_text)
    internal_scale = max(1.0, scale * 2.0)
    return cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), scale=internal_scale)

def svg_to_pdf_bytes(svg_text: str) -> bytes:
    svg_text = ensure_svg_size(svg_text)
    return cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"))

# ---------- Helper: parse svg barcode dims ----------
def _parse_svg_dimensions(svg_text: str):
    """
    Return (width_px, height_px) for an SVG string. Uses viewBox first, then width/height attrs.
    """
    try:
        parser = etree.XMLParser(ns_clean=True, recover=True, remove_blank_text=True)
        root = etree.fromstring(svg_text.encode("utf-8"), parser=parser)
        vb = root.get("viewBox")
        if vb:
            parts = [float(p) for p in vb.strip().split()]
            if len(parts) == 4:
                return parts[2], parts[3]
        w_attr = root.get("width")
        h_attr = root.get("height")
        def _attr_to_px(v):
            if not v:
                return None
            v = str(v).strip()
            if v.endswith("mm"):
                return utils.mm_to_px(float(v[:-2]))
            if v.endswith("px"):
                try:
                    return float(v[:-2])
                except Exception:
                    return None
            if v.endswith("pt"):
                try:
                    return float(v[:-2]) * 1.3333333
                except Exception:
                    return None
            try:
                return float(re.match(r"^([0-9.+-eE]+)", v).group(1))
            except Exception:
                return None
        wpx = _attr_to_px(w_attr)
        hpx = _attr_to_px(h_attr)
        if wpx and hpx:
            return wpx, hpx
    except Exception:
        pass
    return 1000.0, 1000.0

# ---------- placeholders mapping ----------
def find_placeholders(svg_text: str):
    return sorted(set(re.findall(r"\{\{\s*([A-Za-z0-9_\-\.]+)\s*\}\}", svg_text)))

def _remove_white_background_rects(frag_root):
    """
    Remove rect elements that appear to be white background covering the viewport.
    Conservative: only removes <rect> with fill white-like or opacity=1 that span a large area.
    """
    to_remove = []
    for el in list(frag_root.iter()):
        if el.tag.lower().endswith("rect"):
            fill = (el.get("fill") or "").strip().lower()
            opacity = (el.get("opacity") or "").strip().lower()
            # check fills that indicate white background
            if fill in ("#fff", "#ffffff", "white", "rgb(255,255,255)") or fill == "":
                # if fill blank, check style attribute
                style = el.get("style") or ""
                if "fill:#fff" in style or "fill:#ffffff" in style or "fill:white" in style:
                    to_remove.append(el)
                elif fill in ("#fff", "#ffffff", "white"):
                    to_remove.append(el)
            # also if explicit opacity 1 and very large rect (we can't measure exact dims reliably here)
            # We'll remove rect that have width/height attributes equal to viewBox or large numbers:
            try:
                w = float(el.get("width") or 0)
                h = float(el.get("height") or 0)
                if w > 0 and h > 0 and (w > 500 or h > 500):
                    # likely background (conservative)
                    to_remove.append(el)
            except Exception:
                pass
    for r in to_remove:
        parent = r.getparent()
        if parent is not None:
            parent.remove(r)

def apply_mapping_to_svg(svg_text: str, mapping: dict, record: dict) -> str:
    """
    Enhanced apply_mapping_to_svg:
     - Text substitution (default)
     - Barcode EAN13: inserts inline vector barcode, strips white background rectangles,
       scales to requested height (mm) and applies dx/dy/scale mapping transforms.
    """
    parser = etree.XMLParser(ns_clean=True, recover=True, remove_blank_text=True)
    root = etree.fromstring(svg_text.encode("utf-8"), parser=parser)

    text_nodes = list(root.findall(".//{http://www.w3.org/2000/svg}text")) + list(root.findall(".//text"))
    added_xlink = False

    for text_elem in text_nodes:
        content = "".join(text_elem.itertext()) or ""
        matches = re.findall(r"\{\{\s*([A-Za-z0-9_\-\.]+)\s*\}\}", content)
        if not matches:
            continue

        # find barcode placeholders (if any) in this text node
        barcode_placeholders = [ph for ph in matches if mapping.get(ph, {}).get("type", "Text").startswith("Barcode")]
        if barcode_placeholders and len(matches) == 1:
            ph = barcode_placeholders[0]
            cfg = mapping.get(ph, {"col": ph, "align": "Left"})
            col = cfg.get("col", ph)
            val = record.get(col, "")
            if val is None or str(val).strip() == "":
                # clear text if no data
                for child in list(text_elem):
                    text_elem.remove(child)
                text_elem.text = ""
                continue

            # requested height and px conversion
            height_mm = float(cfg.get("height_mm", 25.0) or 25.0)
            desired_h_px = utils.mm_to_px(height_mm)

            # get text position (if numeric)
            x_val = text_elem.get("x") or text_elem.get("dx") or "0"
            y_val = text_elem.get("y") or text_elem.get("dy") or "0"
            try:
                xf = float(x_val)
            except Exception:
                xf = 0.0
            try:
                yf = float(y_val)
            except Exception:
                yf = 0.0

            # mapping adjustments
            try:
                cfg_dx = float(cfg.get("dx", 0) or 0)
            except Exception:
                cfg_dx = 0.0
            try:
                cfg_dy = float(cfg.get("dy", 0) or 0)
            except Exception:
                cfg_dy = 0.0
            try:
                cfg_scale = float(cfg.get("scale", 1.0) or 1.0)
            except Exception:
                cfg_scale = 1.0

            map_type = mapping.get(ph, {}).get("type", "Text")

            # VECTOR insertion (only option now)
            if map_type.startswith("Barcode"):
                try:
                    svg_bar = utils.render_barcode_svg_text(val)
                    # parse barcode svg fragment to an Element
                    parser2 = etree.XMLParser(ns_clean=True, recover=True, remove_blank_text=True)
                    frag = etree.fromstring(svg_bar.encode("utf-8"), parser=parser2)

                    # remove white background rects conservatively
                    _remove_white_background_rects(frag)

                    orig_w, orig_h = _parse_svg_dimensions(svg_bar)
                    if orig_h == 0:
                        scale_by_height = 1.0
                    else:
                        scale_by_height = float(desired_h_px) / float(orig_h)

                    # Compose total transform:
                    # place at (xf + cfg_dx, yf + cfg_dy) and scale = scale_by_height * cfg_scale
                    total_tx = xf + cfg_dx
                    total_ty = yf + cfg_dy
                    total_scale = scale_by_height * cfg_scale

                    # create group and import children
                    g = etree.Element("{http://www.w3.org/2000/svg}g")
                    g.set("transform", f"translate({total_tx},{total_ty}) scale({total_scale})")

                    # import children from frag (skip outer <svg> wrapper attributes)
                    for child in list(frag):
                        frag.remove(child)
                        g.append(child)

                    parent = text_elem.getparent()
                    if parent is None:
                        text_elem.text = ""
                        root.append(g)
                    else:
                        parent.replace(text_elem, g)
                except Exception as e:
                    for child in list(text_elem):
                        text_elem.remove(child)
                    text_elem.text = f"[barcode svg error: {e}]"
                continue

        # Fallback - textual substitution (handles multiple placeholders)
        new_text = content
        for ph in matches:
            cfg = mapping.get(ph, {"col": ph, "align": "Left"})
            col = cfg.get("col", ph)
            val = record.get(col, "")
            if val is None:
                val = ""
            new_text = re.sub(r"\{\{\s*%s\s*\}\}" % re.escape(ph), str(val), new_text)

        # remove child tspans and re-split lines preserving line structure
        for child in list(text_elem):
            text_elem.remove(child)
        lines = str(new_text).splitlines() or [""]
        text_elem.text = lines[0]
        for ln in lines[1:]:
            tspan = etree.Element("{http://www.w3.org/2000/svg}tspan")
            if text_elem.get("x"):
                tspan.set("x", text_elem.get("x"))
            tspan.set("dy", "1em")
            tspan.text = ln
            text_elem.append(tspan)

        align_map = {"Left": "start", "Center": "middle", "Right": "end", "Justify": "start"}
        cfg0 = mapping.get(matches[0], {})
        text_elem.set("text-anchor", align_map.get(cfg0.get("align", "Left"), "start"))
        # transform support (dx,dy,scale) applied to text element
        try:
            dx = float(cfg0.get("dx", 0))
            dy = float(cfg0.get("dy", 0))
            scale_val = float(cfg0.get("scale", 1.0))
            old = text_elem.get("transform", "")
            tf = f" translate({dx},{dy}) scale({scale_val})"
            text_elem.set("transform", (old + tf).strip())
        except Exception:
            pass

    # xlink namespace not needed for vector barcodes, but keep safety
    if added_xlink:
        try:
            root.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
        except Exception:
            pass

    return etree.tostring(root, encoding="utf-8").decode("utf-8")

def bundle_zip(named_files: list[tuple[str, bytes]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, data in named_files:
            zf.writestr(fname, data)
    return buf.getvalue()

# ---------- Main UI ----------
col_tpl, col_data = st.columns([2,5])

with col_tpl:
    st.subheader("1) Upload SVG Template")
    svg_file = st.file_uploader("SVG Template (.svg)", type=["svg"])
with col_data:
    st.subheader("2) Upload Data")
    data_file = st.file_uploader("CSV or XML", type=["csv", "xml"])
    st.caption("Template & Data are shown below (left: mapping, right: preview).")

# session defaults
if "preview_scale" not in st.session_state:
    st.session_state.preview_scale = 1.0
if "mapping" not in st.session_state:
    st.session_state.mapping = {}

with st.sidebar:
    st.header("Preview & Export controls")
    st.session_state.preview_scale = st.slider("Preview scale", 0.25, 3.0, st.session_state.preview_scale, step=0.25)
    colz1, colz2 = st.columns([1,1])
    if colz1.button("−"):
        st.session_state.preview_scale = max(0.25, st.session_state.preview_scale - 0.25)
    if colz2.button("+"):
        st.session_state.preview_scale = min(3.0, st.session_state.preview_scale + 0.25)
    st.markdown("---")
    st.header("Preview Pin")
    pin_preview = st.checkbox("Pin preview (floating overlay)", value=False)
    pin_width_vw = st.slider("Pinned preview width (vw)", 15, 60, 30)
    st.markdown("---")
    st.header("Export")
    export_mode = st.radio("Export Mode", ["One per record (ZIP)", "Single combined PDF"], index=0)
    export_format = st.radio("Export format", ["SVG only", "PDF only", "PDF + SVG"], index=0)
    name_field_hint = st.text_input("Filename field (optional)")
    st.caption("Only rows that have mapped placeholder values will be exported.")

# ---------- Load data ----------
df = None
if data_file:
    try:
        if data_file.name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(data_file)
            except Exception:
                data_file.seek(0)
                df = pd.read_csv(data_file, encoding="latin-1")
        else:
            txt = _decode_bytes(data_file.read())
            root = etree.fromstring(txt.encode("utf-8"))
            records = [{child.tag: child.text for child in row} for row in root]
            df = pd.DataFrame(records)
        if role == "Editor":
            st.success(f"Loaded {len(df)} rows × {len(df.columns)} cols")
    except Exception as e:
        st.error(f"Failed to parse data file: {e}")

# ---------- Read & sanitize template ----------
sanitized_template = None
placeholders = []
raw_svg_bytes = None
if svg_file:
    raw_svg_bytes = svg_file.read()
    try:
        sanitized_template = sanitize_for_preview(raw_svg_bytes)
    except Exception as e:
        st.error(f"❌ Sanitized SVG failed validation; inspect template. ({e})")
        sanitized_template = None

if sanitized_template:
    if role == "Editor":
        st.success("Template sanitized and ready.")
    placeholders = find_placeholders(sanitized_template)
else:
    if svg_file:
        st.warning("Uploaded SVG invalid or could not be sanitized.")

# ---------- Mapping (left) and Preview (right) ----------
left_col, right_col = st.columns([2,5])

with left_col:
    st.subheader("Placeholders & Mapping")

    st.markdown("**Mapping record (save / load)**")
    mapping_file = st.file_uploader("Upload mapping (JSON or CSV) to restore", type=["json", "csv"], key="mapping_upload")
    if mapping_file is not None:
        try:
            raw = mapping_file.read()
            if mapping_file.name.lower().endswith(".json"):
                loaded = json.loads(raw.decode("utf-8"))
                if isinstance(loaded, dict):
                    st.session_state.mapping = loaded
                    st.success("Mapping restored from JSON.")
                else:
                    st.error("JSON mapping must be an object mapping placeholder→config.")
            else:
                # CSV: expect columns: placeholder,col,align,dx,dy,scale,type,height_mm
                dfmap = pd.read_csv(io.BytesIO(raw))
                newmap = {}
                for _, r in dfmap.iterrows():
                    ph = str(r.get("placeholder") or r.get("ph") or r.get("name") or "")
                    if not ph:
                        continue
                    newmap[ph] = {
                        "col": str(r.get("col", "")),
                        "align": str(r.get("align", "Left")),
                        "dx": float(r.get("dx", 0.0) or 0.0),
                        "dy": float(r.get("dy", 0.0) or 0.0),
                        "scale": float(r.get("scale", 1.0) or 1.0),
                        "type": str(r.get("type", "Text")),
                        "height_mm": float(r.get("height_mm", 25.0) or 25.0)
                    }
                if newmap:
                    st.session_state.mapping = newmap
                    st.success("Mapping restored from CSV.")
                else:
                    st.error("CSV mapping file parsing found no records.")
        except Exception as e:
            st.error(f"Failed to load mapping: {e}")

    current_mapping = st.session_state.get("mapping", {})

    try:
        mapping_json_dump = json.dumps(current_mapping, ensure_ascii=False, indent=2)
        st.download_button("Download mapping (JSON)", mapping_json_dump.encode("utf-8"), file_name="mapping.json", help="Download current mapping as JSON")
    except Exception:
        pass

    try:
        csv_buf = io.StringIO()
        csv_buf.write("placeholder,col,align,dx,dy,scale,type,height_mm\n")
        for ph, cfg in current_mapping.items():
            csv_buf.write(
                f"{ph},{cfg.get('col','')},{cfg.get('align','Left')},{cfg.get('dx',0)},{cfg.get('dy',0)},{cfg.get('scale',1.0)},{cfg.get('type','Text')},{cfg.get('height_mm',25.0)}\n"
            )
        st.download_button("Download mapping (CSV)", csv_buf.getvalue().encode("utf-8"), file_name="mapping.csv", help="Download current mapping as CSV")
    except Exception:
        pass

    st.markdown("---")

    if not placeholders:
        st.info("Placeholders not found (use {{field}} in template).")
    else:
        st.markdown('<div style="max-height:520px; overflow:auto; padding-right:6px">', unsafe_allow_html=True)
        for ph in placeholders:
            with st.expander(ph, expanded=False):
                cols = st.columns([2,1,1])
                options = [ph] + (list(df.columns) if df is not None else [])
                prev = st.session_state.mapping.get(ph, {})
                default_idx = 0
                if prev.get("col") in options:
                    default_idx = options.index(prev.get("col"))
                col_selected = cols[0].selectbox("Map column", options, index=default_idx, key=f"mapcol_{ph}")
                align_index = 0
                if prev.get("align") in ("Left", "Center", "Right"):
                    align_index = ["Left", "Center", "Right"].index(prev.get("align"))
                align_selected = cols[1].selectbox("Align", ["Left", "Center", "Right"], index=align_index, key=f"align_{ph}")
                dx = st.number_input("dx (px)", value=float(prev.get("dx", 0.0)), step=0.5, format="%.1f", key=f"dx_{ph}")
                dy = st.number_input("dy (px)", value=float(prev.get("dy", 0.0)), step=0.5, format="%.1f", key=f"dy_{ph}")
                scale = st.slider("scale", 0.1, 3.0, float(prev.get("scale", 1.0)), step=0.01, key=f"scale_{ph}")

                # Type selector: Text or Barcode EAN13 (vector only)
                type_default = prev.get("type", "Text")
                type_selected = st.selectbox("Type", ["Text", "Barcode EAN13"],
                                            index=0 if type_default != "Barcode EAN13" else 1,
                                            key=f"type_{ph}")

                height_mm_val = prev.get("height_mm", 25.0)
                if type_selected == "Barcode EAN13":
                    height_mm_val = st.number_input("Barcode height (mm)", value=float(height_mm_val), step=0.5, key=f"height_mm_{ph}")

                st.session_state.mapping[ph] = {"col": col_selected, "align": align_selected, "dx": dx, "dy": dy, "scale": scale, "type": type_selected, "height_mm": float(height_mm_val)}
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Scroll to edit placeholders. Changes persist in this session.")

with right_col:
    st.subheader("Live Preview")
    preview_box = st.empty()
    if not sanitized_template:
        preview_box.info("Upload a valid SVG template first.")
    elif df is None or df.empty:
        preview_box.info("Upload a data file (CSV/XML) and map placeholders to preview.")
    elif not st.session_state.get("mapping"):
        preview_box.info("Map placeholders to see a live preview.")
    else:
        first_valid_idx = None
        for i, row in df.iterrows():
            rec = {str(k): ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
            for ph, cfg in st.session_state.mapping.items():
                if rec.get(cfg["col"], "") not in ("", None):
                    first_valid_idx = i
                    break
            if first_valid_idx is not None:
                break
        if first_valid_idx is None:
            preview_box.warning("No rows contain values for the mapped placeholders; preview skipped.")
        else:
            idx_select = st.number_input("Preview row (1-based)", min_value=1, max_value=len(df), value=first_valid_idx+1, step=1)
            preview_idx = int(idx_select) - 1
            rec = {str(k): ("" if pd.isna(v) else v) for k, v in df.iloc[preview_idx].to_dict().items()}
            try:
                filled = apply_mapping_to_svg(sanitized_template, st.session_state.mapping, rec)
                png = render_svg_to_png(filled, scale=st.session_state.preview_scale)
                preview_box.image(png, caption=f"Preview of record {preview_idx+1}", use_container_width=True)
                if pin_preview:
                    b64 = base64.b64encode(png).decode("ascii")
                    overlay_html = f'''
                    <div id="floating_preview" style="position:fixed; bottom:20px; right:20px; z-index:9999;
                         border:1px solid #ddd; background:#fff; padding:6px; box-shadow:0 6px 18px rgba(0,0,0,0.2);">
                      <img src="data:image/png;base64,{b64}" style="max-width:{pin_width_vw}vw; height:auto; display:block;" />
                    </div>
                    '''
                    st.markdown(overlay_html, unsafe_allow_html=True)
            except Exception as e:
                preview_box.error(f"Preview rendering failed: {e}")

# ---------- Generate / Export ----------
if st.button("Generate") and sanitized_template and df is not None and not df.empty and st.session_state.get("mapping"):
    files_out = []
    pdf_pages = []
    for idx, row in df.iterrows():
        rec = {str(k): ("" if pd.isna(v) else v) for k, v in row.to_dict().items()}
        matched = any(rec.get(cfg["col"], "") not in ("", None) for cfg in st.session_state.mapping.values())
        if not matched:
            continue
        try:
            final_svg = apply_mapping_to_svg(sanitized_template, st.session_state.mapping, rec)
        except Exception as e:
            st.warning(f"Row {idx+1}: mapping error: {e} — skipped")
            continue
        fname_base = rec.get(name_field_hint, f"record_{idx+1:03d}") if name_field_hint else f"record_{idx+1:03d}"
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", fname_base)
        if export_format in ("SVG only", "PDF + SVG"):
            files_out.append((f"{safe}.svg", final_svg.encode("utf-8")))
        if export_format in ("PDF only", "PDF + SVG") or export_mode == "Single combined PDF":
            try:
                pdf_bytes = svg_to_pdf_bytes(final_svg)
                if export_mode.startswith("One"):
                    files_out.append((f"{safe}.pdf", pdf_bytes))
                else:
                    pdf_pages.append(pdf_bytes)
            except Exception as e:
                st.warning(f"Row {idx+1}: PDF generation failed: {e}")

    if export_mode == "Single combined PDF" and pdf_pages:
        combined = None
        try:
            from PyPDF2 import PdfReader, PdfWriter
            writer = PdfWriter()
            for pb in pdf_pages:
                reader = PdfReader(io.BytesIO(pb))
                for p in reader.pages:
                    writer.add_page(p)
            outb = io.BytesIO()
            writer.write(outb)
            combined = outb.getvalue()
        except Exception:
            for i, pb in enumerate(pdf_pages, start=1):
                files_out.append((f"page_{i:03d}.pdf", pb))
        if combined:
            files_out.append(("combined.pdf", combined))

    if files_out:
        st.download_button("Download ZIP", bundle_zip(files_out), file_name="variable_files.zip")
        st.success(f"Exported {len(files_out)} files.")
    else:
        st.warning("No rows matched placeholders or no files were generated.")

# Footer note for editors
if role == "Editor":
    st.markdown("---")
    st.markdown("**Editor note:** Pin the preview to keep it visible while you scroll the page.")
