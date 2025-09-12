from PIL import Image

def map_to_label(design: Image.Image, target_size: tuple) -> Image.Image:
    """
    Resize and center the design into target_size (width, height) returning an RGBA image with transparency.

    This is a simple placeholder for real UV mapping logic.
    """
    target_w, target_h = target_size
    # Preserve aspect ratio and fit into target
    design = design.convert('RGBA')
    design.thumbnail((target_w, target_h), Image.LANCZOS)
    # Create transparent canvas and paste centered
    canvas = Image.new('RGBA', (target_w, target_h), (0,0,0,0))
    x = (target_w - design.width) // 2
    y = (target_h - design.height) // 2
    canvas.paste(design, (x, y), design)
    return canvas
