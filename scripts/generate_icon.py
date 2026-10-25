#!/usr/bin/env python3
"""
Icon generator for DeepUnzip
Creates a professional-looking icon for the application
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_icon():
    """Create the application icon."""
    
    # Icon size (Windows ICO format supports multiple sizes)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    
    # Get the project root and create icons directory
    project_root = Path(__file__).parent.parent.absolute()
    icons_dir = project_root / "icons"
    icons_dir.mkdir(exist_ok=True)
    
    images = []
    
    for size in sizes:
        # Create a new image with RGBA mode (supports transparency)
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Define colors
        bg_color = (45, 125, 210)  # Blue background
        accent_color = (255, 215, 0)  # Gold accent
        text_color = (255, 255, 255)  # White text
        
        # Calculate dimensions based on size
        margin = max(2, size // 16)
        border_width = max(1, size // 32)
        
        # Draw background with rounded rectangle effect
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=max(2, size // 8),
            fill=bg_color,
            outline=accent_color,
            width=border_width
        )
        
        # Draw folder icon elements
        folder_width = size - 4 * margin
        folder_height = folder_width * 0.7
        folder_x = (size - folder_width) // 2
        folder_y = (size - folder_height) // 2 - margin
        
        # Main folder body
        draw.rounded_rectangle(
            [folder_x, folder_y + folder_height * 0.2, 
             folder_x + folder_width, folder_y + folder_height],
            radius=max(1, size // 16),
            fill=(70, 150, 235),
            outline=accent_color,
            width=max(1, border_width // 2)
        )
        
        # Folder tab
        tab_width = folder_width * 0.4
        draw.rounded_rectangle(
            [folder_x, folder_y, 
             folder_x + tab_width, folder_y + folder_height * 0.3],
            radius=max(1, size // 20),
            fill=(70, 150, 235),
            outline=accent_color,
            width=max(1, border_width // 2)
        )
        
        # Add zipper/extraction effect
        zipper_y = folder_y + folder_height * 0.4
        zipper_width = folder_width * 0.6
        zipper_x = folder_x + (folder_width - zipper_width) // 2
        
        # Draw zipper line
        draw.line(
            [zipper_x, zipper_y, zipper_x + zipper_width, zipper_y],
            fill=accent_color,
            width=max(1, size // 32)
        )
        
        # Draw zipper teeth
        teeth_count = max(3, size // 16)
        for i in range(teeth_count):
            x = zipper_x + (zipper_width * i // (teeth_count - 1))
            draw.rectangle(
                [x - 1, zipper_y - 2, x + 1, zipper_y + 2],
                fill=accent_color
            )
        
        # Add text for larger sizes
        if size >= 32:
            try:
                # Try to use a system font, fallback to default
                font_size = max(8, size // 8)
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                
                # Draw "7z" text
                text = "7z"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = (size - text_width) // 2
                text_y = folder_y + folder_height + margin
                
                if text_y + text_height <= size - margin:
                    draw.text((text_x, text_y), text, fill=text_color, font=font)
            except:
                pass  # Skip text if font operations fail
        
        images.append(img)
        
        # Save individual PNG files for reference
        img.save(icons_dir / f"icon_{size}x{size}.png")
    
    # Create ICO file with multiple sizes
    ico_path = icons_dir / "app_icon.ico"
    images[0].save(ico_path, format='ICO', sizes=[(img.width, img.height) for img in images])
    
    print(f"✅ Icon created successfully!")
    print(f"📁 Icons directory: {icons_dir}")
    print(f"🎨 Main icon file: {ico_path}")
    print(f"📏 Generated sizes: {', '.join(f'{s}x{s}' for s in sizes)}")
    
    return ico_path

if __name__ == "__main__":
    try:
        icon_path = create_icon()
        print(f"\n🎯 Icon ready for use: {icon_path}")
    except ImportError:
        print("❌ PIL (Pillow) is required to generate icons.")
        print("📦 Install it with: poetry add pillow")
    except Exception as e:
        print(f"❌ Error creating icon: {e}")
