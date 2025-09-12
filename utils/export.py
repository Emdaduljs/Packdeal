from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
import io
from PIL import Image

def export_pdf(pil_image: Image.Image):
    """
    Return a BytesIO buffer containing a single-page PDF with the image fit to the page.
    """
    buf = io.BytesIO()
    # Use landscape A4
    page_size = landscape(A4)
    c = pdfcanvas.Canvas(buf, pagesize=page_size)
    # Save PIL image to temporary bytes as PNG
    img_bytes = io.BytesIO()
    pil_image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    # Draw image centered and scaled to fit with margins
    page_w, page_h = page_size
    # Load image dimensions
    img = Image.open(img_bytes)
    img_w, img_h = img.size
    # Determine scale to fit within page with 1cm margins (~28 points)
    margin = 28
    max_w = page_w - 2*margin
    max_h = page_h - 2*margin
    scale = min(max_w / img_w, max_h / img_h, 1.0)
    draw_w = img_w * scale
    draw_h = img_h * scale
    x = (page_w - draw_w) / 2
    y = (page_h - draw_h) / 2
    # Use reportlab to draw the PNG bytes
    img_bytes.seek(0)
    c.drawImage(ImageReader(img_bytes), x, y, width=draw_w, height=draw_h)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf
