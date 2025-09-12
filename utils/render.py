from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
from . import mapping
import os

def apply_texture(design: Image.Image, template: str) -> Image.Image:
    """
    Apply the design to a template. `template` may be:
      - a builtin name like 'Water Bottle' or 'Gift Box'
      - a filesystem path to a 3D model (models/foo.obj / models/bar.glb)
    For 3D model files we return a placeholder preview (centered text + boxed label).
    """

    # Detect model file
    if isinstance(template, str) and os.path.isfile(template):
        lower = template.lower()
        if lower.endswith((".glb", ".gltf", ".obj")):
            return _render_model_placeholder(design, template)

    # Else, handle builtin templates as before
    return _render_builtin(design, template)


def _render_builtin(design: Image.Image, template: str) -> Image.Image:
    # Reuse your existing logic for Water Bottle and Gift Box
    canvas = Image.new('RGBA', (1200, 800), (255, 255, 255, 255))

    if template == 'Water Bottle':
        bottle_box = (450, 150, 750, 650)
        draw = ImageDraw.Draw(canvas)
        try:
            draw.ellipse(bottle_box, outline=(200,200,200,255), width=4)
        except TypeError:
            draw.ellipse(bottle_box, outline=(200,200,200))

        label = mapping.map_to_label(design, (bottle_box[2]-bottle_box[0],
                                              int((bottle_box[3]-bottle_box[1])*0.45)))
        new_w = max(1, int(label.size[0] * 0.98))
        if new_w != label.size[0]:
            label = label.resize((new_w, label.size[1]))

        mask = Image.new("L", label.size, 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0, 0, label.size[0], label.size[1]), fill=255)

        label_pos = (bottle_box[0] + (bottle_box[2]-bottle_box[0]-label.size[0])//2,
                     bottle_box[1] + (bottle_box[3]-bottle_box[1]-label.size[1])//2)
        canvas.paste(label, label_pos, mask)

        shadow = Image.new('RGBA', canvas.size, (0,0,0,0))
        sdraw = ImageDraw.Draw(shadow)
        sdraw.ellipse((bottle_box[0]+10, bottle_box[3]-40, bottle_box[2]-10, bottle_box[3]-10),
                      fill=(0,0,0,80))
        canvas = Image.alpha_composite(canvas, shadow)

    else:
        # Gift Box
        box_origin = (300, 200)
        box_size = (600, 400)
        x0, y0 = box_origin
        x1, y1 = x0 + box_size[0], y0 + box_size[1]

        draw = ImageDraw.Draw(canvas)
        outline_color = (180, 180, 180)
        border_width = 4
        try:
            draw.rectangle([(x0, y0), (x1, y1)], outline=outline_color, width=border_width)
        except TypeError:
            for i in range(border_width):
                draw.rectangle([(x0+i, y0+i), (x1-i, y1-i)], outline=outline_color)

        face = mapping.map_to_label(design, box_size)
        if face.mode != 'RGBA':
            face = face.convert('RGBA')
        canvas.paste(face, box_origin, face)

        rdraw = ImageDraw.Draw(canvas)
        rx = x0 + box_size[0]//2
        rdraw.rectangle([rx-10, y0, rx+10, y1], fill=(200,30,30,255))
        rdraw.rectangle([x0, y0+box_size[1]//2-10, x1, y0+box_size[1]//2+10], fill=(200,30,30,255))

    return canvas.convert('RGB')


def _render_model_placeholder(design: Image.Image, model_path: str) -> Image.Image:
    """
    Create a placeholder preview for a 3D model selection.
    Shows the model filename and a simple image demonstrating the applied label.
    """
    canvas = Image.new('RGB', (1200, 800), (245, 245, 245))
    draw = ImageDraw.Draw(canvas)

    # Title text: model filename
    model_name = os.path.basename(model_path)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 28)
    except Exception:
        font = None

    title_y = 20
    draw.text((20, title_y), f"3D Model selected: {model_name}", fill=(20,20,20), font=font)

    # Show a central placeholder "viewport" area
    viewport = (150, 80, 1050, 520)
    draw.rectangle(viewport, outline=(200,200,200), width=2)

    # Create a small mock label preview below the viewport using the design
    label = mapping.map_to_label(design, (600, 240))
    label_x = 300
    label_y = 560
    # paste label with transparency
    if label.mode != 'RGBA':
        label = label.convert('RGBA')
    canvas_pil = Image.fromarray(Image.new('RGB', (1,1)).convert('RGB')).convert('RGB') if False else canvas  # no-op to keep type hints happy
    canvas.paste(label, (label_x, label_y), label)

    # explanatory text under label
    info_text = "This is a placeholder preview. Replace with a 3D viewer (Three.js/pythreejs) to render the model with the applied texture."
    draw.text((20, 740), info_text, fill=(80,80,80), font=font)

    return canvas
