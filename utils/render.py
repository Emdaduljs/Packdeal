from PIL import Image, ImageOps, ImageFilter, ImageDraw
from . import mapping

def apply_texture(design: Image.Image, template: str) -> Image.Image:
    """
    Apply the design to a simple template. Returns an RGB image ready for display/export.
    Uses an RGBA canvas for safe compositing, then converts to RGB at the end.
    """

    # Base canvas (use RGBA so we can paste with transparency masks safely)
    canvas = Image.new('RGBA', (1200, 800), (255, 255, 255, 255))

    # For demo, use different placements per template
    if template == 'Water Bottle':
        # Simulate a bottle by drawing an outline and applying the design as an oval label
        bottle_box = (450, 150, 750, 650)  # bounding box for bottle
        draw = ImageDraw.Draw(canvas)
        draw.ellipse(bottle_box, outline=(200,200,200,255), width=4)

        # Prepare label from design
        label = mapping.map_to_label(design, (bottle_box[2]-bottle_box[0], int((bottle_box[3]-bottle_box[1])*0.45)))

        # Create oval mask to simulate wrap (mode 'L')
        mask = Image.new("L", label.size, 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0,0,label.size[0],label.size[1]), fill=255)

        # Slight resize to simulate mild curvature/perspective
        label = label.resize((max(1, int(label.size[0]*0.98)), label.size[1]))

        # Paste label onto canvas centered on bottle
        label_pos = (bottle_box[0] + (bottle_box[2]-bottle_box[0]-label.size[0])//2,
                     bottle_box[1] + (bottle_box[3]-bottle_box[1]-label.size[1])//2)
        # Paste RGBA label using the L mask
        canvas.paste(label, label_pos, mask)

        # Add simple shadow as semi-transparent ellipse
        shadow = Image.new('RGBA', canvas.size, (0,0,0,0))
        sdraw = ImageDraw.Draw(shadow)
        sdraw.ellipse((bottle_box[0]+10, bottle_box[3]-40, bottle_box[2]-10, bottle_box[3]-10), fill=(0,0,0,80))
        canvas = Image.alpha_composite(canvas, shadow)

    else:
        # Gift Box - place design on front face of box (robust rectangle drawing)
        box_origin = (300, 200)
        box_size = (600, 400)
        x0, y0 = box_origin
        x1, y1 = x0 + box_size[0], y0 + box_size[1]

        draw = ImageDraw.Draw(canvas)
        outline_color = (180, 180, 180)   # safer 3-tuple RGB
        border_width = 4

        # Try the simple rectangle call (may fail on older Pillow versions)
        try:
            # some Pillow versions accept width; others will raise TypeError
            draw.rectangle([(x0, y0), (x1, y1)], outline=outline_color, width=border_width)
        except TypeError:
            # Fallback for Pillow versions that don't support 'width':
            # draw multiple concentric rectangles to simulate border thickness.
            for i in range(border_width):
                draw.rectangle([(x0+i, y0+i), (x1-i, y1-i)], outline=outline_color)

        # Map design to box face
        face = mapping.map_to_label(design, box_size)
        face_pos = box_origin
        # Paste RGBA face using its alpha channel as mask (robust)
        canvas.paste(face, face_pos, face)

        # Add ribbon (simple) using RGB tuples
        rdraw = ImageDraw.Draw(canvas)
        rx = x0 + box_size[0]//2
        rdraw.rectangle([rx-10, y0, rx+10, y1], fill=(200,30,30))
        rdraw.rectangle([x0, y0+box_size[1]//2-10, x1, y0+box_size[1]//2+10], fill=(200,30,30))

    # Convert back to RGB for display/export
    return canvas.convert('RGB')
