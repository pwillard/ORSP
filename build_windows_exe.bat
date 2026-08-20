@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=C:\Users\willard\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name OpenRailsShapePacker ^
  --icon "assets\OpenRailsShapePacker_RSS.ico" ^
  --add-binary "orzip.exe;." ^
  --add-data "assets;assets" ^
  --add-data "docs;docs" ^
  ORZIP_GUI.py

if errorlevel 1 exit /b %errorlevel%

echo.
echo Built: %CD%\dist\OpenRailsShapePacker.exe
