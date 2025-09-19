# utils.py  (UPDATED)
# Adds robust EAN-13 support: checksum calculation, normalization, PNG bytes and SVG text
# Backwards-compatible: keeps existing render_label_image + render_barcode_image behavior

from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter, SVGWriter
import io
from typing import Optional
import base64

DPI_DEFAULT = 300

def mm_to_px(mm: float, dpi: int = DPI_DEFAULT) -> int:
    inches = mm / 25.4
    return max(1, int(round(inches * dpi)))

# ---------------- EAN-13 helpers ----------------
def calculate_ean13_checksum(number12: str) -> str:
    """
    Calculate the EAN-13 checksum digit for a 12-digit numeric string.
    Digit-by-digit arithmetic to avoid encoding surprises.
    """
    number12 = ''.join(ch for ch in str(number12) if ch.isdigit())
    if len(number12) != 12:
        raise ValueError("checksum requires 12 digits")
    total = 0
    for i, ch in enumerate(number12):
        d = ord(ch) - 48
        weight = 1 if (i % 2 == 0) else 3
        total += d * weight
    check = (10 - (total % 10)) % 10
    return str(check)

def normalize_to_ean13(value: str) -> Optional[str]:
    """
    Normalize an input value to canonical 13-digit EAN string.
    - strips non-digits
    - accepts 12 or 13 digits
    - if 12 digits -> append computed checksum
    - if 13 digits -> validate checksum and replace if incorrect
    - returns None for other lengths
    """
    s = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(s) == 12:
        return s + calculate_ean13_checksum(s)
    if len(s) == 13:
        chk = calculate_ean13_checksum(s[:12])
        return s if chk == s[-1] else s[:12] + chk
    return None

# ---------------- Barcode rendering ----------------
def render_barcode_image(ean: str, height_mm: float, dpi: int = DPI_DEFAULT) -> Image.Image:
    """
    Return a PIL Image (RGBA) representing the barcode as PNG raster.
    Kept for backwards compatibility with the existing app code.
    """
    canonical = normalize_to_ean13(ean)
    if canonical is None:
        raise ValueError(f"EAN not normalizable: {ean}")

    # Use ImageWriter to render PNG via pillow
    EAN = barcode.get_barcode_class('ean13')
    writer = ImageWriter()

    # python-barcode's writer options are in "mm"/units; here we pick module_height relatively
    # but to remain compatible with prior behaviour we compute pixel heights and pass them
    module_height_px = mm_to_px(height_mm, dpi)
    options = {
        'module_height': module_height_px,
        'font_size': 18,
        'text_distance': 4,
        'quiet_zone': 6.0,
        'dpi': dpi,
    }

    obj = EAN(canonical, writer=writer)
    bio = io.BytesIO()
    obj.write(bio, options)
    bio.seek(0)
    img = Image.open(bio).convert('RGBA')
    return img


def render_barcode_png_bytes(ean: str, height_mm: float, dpi: int = DPI_DEFAULT) -> bytes:
    """
    Return PNG bytes for the given EAN (canonicalized). Useful for embedding into SVG as data URI.
    """
    img = render_barcode_image(ean, height_mm, dpi=dpi)
    out = io.BytesIO()
    img.save(out, format='PNG')
    return out.getvalue()


def render_barcode_svg_text(ean: str, writer_options: dict = None) -> str:
    """
    Return the barcode as an SVG text string. Uses python-barcode + SVGWriter.
    writer_options (optional) are passed to the writer.write call.
    """
    canonical = normalize_to_ean13(ean)
    if canonical is None:
        raise ValueError(f"EAN not normalizable: {ean}")

    EAN = barcode.get_barcode_class('ean13')
    writer = SVGWriter()
    obj = EAN(canonical, writer=writer)
    bio = io.BytesIO()
    if writer_options is None:
        writer_options = {}
    # python-barcode SVGWriter writes text (utf-8 bytes)
    obj.write(bio, writer_options)
    bio.seek(0)
    raw = bio.read()
    try:
        return raw.decode('utf-8')
    except Exception:
        return raw.decode('utf-8', errors='ignore')


