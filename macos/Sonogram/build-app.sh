#!/bin/bash
set -euo pipefail

# Build Sonogram.app bundle from Swift Package
# Usage: ./build-app.sh [release|debug]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

CONFIG="${1:-release}"
APP_NAME="Sonogram"
BUNDLE_ID="com.sonogram.app"
VERSION="1.0.0"

echo "Building $APP_NAME ($CONFIG)..."

if [[ "$CONFIG" == "release" ]]; then
    swift build -c release 2>&1
    BINARY=".build/release/$APP_NAME"
else
    swift build 2>&1
    BINARY=".build/debug/$APP_NAME"
fi

if [[ ! -f "$BINARY" ]]; then
    echo "ERROR: Build failed — binary not found at $BINARY"
    exit 1
fi

# Create .app bundle structure
APP_DIR="$SCRIPT_DIR/$APP_NAME.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Copy binary
cp "$BINARY" "$APP_DIR/Contents/MacOS/$APP_NAME"

# Generate Info.plist
cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>${APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>${VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>${VERSION}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticTermination</key>
    <true/>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>WAV Audio</string>
            <key>CFBundleTypeRole</key>
            <string>Viewer</string>
            <key>LSItemContentTypes</key>
            <array>
                <string>com.microsoft.waveform-audio</string>
                <string>public.wav</string>
            </array>
        </dict>
    </array>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
PLIST

# Generate an app icon (simple waveform icon using sips if available)
# Create a basic 1024x1024 icon using Python if available
if command -v python3 &>/dev/null; then
    python3 - "$APP_DIR/Contents/Resources" << 'ICONPY'
import sys, os

outdir = sys.argv[1]

try:
    from PIL import Image, ImageDraw
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for sz in sizes:
        img = Image.new("RGBA", (sz, sz), (20, 20, 25, 255))
        draw = ImageDraw.Draw(img)
        # Draw simple waveform bars
        cx, cy = sz // 2, sz // 2
        bar_w = max(1, sz // 20)
        gap = max(2, sz // 12)
        heights = [0.3, 0.5, 0.8, 1.0, 0.7, 0.9, 0.6, 0.4, 0.7, 0.5, 0.3]
        total_w = len(heights) * (bar_w + gap) - gap
        start_x = cx - total_w // 2
        max_h = int(sz * 0.7)
        for i, h in enumerate(heights):
            x = start_x + i * (bar_w + gap)
            bh = int(max_h * h)
            y1 = cy - bh // 2
            y2 = cy + bh // 2
            draw.rectangle([x, y1, x + bar_w, y2], fill=(80, 200, 255, 255))
        img.save(os.path.join(outdir, f"icon_{sz}x{sz}.png"))

    # Create iconset and convert to icns
    iconset = os.path.join(outdir, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    mapping = [
        (16, "icon_16x16.png"),
        (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"),
        (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024, "icon_512x512@2x.png"),
    ]
    for sz, name in mapping:
        src = os.path.join(outdir, f"icon_{sz}x{sz}.png")
        dst = os.path.join(iconset, name)
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, dst)

    icns_path = os.path.join(outdir, 'AppIcon.icns')
    os.system(f"iconutil -c icns '{iconset}' -o '{icns_path}' 2>/dev/null")

    # Clean up individual PNGs
    for sz in sizes:
        p = os.path.join(outdir, f"icon_{sz}x{sz}.png")
        if os.path.exists(p):
            os.remove(p)
    import shutil
    if os.path.exists(iconset):
        shutil.rmtree(iconset)

except ImportError:
    pass
ICONPY
fi

# Remove quarantine attribute so the app opens without Gatekeeper warnings
xattr -cr "$APP_DIR" 2>/dev/null || true

echo ""
echo "Built: $APP_DIR"
echo "Run:   open '$APP_DIR'"
