# macOS Packaging Guide

**DeskCoach .app Bundle Creation**

This guide covers building an unsigned macOS .app bundle that integrates the background monitoring service and Streamlit UI.

**PRIVACY:** No frames saved. Only metrics stored locally.

---

## Overview

The DeskCoach.app bundle:
- Launches background monitoring service automatically
- Opens Streamlit UI in browser
- Handles graceful shutdown of both processes
- Supports Login Item (launch at login)
- Stores data in `~/Library/Application Support/DeskCoach/`

---

## Prerequisites

### Required
- macOS 10.15 (Catalina) or later
- Python 3.11+
- Virtual environment with dependencies installed

### Optional
- `terminal-notifier` for notifications: `brew install terminal-notifier`
- Pillow for icon generation: `pip install Pillow`

---

## Build Steps

### 1. Prepare Environment

```bash
cd /path/to/deskcoach

# Ensure venv exists and is activated
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install PyInstaller if not already installed
pip install pyinstaller
```

### 2. Run Build Script

```bash
./packaging/macos/build.sh
```

**What it does:**
1. Checks for virtual environment
2. Creates placeholder icon (if missing)
3. Generates PyInstaller spec file
4. Builds one-folder .app bundle
5. Outputs to `dist/DeskCoach.app`

**Build time:** 2-5 minutes (first build)

### 3. Verify Build

```bash
ls -lh dist/DeskCoach.app
# Should show: DeskCoach.app directory

# Check bundle structure
tree -L 3 dist/DeskCoach.app
```

**Expected structure:**
```
DeskCoach.app/
├── Contents/
│   ├── Info.plist
│   ├── MacOS/
│   │   └── entry_launcher (executable)
│   ├── Resources/
│   │   └── icon.icns
│   └── Frameworks/
│       └── (Python runtime and dependencies)
```

---

## Running the App

### First Launch (Unsigned App)

**Important:** macOS Gatekeeper will block unsigned apps by default.

**Method 1: Right-click Open (Recommended)**
1. Right-click `DeskCoach.app` in Finder
2. Select "Open"
3. Click "Open" in the security dialog
4. App will launch

**Method 2: Command Line**
```bash
open dist/DeskCoach.app
```

**Method 3: Remove Quarantine (Advanced)**
```bash
xattr -dr com.apple.quarantine dist/DeskCoach.app
open dist/DeskCoach.app
```

### Subsequent Launches

After first launch, you can double-click normally.

---

## Permissions

### Camera Permission

**Required for posture monitoring.**

On first launch, macOS will prompt:
> "DeskCoach" would like to access the camera.

**Grant access:**
1. Click "OK" in the prompt, OR
2. System Settings → Privacy & Security → Camera → Enable "DeskCoach"

**If denied:**
- App will run but monitoring will be paused
- Re-enable in System Settings → Privacy & Security → Camera

### Notification Permission

**Optional but recommended.**

macOS will prompt:
> "DeskCoach" would like to send you notifications.

**Grant access:**
1. Click "Allow" in the prompt, OR
2. System Settings → Notifications → DeskCoach → Enable

**If denied:**
- Notifications won't appear
- Monitoring still works
- Re-enable in System Settings → Notifications

### Full Disk Access

**Not required.** DeskCoach only accesses:
- Camera (for pose estimation)
- `~/Library/Application Support/DeskCoach/` (for storage)

---

## Storage Location

### App Bundle Storage

When running as .app bundle, all data is stored in:
```
~/Library/Application Support/DeskCoach/
├── calibration.json
├── config.json
├── events.json
├── deskcoach.pid
├── deskcoach.log
├── service.json
├── status.json
└── calibration_status.json
```

**Privacy:** No frames or images. Only metrics and configuration.

### Development Storage

When running from source (not .app), data is stored in:
```
/path/to/deskcoach/storage/
```

---

## Login Item

### Enable Launch at Login

**Method 1: UI (Recommended)**
1. Launch DeskCoach.app
2. In the UI, go to "System Settings" section
3. Check "Launch DeskCoach at login"
4. Status will show "✅ Enabled"

**Method 2: Command Line**
```bash
# From within the app bundle
python3 -c "from core.login_items import add_login_item; print(add_login_item())"
```

### Disable Launch at Login

**Method 1: UI**
1. In the UI, go to "System Settings" section
2. Uncheck "Launch DeskCoach at login"
3. Status will show "❌ Disabled"

