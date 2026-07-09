#!/bin/bash
# Genera ~/Applications/CatalàMiner.app apuntando a este checkout.
set -e
cd "$(dirname "$0")"
REPO="$(pwd)"
APP="$HOME/Applications/CatalàMiner.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# icono del Dock/Finder
if [ -f "$REPO/assets/AppIcon.icns" ]; then
  cp "$REPO/assets/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>CatalàMiner</string>
  <key>CFBundleDisplayName</key><string>CatalàMiner</string>
  <key>CFBundleIdentifier</key><string>cat.catalaminer.app</string>
  <key>CFBundleVersion</key><string>0.6.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST

cat > "$APP/Contents/MacOS/launcher" <<LAUNCH
#!/bin/bash
cd "$REPO"
exec "$REPO/.venv/bin/python" -m app.desktop
LAUNCH
chmod +x "$APP/Contents/MacOS/launcher"
echo "✅ Creada $APP — ábrela desde Launchpad o Spotlight."