def png_bytes_to_data_uri(png_bytes: bytes) -> str:
    return 'data:image/png;base64,' + base64.b64encode(png_bytes).decode('ascii')

# ---------------- Label renderer (keeps previous behaviour) ----------------

def render_label_image(brand: str, name: str, price: str, ean: str,
                       width_mm: float = 80.0, height_mm: float = 50.0,
                       dpi: int = DPI_DEFAULT, font_path: Optional[str] = None) -> Image.Image:
    w = mm_to_px(width_mm, dpi)
    h = mm_to_px(height_mm, dpi)
    bg_color = (255, 255, 255, 255)
    label = Image.new("RGBA", (w, h), bg_color)
    draw = ImageDraw.Draw(label)

    # Fonts (fallback to default PIL font if custom not provided)
    try:
        if font_path:
            font_bold = ImageFont.truetype(font_path, size=int(h*0.13))
            font_regular = ImageFont.truetype(font_path, size=int(h*0.10))
        else:
            font_bold = ImageFont.truetype("arial.ttf", size=int(h*0.13))
            font_regular = ImageFont.truetype("arial.ttf", size=int(h*0.10))
    except Exception:
        font_bold = ImageFont.load_default()
        font_regular = ImageFont.load_default()

    # Layout: simple left text, right barcode
    padding = int(w * 0.04)
    # Draw brand and name
    y = padding
    draw.text((padding, y), brand.upper(), font=font_bold, fill=(30,30,30))
    y += int(h * 0.16)
    draw.text((padding, y), name, font=font_regular, fill=(60,60,60))
    # Price at bottom-left
    ptext = f"{price}"
    psize = draw.textsize(ptext, font=font_bold)
    draw.text((padding, h - padding - psize[1]), ptext, font=font_bold, fill=(0,0,0))

    # Render barcode and paste on right side
    try:
        bc_img = render_barcode_image(ean, height_mm * 0.45, dpi=dpi)
        # resize barcode so it fits approximately right half
        max_bc_w = int(w * 0.48)
        scale = min(1.0, max_bc_w / bc_img.width)
        bc_w = int(bc_img.width * scale)
        bc_h = int(bc_img.height * scale)
        bc_img = bc_img.resize((bc_w, bc_h), resample=Image.LANCZOS)
        bc_x = w - bc_w - padding
        bc_y = h - bc_h - padding
        label.paste(bc_img, (bc_x, bc_y), bc_img)
    except Exception:
        # If barcode generation fails, draw placeholder box
        draw.rectangle([w - int(w*0.48) - padding, h - int(h*0.35) - padding, w - padding, h - padding], outline=(0,0,0))

    return label


# ---------------- Integration notes (for app.py) ----------------
#
# The updated utils include helpers to produce PNG bytes (render_barcode_png_bytes)
# and SVG text (render_barcode_svg_text). To embed barcodes into an SVG template
# in app.py you can do one of the following:
#
# 1) Replace a <text> placeholder with an <image> element whose href is a data URI
#    using png_bytes_to_data_uri(render_barcode_png_bytes(ean, height_mm)).
#    Example: <image x="..." y="..." width="..." height="..." href="data:image/png;base64,..." />
#
# 2) Insert the SVG markup returned by render_barcode_svg_text(ean) inline into the template
#    (requires sanitization to avoid nested <svg> size issues). Prefer option (1) as it's simpler
#    and works well with your existing `ensure_svg_size` + cairosvg pipeline.
#
# Suggested minimal change in app.py (pseudocode):
# - In the mapping UI add an additional control per-placeholder: a Type selector ["Text","Barcode (EAN13)"]
# - When apply_mapping_to_svg encounters a placeholder with cfg['type']=='Barcode', generate png bytes:
#       png = render_barcode_png_bytes(rec[cfg['col']], height_mm=cfg.get('height_mm', 25))
#       datauri = png_bytes_to_data_uri(png)
#   Then replace the text node in the SVG with an <image ... href="{datauri}" /> element. Use cfg.scale/dx/dy
#   to set width/height/x/y attributes.
#
# If you want, I can also prepare the exact patch for app.py to add the mapping UI and SVG insertion logic.
#
# End of utils.py update.
