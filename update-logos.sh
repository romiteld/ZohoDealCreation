#!/bin/bash

# Update Outlook Add-in logos with The Well branding
# This script will replace all icon files with The Well logo

echo "Updating Outlook Add-in logos with The Well branding..."

# Source logo file (provided by user)
SOURCE_LOGO="/tmp/the-well-logo.png"

# Target icon directory
ICON_DIR="/home/romiteld/outlook/static/icons"

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "Installing ImageMagick for image resizing..."
    sudo apt-get update && sudo apt-get install -y imagemagick
fi

# Create different sized icons from the source logo
echo "Creating icon sizes..."

# 16x16
convert "$SOURCE_LOGO" -resize 16x16 -background transparent -gravity center -extent 16x16 "$ICON_DIR/icon-16.png"
echo "✓ Created icon-16.png"

# 32x32
convert "$SOURCE_LOGO" -resize 32x32 -background transparent -gravity center -extent 32x32 "$ICON_DIR/icon-32.png"
echo "✓ Created icon-32.png"

# 64x64
convert "$SOURCE_LOGO" -resize 64x64 -background transparent -gravity center -extent 64x64 "$ICON_DIR/icon-64.png"
echo "✓ Created icon-64.png"

# 80x80
convert "$SOURCE_LOGO" -resize 80x80 -background transparent -gravity center -extent 80x80 "$ICON_DIR/icon-80.png"
echo "✓ Created icon-80.png"

# 128x128
convert "$SOURCE_LOGO" -resize 128x128 -background transparent -gravity center -extent 128x128 "$ICON_DIR/icon-128.png"
echo "✓ Created icon-128.png"

echo ""
echo "✅ All Outlook Add-in icons updated with The Well branding!"
echo ""
echo "Icons updated in: $ICON_DIR"
echo "Sizes created: 16x16, 32x32, 64x64, 80x80, 128x128"
echo ""
echo "Note: These icons will be served when the Container App is deployed."