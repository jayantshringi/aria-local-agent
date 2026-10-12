import os
from PIL import Image, ImageDraw, ImageFont

def create_aria_icon(size: int, output_path: str):
    # Create image with transparent or gradient background
    img = Image.new("RGBA", (size, size), (11, 15, 25, 255))
    draw = ImageDraw.Draw(img)

    # Gradient background / rounded box
    radius = int(size * 0.22)
    padding = int(size * 0.08)
    box = [padding, padding, size - padding, size - padding]

    # Draw rounded background with indigo/purple glow
    draw.rounded_rectangle(box, radius=radius, fill=(99, 102, 241, 255))

    # Inner subtle accent shape
    inner_pad = int(size * 0.14)
    inner_box = [inner_pad, inner_pad, size - inner_pad, size - inner_pad]
    draw.rounded_rectangle(inner_box, radius=int(radius * 0.7), fill=(168, 85, 247, 220))

    # Center shield / symbol
    cx = size // 2
    cy = size // 2
    sw = int(size * 0.26)
    sh = int(size * 0.30)

    # Shield polygon
    shield_pts = [
        (cx - sw, cy - sh),
        (cx + sw, cy - sh),
        (cx + sw, cy + int(sh * 0.1)),
        (cx, cy + sh),
        (cx - sw, cy + int(sh * 0.1))
    ]
    draw.polygon(shield_pts, fill=(255, 255, 255, 255))

    # Inner checkmark / core in shield
    check_pts = [
        (cx - int(sw * 0.45), cy - int(sh * 0.05)),
        (cx - int(sw * 0.1), cy + int(sh * 0.35)),
        (cx + int(sw * 0.5), cy - int(sh * 0.35)),
    ]
    draw.line(check_pts, fill=(99, 102, 241, 255), width=max(2, int(size * 0.05)), joint="curve")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Generated icon: {output_path} ({size}x{size})")

if __name__ == "__main__":
    for s in [192, 512]:
        create_aria_icon(s, f"web/public/icons/icon-{s}.png")
        create_aria_icon(s, f"web/dist/icons/icon-{s}.png")
