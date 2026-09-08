#!/usr/bin/env python3
"""Generate high-resolution brand assets for Shade Complete."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_icon(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background squircle
    radius = size // 5
    bg_color = (15, 23, 42, 255)  # Deep Slate #0f172a
    draw.rounded_rectangle([16, 16, size - 16, size - 16], radius=radius, fill=bg_color)

    # Glowing Sun behind window
    sun_center = (size - 130, 130)
    sun_radius = 65
    draw.ellipse(
        [
            sun_center[0] - sun_radius,
            sun_center[1] - sun_radius,
            sun_center[0] + sun_radius,
            sun_center[1] + sun_radius,
        ],
        fill=(251, 191, 36, 230),  # Amber Gold
    )

    # Sun Rays
    for angle_deg in range(0, 360, 45):
        import math

        rad = math.radians(angle_deg)
        x1 = sun_center[0] + int(80 * math.cos(rad))
        y1 = sun_center[1] + int(80 * math.sin(rad))
        x2 = sun_center[0] + int(105 * math.cos(rad))
        y2 = sun_center[1] + int(105 * math.sin(rad))
        draw.line([x1, y1, x2, y2], fill=(245, 158, 11, 200), width=6)

    # Window Frame (Outer)
    win_left = 70
    win_top = 100
    win_right = size - 70
    win_bottom = size - 80
    draw.rounded_rectangle(
        [win_left, win_top, win_right, win_bottom],
        radius=16,
        outline=(56, 189, 248, 255),
        width=8,
        fill=(30, 41, 59, 180),
    )

    # Shade Cassette / Roller at top
    draw.rounded_rectangle(
        [win_left + 10, win_top + 10, win_right - 10, win_top + 50],
        radius=8,
        fill=(100, 116, 139, 255),
    )

    # Motorized Blind Slats (partially lowered to showcase tracking)
    slat_y_start = win_top + 55
    slat_count = 6
    slat_height = 24
    slat_spacing = 8

    for i in range(slat_count):
        y = slat_y_start + i * (slat_height + slat_spacing)
        # Slat body with tilt shading
        draw.rounded_rectangle(
            [win_left + 16, y, win_right - 16, y + slat_height],
            radius=4,
            fill=(226, 232, 240, 240),
        )
        # Highlight edge
        draw.line(
            [win_left + 18, y + 2, win_right - 18, y + 2],
            fill=(255, 255, 255, 220),
            width=2,
        )
        draw.line(
            [win_left + 18, y + slat_height - 2, win_right - 18, y + slat_height - 2],
            fill=(148, 163, 184, 200),
            width=2,
        )

    # Pull bar / bottom rail
    bottom_y = slat_y_start + slat_count * (slat_height + slat_spacing)
    draw.rounded_rectangle(
        [win_left + 12, bottom_y, win_right - 12, bottom_y + 16],
        radius=4,
        fill=(56, 189, 248, 255),
    )

    return img


def create_logo() -> Image.Image:
    width = 1024
    height = 512
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background card
    draw.rounded_rectangle(
        [16, 16, width - 16, height - 16],
        radius=40,
        fill=(15, 23, 42, 255),
        outline=(51, 65, 85, 255),
        width=4,
    )

    # Insert Icon on left
    icon = create_icon(420)
    img.paste(icon, (46, 46), icon)

    # Title & Subtitle text using default bitmap font fallback or simple rendering
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_sub = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        font_badge = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_badge = ImageFont.load_default()

    draw.text((490, 130), "SHADE COMPLETE", font=font_title, fill=(248, 250, 252, 255))
    draw.text(
        (495, 215),
        "Smart Sun Tracking & Battery Intelligence",
        font=font_sub,
        fill=(56, 189, 248, 255),
    )

    # Badges
    badges = [
        ("SUN TRACKING", (245, 158, 11)),
        ("TILT ENTITIES", (16, 185, 129)),
        ("AUTO CLOSE", (99, 102, 241)),
        ("BATTERY LEARN", (236, 72, 153)),
    ]
    bx = 495
    by = 280
    for text, color in badges:
        bw = len(text) * 12 + 20
        draw.rounded_rectangle(
            [bx, by, bx + bw, by + 34],
            radius=6,
            fill=(*color, 40),
            outline=(*color, 200),
            width=2,
        )
        draw.text((bx + 10, by + 7), text, font=font_badge, fill=(241, 245, 249, 255))
        bx += bw + 14
        if bx > width - 180:
            bx = 495
            by += 44

    return img


def main():
    root = Path(__file__).resolve().parent.parent
    brand_dir = root / "custom_components" / "shade_complete" / "brand"
    brand_dir.mkdir(parents=True, exist_ok=True)

    icon = create_icon()
    icon.save(root / "icon.png")
    icon.save(brand_dir / "icon.png")

    logo = create_logo()
    logo.save(root / "logo.png")
    logo.save(brand_dir / "logo.png")

    print("✅ Brand assets successfully generated at icon.png, logo.png and brand/")


if __name__ == "__main__":
    main()