**Method 2: System Settings**
1. System Settings → General → Login Items
2. Find "DeskCoach" in the list
3. Click "-" to remove

### Verify Login Item

```bash
# Check if enabled
osascript -e 'tell application "System Events" to get name of every login item'
# Should include "DeskCoach" if enabled
```

---

## Installation

### Install to Applications

```bash
# Copy to /Applications
cp -r dist/DeskCoach.app /Applications/

# Launch from Applications
open /Applications/DeskCoach.app
```

### Uninstall

```bash
# Remove app
rm -rf /Applications/DeskCoach.app

# Remove data (optional)
rm -rf ~/Library/Application\ Support/DeskCoach/

# Remove from Login Items (if enabled)
# System Settings → General → Login Items → Remove DeskCoach
```

---

## Troubleshooting

### App Won't Launch

**Symptom:** Double-click does nothing, or app crashes immediately.

**Solutions:**
1. **Check Gatekeeper:** Right-click → Open (see "First Launch" above)
2. **Check Console:** Open Console.app, filter for "DeskCoach", look for errors
3. **Check permissions:** Ensure Camera permission granted
4. **Run from Terminal:**
   ```bash
   /Applications/DeskCoach.app/Contents/MacOS/entry_launcher
   ```
   Look for error messages

### Camera Not Working

**Symptom:** App launches but monitoring is paused, "Low confidence" message.

**Solutions:**
1. **Grant Camera permission:**
   - System Settings → Privacy & Security → Camera → Enable "DeskCoach"
2. **Restart app** after granting permission
3. **Check camera in use:** Close other apps using camera (Zoom, FaceTime, etc.)
4. **Test camera:**
   ```bash
   # Open Photo Booth to verify camera works
   open -a "Photo Booth"
   ```

### Notifications Not Appearing

**Symptom:** State transitions happen but no notifications.

**Solutions:**
1. **Install terminal-notifier:**
   ```bash
   brew install terminal-notifier
   ```
2. **Grant Notification permission:**
   - System Settings → Notifications → DeskCoach → Enable
3. **Check Do Not Disturb:** Disable DND in Control Center
4. **Check logs:**
   - In UI, go to "Service Logs" section
   - Look for "[POLICY]" lines showing notification attempts

### Login Item Not Working

**Symptom:** Checkbox doesn't work, or app doesn't launch at login.

**Solutions:**
1. **Only works as .app bundle:** Not available when running from source
2. **Check System Settings:**
   - System Settings → General → Login Items
   - Verify "DeskCoach" is in the list
3. **Re-add manually:**
   - System Settings → General → Login Items
   - Click "+" → Select DeskCoach.app → Add
4. **Test:**
   - Log out and log back in
   - DeskCoach should launch automatically

### High CPU Usage

**Symptom:** Activity Monitor shows high CPU for DeskCoach.

**Solutions:**
1. **Check performance mode:**
   - Default is "lightweight" (6 FPS, 424×240, lite model)
   - Should use 10-15% CPU
2. **Check logs for governor:**
   - Look for "[GOVERNOR]" messages
   - Governor should drop FPS if over budget
3. **Restart app** to reset performance settings
4. **Close other apps** using camera

### Storage Location Issues

**Symptom:** App can't find calibration, or data not persisting.

**Solutions:**
1. **Check storage directory:**
   ```bash
   ls -la ~/Library/Application\ Support/DeskCoach/
   ```
2. **Verify permissions:**
   ```bash
   # Should be writable by your user
   ls -ld ~/Library/Application\ Support/DeskCoach/
   ```
3. **Create manually if missing:**
   ```bash
   mkdir -p ~/Library/Application\ Support/DeskCoach/
   ```

---

## Platform-Specific Notes

### macOS Sonoma (14.x)

**Changes:**
- Stricter Gatekeeper enforcement
- New notification permission prompts
- Enhanced privacy controls

**Workarounds:**
- Use "Right-click → Open" for first launch
- Grant permissions when prompted
- Check System Settings → Privacy & Security for any blocks

### macOS Sequoia (15.x)

**Changes:**
- Even stricter app verification
- New permission categories
- Enhanced DND controls

**Workarounds:**
- Same as Sonoma
- May need to explicitly allow in Privacy & Security settings
- DND may block notifications more aggressively (check Focus modes)

### Apple Silicon (M1/M2/M3)

**Notes:**
- App is built as universal binary (works on Intel and Apple Silicon)
- Performance is excellent on Apple Silicon (10-15% CPU typical)
- No Rosetta required

