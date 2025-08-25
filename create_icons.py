#!/usr/bin/env python3
"""
Create icon files for Outlook Add-in
Black background with gold "TW" text in different sizes
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    """Create an icon with specified size"""
    # Create image with black background
    img = Image.new('RGB', (size, size), color='black')
    draw = ImageDraw.Draw(img)
    
    # Calculate font size (roughly 60% of image size)
    font_size = int(size * 0.6)
    
    try:
        # Try to use a system font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        try:
            # Fallback font
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            # Use default font if no system font available
            font = ImageFont.load_default()
    
    # Gold color
    gold_color = '#FFD700'
    
    # Get text dimensions
    text = "TW"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Calculate position to center the text
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill=gold_color, font=font)
    
    # Save the image
    img.save(filename, 'PNG')
    print(f"Created {filename} ({size}x{size})")

def main():
    """Create all required icon sizes"""
    # Create icons directory if it doesn't exist
    icons_dir = "/home/romiteld/outlook/static/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    # Create icons in different sizes
    sizes = [16, 32, 80]
    for size in sizes:
        filename = f"{icons_dir}/icon-{size}.png"
        create_icon(size, filename)
    
    print("\nAll icons created successfully!")
    print("Icons saved in:", icons_dir)

if __name__ == "__main__":
    main()