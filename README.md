# Open Rails Shape Packer

Standalone front-end for packing and unpacking Open Rails `.S` shape files with ORZIP.

## Contents

- `Open_Rails_Shape_Packer_User_Guide.adoc` - AsciiDoctor user guide.
- `ORZIP_GUI.py` - Python/Tkinter application.
- `Run_Open_Rails_Shape_Packer.bat` - friendly Windows launcher.
- `Run_ORZIP_GUI.bat` - older Windows launcher name, kept for compatibility.
- `orzip.exe` - ORZIP backend executable.
- `assets/OpenRailsShapePacker_RSS.ico` - window icon referencing RailSimStuff.com / RSS.
- `assets/OpenRailsShapePacker_RSS.png` - PNG source/export used in the title banner.
- `tools/build_rss_icon.py` - regenerates the RSS/RailSimStuff icon.

## Run

From Windows, double-click:

```bat
Run_Open_Rails_Shape_Packer.bat
```

Or from a command prompt in this folder:

```bat
python ORZIP_GUI.py
```

## Run ORZIP from Open Rails Shape Packer

1. Choose a folder with the Shape Path Browse button.
2. Press `Scan`.
3. Select one or more `.S` files in the Shape Files list, use `Select Uncompressed` / `Select Compressed`, or change Selection to `Use all scanned files`.
4. Pick the Mode: Auto-detect, Compress, Uncompress, Detect, or Validate.
5. Press the bottom `Run ORZIP` button.
6. Watch the `ORZIP Output Log` panel at the bottom of the window. It shows the exact command, live ORZIP stdout/stderr, warnings, and the ORZIP exit code. Use `Clear Log` or `Copy Log` as needed.

The ORZIP command/path field only tells the GUI where `orzip.exe` is. The `Run ORZIP` button actually runs ORZIP.

## Main features

- Scan folders for Open Rails `.S` shape files.
- Select all compressed or all uncompressed files with one click.
- Auto-detect compression action.
- Compress uncompressed shapes.
- Uncompress compressed shapes.
- Detect/verify shape-file type.
- Validate shape files.
- Track successful runs with warnings separately from failures.
- Optional `.PreORZIP` backups before changing files.
- Optional overwrite (`--force`), subfolder scan, and unchanged-file skipping.

## Safety

Work on copies of route or rolling-stock files when possible. Keep `.PreORZIP` backups enabled unless you are processing disposable test copies.

## Windows Executable

A Windows executable version of the tool is packaged in the Releases section.

## AsciiDoctor-PDF is needed to compile the DOCS into a PDF or HTML file.