---

## Resetting Permissions (QA)

### Reset Camera Permission

```bash
# Reset all camera permissions (requires restart)
tccutil reset Camera

# Restart Mac
sudo shutdown -r now
```

After restart, launch DeskCoach.app and grant camera permission again.

### Reset Notification Permission

```bash
# Reset all notification permissions
tccutil reset Notifications

# Restart Mac
sudo shutdown -r now
```

After restart, launch DeskCoach.app and grant notification permission again.

### Reset All Permissions

```bash
# Nuclear option: reset all privacy permissions
tccutil reset All

# Restart Mac
sudo shutdown -r now
```

**Warning:** This resets permissions for ALL apps, not just DeskCoach.

---

## Build Customization

### Change App Name

Edit `packaging/macos/Info.plist`:
```xml
<key>CFBundleDisplayName</key>
<string>YourAppName</string>
```

Rebuild with `./packaging/macos/build.sh`

### Change Bundle Identifier

Edit `packaging/macos/build.sh`, find:
```python
bundle_identifier='com.deskcoach.app',
```

Change to:
```python
bundle_identifier='com.yourcompany.yourapp',
```

### Custom Icon

Replace `packaging/macos/icon.icns` with your own icon.

**Requirements:**
- .icns format
- Multiple resolutions (16×16 to 1024×1024)
- Use Icon Composer or `iconutil`

**Generate from PNG:**
```bash
# Create iconset directory
mkdir icon.iconset

# Add PNG files at different sizes
# icon_16x16.png, icon_32x32.png, ..., icon_512x512@2x.png

# Convert to icns
iconutil -c icns icon.iconset -o packaging/macos/icon.icns
```

### Change Storage Location

Edit `packaging/macos/entry_launcher.py`:
```python
# Change this line:
STORAGE_DIR = Path.home() / "Library" / "Application Support" / "DeskCoach"

# To:
STORAGE_DIR = Path.home() / "Documents" / "DeskCoach"
```

Rebuild with `./packaging/macos/build.sh`

---

## Code Signing (Optional)

**For distribution outside the App Store, you need a Developer ID certificate.**

### Prerequisites
- Apple Developer account ($99/year)
- Developer ID Application certificate

### Sign the App

```bash
# Sign the app bundle
codesign --deep --force --verify --verbose \
  --sign "Developer ID Application: Your Name (TEAM_ID)" \
  dist/DeskCoach.app

# Verify signature
codesign --verify --verbose dist/DeskCoach.app
spctl --assess --verbose dist/DeskCoach.app
```

### Notarize the App

```bash
# Create a zip
ditto -c -k --keepParent dist/DeskCoach.app DeskCoach.zip

# Submit for notarization
xcrun notarytool submit DeskCoach.zip \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --password "app-specific-password" \
  --wait

# Staple the ticket
xcrun stapler staple dist/DeskCoach.app
```

**Note:** Notarization can take 5-30 minutes.

---

## Distribution

### Create DMG (Recommended)

```bash
# Install create-dmg
brew install create-dmg

# Create DMG
create-dmg \
  --volname "DeskCoach" \
  --window-pos 200 120 \
  --window-size 800 400 \
  --icon-size 100 \
  --icon "DeskCoach.app" 200 190 \
  --hide-extension "DeskCoach.app" \
  --app-drop-link 600 185 \
  "DeskCoach-1.0.0.dmg" \
  "dist/DeskCoach.app"
```

Users can:
1. Download DMG
2. Open DMG
3. Drag DeskCoach.app to Applications folder

### Create ZIP

```bash
# Create zip
cd dist
zip -r ../DeskCoach-1.0.0.zip DeskCoach.app
cd ..
```

Users can:
1. Download ZIP
2. Extract
3. Move DeskCoach.app to Applications

---

## Summary

**Build:**
```bash
./packaging/macos/build.sh
```

**Install:**
```bash
cp -r dist/DeskCoach.app /Applications/
```

**Run:**
```bash
open /Applications/DeskCoach.app
```

**Enable Login Item:**
- In UI → System Settings → Check "Launch DeskCoach at login"

**Storage:**
- `~/Library/Application Support/DeskCoach/`

**Privacy:**
- ✅ No frames saved
- ✅ Only metrics stored locally
- ✅ Camera permission required
- ✅ Notification permission optional

---

**Questions?** Check the troubleshooting section or open an issue.
