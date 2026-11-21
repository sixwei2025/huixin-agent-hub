#!/bin/zsh
set -eu
app_source="$(cd "$(dirname "$0")" && pwd)"
desktop_bundle="$app_source/../汇芯智能体中台.app"
mkdir -p "$desktop_bundle/Contents/MacOS" "$desktop_bundle/Contents/Resources/web" "$desktop_bundle/Contents/Resources/bin"
/usr/bin/swiftc "$app_source/Desktop.swift" -o "$desktop_bundle/Contents/MacOS/HuixinHub" -framework AppKit -framework WebKit
cp "$app_source/server.py" "$desktop_bundle/Contents/Resources/server.py"
cp "$app_source/web/index.html" "$desktop_bundle/Contents/Resources/web/index.html"
cp "$app_source/web/brand.svg" "$desktop_bundle/Contents/Resources/web/brand.svg"
cp "$app_source/../bin/workbuddy-acp" "$desktop_bundle/Contents/Resources/bin/workbuddy-acp"
cp "$app_source/../bin/acp_stdio_bridge.py" "$desktop_bundle/Contents/Resources/bin/acp_stdio_bridge.py"
cp "$app_source/../bin/grokbot-acp" "$desktop_bundle/Contents/Resources/bin/grokbot-acp"
chmod +x "$desktop_bundle/Contents/Resources/bin/workbuddy-acp" "$desktop_bundle/Contents/Resources/bin/acp_stdio_bridge.py" "$desktop_bundle/Contents/Resources/bin/grokbot-acp"
icon_work=$(mktemp -d)
mkdir -p "$icon_work/Brand.iconset"
/usr/bin/swift "$app_source/make-icon.swift" "$icon_work/Brand.iconset"
/usr/bin/iconutil -c icns "$icon_work/Brand.iconset" -o "$desktop_bundle/Contents/Resources/AppIcon.icns"
cp "$icon_work/Brand.iconset/icon_512x512@2x.png" "$app_source/../汇芯无限标志.png"
cat > "$desktop_bundle/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>com.huixin.agenthub</string>
<key>CFBundleName</key><string>汇芯智能体中台</string>
<key>CFBundleDisplayName</key><string>汇芯智能体中台</string>
<key>CFBundleExecutable</key><string>HuixinHub</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.5.0</string>
<key>CFBundleVersion</key><string>6</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
<key>LSMinimumSystemVersion</key><string>13.0</string>
</dict></plist>
PLIST
/usr/bin/codesign --force --sign - "$desktop_bundle"
echo "已构建：$desktop_bundle"
