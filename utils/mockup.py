from PIL import Image
from . import render

def generate_mockup(design: Image.Image, template: str) -> Image.Image:
    """
    Generate a simple mockup by applying the design as a label/skin on a template.
    This is a 2D compositing approximation meant for an MVP.
    """
    # delegate to render.apply_texture which returns an RGB image
    return render.apply_texture(design, template)
