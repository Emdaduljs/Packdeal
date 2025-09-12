from PIL import Image, ImageOps, ImageFilter, ImageDraw
from . import mapping

def apply_texture(design: Image.Image, template: str) -> Image.Image:
    """
    Apply the design to a simple template. Returns an RGB image ready for display/export.
    """

    # Base canvas (simulate scene)
    canvas = Image.new('RGB', (1200, 800), (255, 255, 255))

    # For demo, use different placements per template
    if template == 'Water Bottle':
        # Simulate a bottle by drawing an outline and applying the design as an oval label
        bottle_box = (450, 150, 750, 650)  # bounding box for bottle
        draw = ImageDraw.Draw(canvas)
        draw.ellipse(bottle_box, outline=(200,200,200), width=4)

        # Prepare label from design
        label = mapping.map_to_label(design, (bottle_box[2]-bottle_box[0], int((bottle_box[3]-bottle_box[1])*0.45)))

        # Create oval mask to simulate wrap
        mask = Image.new("L", label.size, 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.ellipse((0,0,label.size[0],label.size[1]), fill=255)

        # Slightly warp - use resize for mild perspective effect
        label = label.resize((max(1, int(label.size[0]*0.98)), label.size[1]))

        # Paste label onto canvas centered on bottle
        label_pos = (bottle_box[0] + (bottle_box[2]-bottle_box[0]-label.size[0])//2,
                     bottle_box[1] + (bottle_box[3]-bottle_box[1]-label.size[1])//2)
        canvas.paste(label.convert('RGB'), label_pos, mask)

        # Add simple shadow
        shadow = Image.new('RGBA', canvas.size, (0,0,0,0))
        sdraw = ImageDraw.Draw(shadow)
        sdraw.ellipse((bottle_box[0]+10, bottle_box[3]-40, bottle_box[2]-10, bottle_box[3]-10), fill=(0,0,0,80))
        canvas = Image.alpha_composite(canvas.convert('RGBA'), shadow).convert('RGB')

    else:
        # Gift Box - place design on front face of box
        box_origin = (300, 200)
        box_size = (600, 400)
        # Draw box rectangle
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([box_origin, (box_origin[0]+box_size[0], box_origin[1]+box_size[1])], outline=(180,180,180), width=4)
        # Map design to box face
        face = mapping.map_to_label(design, box_size)
        face_pos = box_origin
        canvas.paste(face.convert('RGB'), face_pos, face)
        # Add ribbon (simple)
        rdraw = ImageDraw.Draw(canvas)
        rx = box_origin[0] + box_size[0]//2
        rdraw.rectangle([rx-10, box_origin[1], rx+10, box_origin[1]+box_size[1]], fill=(200,30,30))
        rdraw.rectangle([box_origin[0], box_origin[1]+box_size[1]//2-10, box_origin[0]+box_size[0], box_origin[1]+box_size[1]//2+10], fill=(200,30,30))

    return canvas
