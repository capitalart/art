"""
ArtNarrator Signing Service
Processes a single artwork to add a colour-contrasting signature.
"""

from pathlib import Path
import random
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
from sklearn.cluster import KMeans
import config

# Configuration is now fully sourced from config.py
SIGNATURE_PNGS = {
    "beige": config.SIGNATURES_DIR / "beige.png",
    "black": config.SIGNATURES_DIR / "black.png",
    "blue": config.SIGNATURES_DIR / "blue.png",
    "brown": config.SIGNATURES_DIR / "brown.png",
    "gold": config.SIGNATURES_DIR / "gold.png",
    "green": config.SIGNATURES_DIR / "green.png",
    "grey": config.SIGNATURES_DIR / "grey.png",
    "odd": config.SIGNATURES_DIR / "odd.png",
    "red": config.SIGNATURES_DIR / "red.png",
    "skyblue": config.SIGNATURES_DIR / "skyblue.png",
    "white": config.SIGNATURES_DIR / "white.png",
    "yellow": config.SIGNATURES_DIR / "yellow.png"
}

SIGNATURE_COLORS_RGB = {
    "beige": (245, 245, 220), "black": (0, 0, 0), "blue": (0, 0, 255),
    "brown": (139, 69, 19), "gold": (255, 215, 0), "green": (0, 255, 0),
    "grey": (128, 128, 128), "odd": (128, 128, 128), "red": (255, 0, 0),
    "skyblue": (135, 206, 235), "white": (210, 210, 210), "yellow": (255, 255, 0)
}

SMOOTHING_BUFFER_PIXELS = 3
BLUR_RADIUS = 25
NUM_COLORS_FOR_ZONE_ANALYSIS = 2

# === Utility Functions (Mostly unchanged from your script) ===

def get_relative_luminance(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    r = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
    g = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
    b = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def get_contrast_ratio(rgb1, rgb2):
    L1, L2 = get_relative_luminance(rgb1), get_relative_luminance(rgb2)
    return (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)

def get_dominant_color_in_masked_zone(image_data_pixels, mask_pixels, num_colors=1):
    masked_pixels = [image_data_pixels[i] for i, alpha in enumerate(mask_pixels) if alpha > 0]
    if not masked_pixels: return (0, 0, 0)
    
    pixels_array = np.array(masked_pixels).reshape(-1, 3)
    if pixels_array.shape[0] < num_colors:
        return tuple(map(int, np.mean(pixels_array, axis=0)))

    kmeans = KMeans(n_clusters=num_colors, random_state=0, n_init='auto').fit(pixels_array)
    return tuple(map(int, kmeans.cluster_centers_[0]))

def get_contrasting_signature_path(background_rgb):
    best_signature, max_contrast = "black", -1.0
    for name, rgb in SIGNATURE_COLORS_RGB.items():
        if SIGNATURE_PNGS.get(name, Path()).is_file():
            contrast = get_contrast_ratio(background_rgb, rgb)
            if contrast > max_contrast:
                max_contrast, best_signature = contrast, name
    return SIGNATURE_PNGS[best_signature]

# === Main Processing Function (Refactored for Single Image) ===

def add_smart_signature(source_path: Path, destination_path: Path) -> tuple[bool, str]:
    """
    Applies a smart signature to a single image and saves it to the destination.
    Returns a tuple of (success_boolean, message).
    """
    try:
        with Image.open(source_path).convert("RGB") as img:
            width, height = img.size
            choose_right = random.choice([True, False])

            long_edge = max(width, height)
            sig_size = int(long_edge * config.SIGNATURE_SIZE_PERCENTAGE)
            
            dummy_sig_path = next(iter(SIGNATURE_PNGS.values()))
            with Image.open(dummy_sig_path).convert("RGBA") as dummy_sig:
                sw, sh = dummy_sig.size
                if sw > sh:
                    scaled_w, scaled_h = sig_size, int(sh * (sig_size / sw))
                else:
                    scaled_h, scaled_w = sig_size, int(sw * (sig_size / sh))
            
            margin_x = int(width * config.SIGNATURE_MARGIN_PERCENTAGE)
            margin_y = int(height * config.SIGNATURE_MARGIN_PERCENTAGE)

            paste_x = width - scaled_w - margin_x if choose_right else margin_x
            paste_y = height - scaled_h - margin_y

            with Image.open(dummy_sig_path).convert("RGBA") as base_sig:
                resized_sig = base_sig.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                mask_canvas = Image.new("L", img.size, 0)
                mask_canvas.paste(resized_sig.split()[-1], (paste_x, paste_y))
                expanded_mask = mask_canvas.filter(ImageFilter.GaussianBlur(SMOOTHING_BUFFER_PIXELS))
                expanded_mask = expanded_mask.point(lambda x: 255 if x > 10 else 0)

            dom_color = get_dominant_color_in_masked_zone(list(img.getdata()), list(expanded_mask.getdata()), NUM_COLORS_FOR_ZONE_ANALYSIS)
            
            patch_base = Image.new("RGB", img.size, dom_color)
            patch_blurred = patch_base.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
            patch_rgba = patch_blurred.convert("RGBA")
            patch_rgba.putalpha(expanded_mask)

            img_with_patch = Image.alpha_composite(img.convert("RGBA"), patch_rgba)

            sig_path = get_contrasting_signature_path(dom_color)
            with Image.open(sig_path).convert("RGBA") as sig_img:
                sig_img = sig_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
                img_with_patch.paste(sig_img, (paste_x, paste_y), sig_img)

            final_img = img_with_patch.convert("RGB")
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            final_img.save(destination_path)
            
        return True, f"Successfully signed and saved to {destination_path.name}"

    except Exception as e:
        return False, f"Error signing {source_path.name}: {e}"