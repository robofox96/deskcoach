# macOS Build & Launcher Scripts (M1)

This document explains the **new, from-scratch** macOS packaging pieces for DeskCoach:

- `packaging/macos/entry_launcher.py`
- `packaging/macos/build.sh`

It is intentionally shorter than the full `docs/packaging-macos.md` guide and
focuses only on how the build scripts work and how to use them.

---

## 1. Entry Launcher (`packaging/macos/entry_launcher.py`)

### Purpose

`entry_launcher.py` is the main Python entry point for the
**PyInstaller-built DeskCoach.app**. PyInstaller turns this script into the
executable binary at:

```text
DeskCoach.app/Contents/MacOS/DeskCoach
```

The launcher has **two modes**, controlled by its command-line arguments.

### 1.1 App Mode (default)

App mode is used when a user double-clicks `DeskCoach.app` or runs:

```bash
open dist/DeskCoach.app
```

**Responsibilities:**

- **Storage root setup**
  - Creates a macOS-friendly storage root:
    ```text
    ~/Library/Application Support/DeskCoach/
    ```
  - Changes the current working directory to this folder.
  - Sets the environment variable `DESKCOACH_STORAGE_ROOT` to this path.
  - As a result, anything using relative paths like `storage/status.json`,
    `storage/events.jsonl`, `storage/calibration.json`, etc. writes under:
    ```text
    ~/Library/Application Support/DeskCoach/storage/
    ```

- **Background service startup**
  - Imports `core.get_service_manager()`.
  - Loads system settings from `ui.ConfigManager`:
    - Camera index
    - Target FPS
    - Diagnostics flag
    - Sensitivity preset
  - Calls `ServiceManager.start_background(...)` with those values.
  - Inside the app bundle, `ServiceManager` re-invokes the same executable
    in `--service` mode so that the background pose loop runs in a separate
    process.

- **Start Streamlit UI**
  - Uses Streamlit’s internal bootstrap API:
    ```python
    from streamlit import config as st_config
    from streamlit.web.bootstrap import run as st_run
    ```
  - Configures the server:
    - `server.headless = False`
    - `server.address = "localhost"`
    - `server.port = 8501`
  - Resolves the path to `ui/app_with_controls.py` and runs it via
    `st_run(...)`.
  - Attempts to open the default browser at `http://localhost:8501`.

- **Shutdown behaviour**
  - When the Streamlit server exits (user quits the app), the launcher calls
    `service_mgr.stop_background()` to stop the pose-loop process.
  - This ensures `deskcoach.pid`, `service.json`, and related files are
    cleaned up from the storage directory.

### 1.2 Service Mode (`--service`)

Service mode is an **internal** mode. End users never invoke it directly.
It is used only by `ServiceManager.start_background` inside the bundled app.

**How it works:**

- The launcher sees `--service` on `sys.argv` and routes to `_run_service_mode`.
- `_run_service_mode`:
  - Strips `--service` out of `sys.argv`.
  - Ensures the project root is on `sys.path`.
  - Imports and calls `dev_runner.main()`.
- Because the `--service` flag never reaches `dev_runner`’s `argparse`,
  the CLI interface for development (`python dev_runner.py ...`) remains
  unchanged.

### 1.3 Interaction with `ServiceManager`

`core/ServiceManager` was updated to support the app bundle scenario:

- When `sys.frozen` is **true** (running inside PyInstaller):
  - It re-runs `sys.executable` with `--service ...` instead of launching
    `dev_runner.py` directly.
- When `DESKCOACH_STORAGE_ROOT` is set:
  - The background process’s working directory is set to that folder.
  - All relative `storage/...` paths used by the background service end up
    under the same Application Support tree as the main app.

This keeps the on-disk layout consistent with the project’s privacy and
packaging documentation.

---

## 2. Build Script (`packaging/macos/build.sh`)

### Purpose

`build.sh` is a **thin, documented wrapper** around PyInstaller. It provides
one command that:

1. Activates the project virtualenv.
2. Ensures required Python packages are installed.
3. Runs PyInstaller with sane defaults for DeskCoach.
4. Overwrites the generated `Info.plist` with the curated one.

### 2.1 Prerequisites

Before running the build script, from the repo root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

You do **not** need to install PyInstaller manually; the script will do that.

### 2.2 Running the build

From the repository root:

```bash
chmod +x packaging/macos/build.sh
./packaging/macos/build.sh
```

What the script does, step by step:

1. **Locate repo root**
   - Computes `REPO_ROOT` from the script location and `cd`s into it.

2. **Check virtualenv**
   - Verifies `venv/` exists.
   - If missing, prints the exact commands to create it and exits.

3. **Activate venv and install deps**
   - Activates `venv/bin/activate`.
   - Runs:
     - `pip install -r requirements.txt`
     - `pip install pyinstaller`
   - Both are safe to rerun.

4. **Ensure icon**
   - Checks for `packaging/macos/icon.icns`.
   - If missing, attempts to run `packaging/macos/create_icon.sh` to
     generate a placeholder.

5. **Clean old artifacts**
   - Removes `build/`, `dist/`, and any stale `DeskCoach.spec`.

6. **Run PyInstaller**
   - Invokes:
     ```bash
     pyinstaller \
       --clean --noconfirm \
       --name "DeskCoach" \
       --windowed \
       --icon packaging/macos/icon.icns \
       --osx-bundle-identifier com.deskcoach.app \
       packaging/macos/entry_launcher.py
     ```
   - Produces `dist/DeskCoach.app`.

7. **Copy Info.plist**
   - Copies `packaging/macos/Info.plist` into:
     ```text
     dist/DeskCoach.app/Contents/Info.plist
     ```
   - This ensures the app has the correct camera and notification
     usage descriptions and bundle metadata.

8. **Print next steps**
   - Shows how to:
     - Launch the app from `dist/`.
     - Copy it into `/Applications`.
     - Where data will be stored on disk.

### 2.3 Output

After a successful run you should see:

```text
dist/DeskCoach.app
```

You can then:

```bash
# Run from build folder
open dist/DeskCoach.app

# Or install to Applications
cp -R dist/DeskCoach.app /Applications/
open /Applications/DeskCoach.app
```

On first launch, macOS Gatekeeper may require you to right-click → **Open**
and confirm before allowing future double-click launches.

---

## 3. Data & Privacy

Both the launcher and the build script are aligned with the project’s
privacy rules:

- No camera frames or video are ever written to disk.
- All data are stored locally under:
  ```text
  ~/Library/Application Support/DeskCoach/
  ```
- Stored files are limited to:
  - Calibration baselines (angles/timestamps)
  - Configuration (`ui_config.json`)
  - Event logs (`events.jsonl`)
  - Status snapshots and service metadata
- The existing **Purge Data** control in the UI still removes metrics and
  configuration data.

---

## 4. Quick Reference

- **Build the app**
  ```bash
  ./packaging/macos/build.sh
  ```

- **Install to Applications**
  ```bash
  cp -R dist/DeskCoach.app /Applications/
  ```

- **Run the app**
  ```bash
  open /Applications/DeskCoach.app
  ```

- **Data directory**
  ```text
  ~/Library/Application Support/DeskCoach/
  ```

These scripts are intentionally small and self-contained so they can be
iterated on easily as packaging evolves.
