# utils.py
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter
import io
from typing import Optional

DPI_DEFAULT = 300

def mm_to_px(mm: float, dpi: int = DPI_DEFAULT) -> int:
    inches = mm / 25.4
    return max(1, int(round(inches * dpi)))

def render_barcode_image(ean: str, height_mm: float, dpi: int = DPI_DEFAULT) -> Image.Image:
    # Using python-barcode writer with PIL (ImageWriter)
    EAN = barcode.get_barcode_class('ean13')
    ean_clean = ''.join(filter(str.isdigit, str(ean)))
    if len(ean_clean) == 12:
        # python-barcode expects full 13 to compute checksum if needed; it handles 12 too
        pass
    writer = ImageWriter()
    # Set writer options (quiet_zone, module_width are adjustable)
    options = {
        'module_height': mm_to_px(height_mm, dpi),
        'font_size': 18,
        'text_distance': 4,
        'quiet_zone': 6.0,  # in px for writer, but this writer expects numeric units; python-barcode will scale
    }
    rv = EAN(ean_clean, writer=writer)
    bio = io.BytesIO()
    rv.write(bio, options)
    bio.seek(0)
    img = Image.open(bio).convert("RGBA")
    return img

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
