from PIL import Image

def _get_resample_filter():
    """
    Return a Pillow resampling filter that exists in this environment,
    compatible with multiple Pillow versions.
    """
    # Pillow 9+/10+: Image.Resampling.LANCZOS
    try:
        return Image.Resampling.LANCZOS
    except Exception:
        pass
    # older Pillow: Image.LANCZOS
    try:
        return Image.LANCZOS
    except Exception:
        pass
    # fallback
    try:
        return Image.BICUBIC
    except Exception:
        return Image.NEAREST

def map_to_label(design: Image.Image, target_size: tuple) -> Image.Image:
    """
    Resize and center the design into target_size (width, height) returning an RGBA image with transparency.

    This is a simple placeholder for real UV mapping logic.
    """
    target_w, target_h = target_size
    # Preserve aspect ratio and fit into target
    design = design.convert('RGBA')
    resample = _get_resample_filter()

    # Use thumbnail-like semantics but without modifying the original unexpectedly:
    # compute the new size preserving aspect ratio
    orig_w, orig_h = design.size
    scale = min(target_w / orig_w, target_h / orig_h, 1.0)
    new_w = max(1, int(orig_w * scale))
    new_h = max(1, int(orig_h * scale))
    resized = design.resize((new_w, new_h), resample)

    # Create transparent canvas and paste centered
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    x = (target_w - resized.width) // 2
    y = (target_h - resized.height) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas
