from PIL import Image
from . import render
import os

def generate_mockup(design: Image.Image, template: str) -> Image.Image:
    """
    Generate a mockup.
    `template` may be a builtin name (e.g., "Water Bottle") or a filesystem path
    to a 3D model (models/*.glb, models/*.obj, etc.). Render will handle both cases.
    """
    return render.apply_texture(design, template)
